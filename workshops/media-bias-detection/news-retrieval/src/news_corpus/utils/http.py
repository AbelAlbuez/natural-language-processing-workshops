"""Cliente HTTP con rate limiting, reintentos y backoff (§19).

El rate limiter es por proveedor, no global: los sitemaps aguantan 1 req/s sin
problema, mientras que GDELT necesita una cada 25 s. Un límite único obligaría
a ir al ritmo del más lento.
"""

from __future__ import annotations

import gzip
import time
from dataclasses import dataclass

import httpx

from news_corpus.config.settings import get_settings
from news_corpus.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Espaciado mínimo entre peticiones al mismo proveedor."""

    def __init__(self, rate_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._last_call = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


class FetchError(RuntimeError):
    """La petición no se pudo completar tras agotar los reintentos.

    Se distingue de "no había nada": un bloque que falla se reintenta, uno
    vacío legítimo se completa. Confundirlos es el error que deja huecos
    silenciosos en el corpus.
    """


class NotFound(RuntimeError):
    """404: el recurso no existe. No tiene sentido reintentarlo.

    En un sitemap mensual esto suele significar que el medio no publicó ese
    mes, o que el archivo no llega tan atrás. Es información, no un fallo.
    """


@dataclass
class Response:
    url: str
    status: int
    text: str


class HttpFetcher:
    def __init__(self, provider: str, rate_per_sec: float | None = None) -> None:
        settings = get_settings()
        self.provider = provider
        self._limiter = RateLimiter(
            rate_per_sec if rate_per_sec is not None else settings.rate_for(provider)
        )
        self._client = httpx.Client(
            timeout=settings.request_timeout_sec,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        self._max_retries = settings.max_retries

    def __enter__(self) -> HttpFetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, url: str) -> Response:
        last_error: str = "sin intentos"

        for attempt in range(self._max_retries):
            self._limiter.wait()
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "error de red", url=url, intento=attempt + 1, error=last_error
                )
                time.sleep(2**attempt)
                continue

            if resp.status_code == 404:
                raise NotFound(url)

            # 429 y 5xx son transitorios: reintentar con backoff.
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                wait = 2**attempt
                logger.warning(
                    "respuesta transitoria",
                    url=url,
                    status=resp.status_code,
                    espera_s=wait,
                    intento=attempt + 1,
                )
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                raise FetchError(f"{url} devolvió HTTP {resp.status_code}")

            return Response(url=url, status=resp.status_code, text=_decode(url, resp))

        raise FetchError(
            f"{url} no respondió tras {self._max_retries} intentos ({last_error})"
        )


def _decode(url: str, resp: httpx.Response) -> str:
    """Descomprime los sitemaps .gz de La República y RCN.

    httpx ya deshace el `Content-Encoding: gzip` del transporte, pero estos
    archivos son .gz *como contenido*, no como codificación de transferencia.
    """
    body = resp.content
    if url.endswith(".gz") or body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except (OSError, EOFError) as exc:
            raise FetchError(f"{url}: no se pudo descomprimir ({exc})") from exc
    return body.decode("utf-8", errors="replace")
