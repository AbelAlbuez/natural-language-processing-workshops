#!/usr/bin/env python3
"""
Genera un corpus de eventos reales (mismo evento cubierto por varios medios)
usando la API de MediaStack, con la misma estructura que corpus_ejemplo.json.

Uso:
    python3 generar_corpus.py                      # solo El Tiempo, Noticias Caracol, Blu Radio
    python3 generar_corpus.py --todos-los-medios   # agrega otros medios colombianos indexados
    python3 generar_corpus.py --texto-completo     # descarga el texto completo de cada URL
    python3 generar_corpus.py --sin-cache          # ignora respuestas guardadas de la API
    python3 generar_corpus.py --max-eventos 17000  # cuántos eventos generar (por defecto 1000)
    python3 generar_corpus.py --max-peticiones 200 # tope de peticiones nuevas a la API

Dependencias: requests (pip install requests)
API key: archivo .env junto al script con MEDIASTACK_API_KEY=tu_clave
(o la variable de entorno MEDIASTACK_API_KEY). El .env no se sube a git.

Nota: el plan gratuito de MediaStack tiene ~100 peticiones/mes. Las respuestas
se guardan en .cache_mediastack/ para no gastar cuota al volver a ejecutar.
El script pide páginas por rondas hasta llegar a --max-eventos, agotar los
resultados de la API o alcanzar --max-peticiones.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: falta la librería 'requests'. Instálala con: pip3 install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

API_URL = "https://api.mediastack.com/v1/news"
DIR_BASE = os.path.dirname(os.path.abspath(__file__))


def cargar_api_key():
    """Lee MEDIASTACK_API_KEY del entorno o de un archivo .env junto al script."""
    if os.environ.get("MEDIASTACK_API_KEY"):
        return os.environ["MEDIASTACK_API_KEY"]
    ruta_env = os.path.join(DIR_BASE, ".env")
    if os.path.exists(ruta_env):
        with open(ruta_env, encoding="utf-8") as f:
            for linea in f:
                clave, _, valor = linea.strip().partition("=")
                if clave.strip() == "MEDIASTACK_API_KEY":
                    return valor.strip().strip('"').strip("'")
    print("ERROR: falta la API key de MediaStack. Crea un archivo .env junto al script con:")
    print("    MEDIASTACK_API_KEY=tu_clave")
    sys.exit(1)


API_KEY = cargar_api_key()
RUTA_REFERENCIA = os.path.join(DIR_BASE, "corpus_ejemplo.json")
RUTA_SALIDA = os.path.join(DIR_BASE, "corpus_eventos_reales.json")
DIR_CACHE = os.path.join(DIR_BASE, ".cache_mediastack")

# Temas a buscar -> palabras clave enviadas a MediaStack.
# (Los años no se envían como keyword porque MediaStack exige que aparezcan
# literalmente en el texto y eso reduce casi a cero los resultados.)
TEMAS = {
    "reforma tributaria 2023": ["reforma tributaria"],
    "acuerdo de paz": ["acuerdo de paz", "acuerdo paz"],
    "reforma pensional": ["reforma pensional"],
    "elecciones locales 2024": ["elecciones"],
}

# Medios objetivo. Se identifican por el DOMINIO de la URL, no por el código
# de fuente de MediaStack, porque los códigos no son fiables
# (p. ej. "eltiempo" en MediaStack es El Tiempo de Venezuela, eltiempove.com).
MEDIOS = {
    "El Tiempo": {"dominios": ["eltiempo.com"], "codigos": ["eltiempo"]},
    "Noticias Caracol": {"dominios": ["noticias.caracoltv.com", "caracoltv.com"],
                         "codigos": ["noticiascaracol", "caracoltv"]},
    "Blu Radio": {"dominios": ["bluradio.com"], "codigos": ["bluradio"]},
}

# Solo se usan con --todos-los-medios (medios colombianos que MediaStack sí indexa).
MEDIOS_EXTRA = {
    "Caracol Radio": {"dominios": ["caracol.com.co"], "codigos": ["caracol"]},
    "El Colombiano": {"dominios": ["elcolombiano.com"], "codigos": ["El Colombiano"]},
    "W Radio": {"dominios": ["wradio.com.co"], "codigos": ["wradio"]},
    "La Opinión": {"dominios": ["laopinion.com.co", "laopinion.co"], "codigos": ["laopinion"]},
    "La Nación": {"dominios": ["lanacion.com.co"], "codigos": ["lanacion"]},
    "El Diario": {"dominios": ["eldiario.com.co"], "codigos": ["eldiario"]},
    "El Nuevo Día": {"dominios": ["elnuevodia.com.co"], "codigos": ["elnuevodia"]},
}

MIN_ARTICULOS_POR_MEDIO = 20
MAX_EVENTOS_DEFECTO = 1000
MAX_PETICIONES_DEFECTO = 50    # peticiones nuevas a la API por ejecución (las de cache no cuentan)
EVENTOS_PROYECCION = 17000
UMBRAL_SIMILITUD = 0.20        # coseno TF-IDF mínimo para considerar "mismo evento"
VENTANA_DIAS = 4               # artículos del mismo evento deben estar a <= N días

STOPWORDS = set("""
a al algo algunas algunos ante antes aqui asi aun bajo bien cada casi como con
contra cual cuando de del desde donde dos el ella ellas ellos en entre era eran
es esa esas ese eso esos esta estaba estado estan estar este esto estos fue fueron
gran ha habia han hasta hay la las le les lo los mas me mientras muy nada ni no
nos o otra otras otro otros para pero poco por porque que quien se sea segun ser
si sido siempre sin sobre solo son su sus tambien tanto te tiene tienen todo todos
tras tu un una uno unos ya yo dijo dice segun hoy ayer cuales este sera seran
puede pueden hace hacer parte tiene tras luego aunque donde ademas asegura
""".split())


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def tokenizar(texto):
    return [t for t in re.findall(r"[a-z0-9]+", normalizar(texto))
            if len(t) > 3 and t not in STOPWORDS]


def dominio(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def identificar_medio(articulo, medios):
    """Devuelve el nombre del medio si el artículo pertenece a uno de los objetivo."""
    host = dominio(articulo.get("url") or "")
    for nombre, cfg in medios.items():
        for d in cfg["dominios"]:
            if host == d or host.endswith("." + d):
                return nombre
    return None


def limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = re.sub(r"&#?\w+;", " ", texto)
    texto = texto.replace("[…]", "").replace("[...]", "")
    return re.sub(r"\s+", " ", texto).strip()


def leer_referencia():
    """Lee corpus_ejemplo.json solo para obtener los campos esperados."""
    campos_por_defecto = ["evento_id", "medio", "titulo", "fecha", "url", "texto"]
    try:
        with open(RUTA_REFERENCIA, encoding="utf-8") as f:
            datos = json.load(f)
        campos = list(datos[0].keys())
        print("✓ Estructura de referencia (corpus_ejemplo.json): " + ", ".join(campos))
        return campos
    except (OSError, ValueError, IndexError, KeyError) as e:
        print("⚠ No se pudo leer corpus_ejemplo.json ({}). Se usa la estructura estándar.".format(e))
        return campos_por_defecto


# ---------------------------------------------------------------------------
# MediaStack
# ---------------------------------------------------------------------------

class ErrorMediaStack(Exception):
    pass


MENSAJES_ERROR = {
    "invalid_access_key": "La API key no es válida. Revisa MEDIASTACK_API_KEY en el archivo .env.",
    "missing_access_key": "No se envió la API key.",
    "inactive_user": "La cuenta de MediaStack está inactiva.",
    "https_access_restricted": "Tu plan no permite HTTPS. Cambia API_URL a http://api.mediastack.com/v1/news",
    "usage_limit_reached": "Se agotó la cuota mensual de peticiones de MediaStack.",
    "rate_limit_reached": "Demasiadas peticiones seguidas. Espera un momento y vuelve a intentar.",
    "function_access_restricted": "Tu plan de MediaStack no permite esta función.",
}


def ruta_cache_de(params):
    clave = hashlib.md5(json.dumps({k: v for k, v in params.items() if k != "access_key"},
                                   sort_keys=True).encode()).hexdigest()
    return os.path.join(DIR_CACHE, clave + ".json")


def consultar_mediastack(params, usar_cache=True):
    ruta_cache = ruta_cache_de(params)
    params = dict(params, access_key=API_KEY)

    if usar_cache and os.path.exists(ruta_cache):
        with open(ruta_cache, encoding="utf-8") as f:
            return json.load(f), True

    for intento in range(3):
        try:
            resp = requests.get(API_URL, params=params, timeout=30)
        except requests.exceptions.ConnectionError:
            raise ErrorMediaStack("No hay conexión con api.mediastack.com. Revisa tu internet.")
        except requests.exceptions.Timeout:
            if intento < 2:
                time.sleep(2)
                continue
            raise ErrorMediaStack("MediaStack no respondió (timeout) tras 3 intentos.")

        try:
            datos = resp.json()
        except ValueError:
            raise ErrorMediaStack("Respuesta no válida de MediaStack (HTTP {}): {}".format(
                resp.status_code, resp.text[:200]))

        if "error" in datos:
            err = datos["error"]
            codigo = err.get("code", "")
            if codigo == "rate_limit_reached" and intento < 2:
                time.sleep(5)
                continue
            msg = MENSAJES_ERROR.get(codigo, err.get("message", "Error desconocido"))
            raise ErrorMediaStack("[{}] {}".format(codigo, msg))

        os.makedirs(DIR_CACHE, exist_ok=True)
        with open(ruta_cache, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        return datos, False

    raise ErrorMediaStack("No se pudo completar la consulta.")


def buscar_y_agrupar(medios, usar_cache, max_eventos, max_peticiones):
    """
    Busca por rondas: en cada ronda pide la siguiente página de cada consulta
    (palabra clave × estrategia) y vuelve a agrupar. Se detiene al llegar a
    max_eventos, al agotar los resultados o al gastar max_peticiones nuevas.
    """
    codigos = sorted({c for cfg in medios.values() for c in cfg["codigos"]})
    # Dos estrategias: por país (co) y por código de fuente, porque algunos
    # medios colombianos no están marcados con country=co en MediaStack.
    estrategias = [
        ("país=co", {"countries": "co"}),
        ("fuentes", {"sources": ",".join(codigos)}),
    ]
    consultas = [{"tema": tema, "kw": kw, "est": nombre_est, "filtro": filtro,
                  "pagina": 0, "agotada": False}
                 for tema, keywords in TEMAS.items()
                 for kw in keywords
                 for nombre_est, filtro in estrategias]

    encontrados = {}   # url -> artículo
    total_api = 0
    peticiones = 0
    eventos = []
    motivo = ""
    ronda = 0

    while True:
        ronda += 1
        print("\n🔎 Ronda {} (página {} de cada consulta)".format(ronda, ronda))
        for i, c in enumerate(consultas, start=1):
            if c["agotada"]:
                continue
            params = dict(c["filtro"], keywords=c["kw"], languages="es", limit=100,
                          offset=c["pagina"] * 100, sort="published_desc")
            en_cache = usar_cache and os.path.exists(ruta_cache_de(params))
            if not en_cache and peticiones >= max_peticiones:
                motivo = "se alcanzó --max-peticiones ({})".format(max_peticiones)
                break
            try:
                datos, desde_cache = consultar_mediastack(params, usar_cache)
            except ErrorMediaStack as e:
                if not encontrados:
                    raise
                # Con artículos ya descargados, se sigue con lo que hay.
                motivo = "error de MediaStack: {}".format(e)
                break
            if not desde_cache:
                peticiones += 1
            articulos = datos.get("data", [])
            total = datos.get("pagination", {}).get("total", 0)
            total_api += len(articulos)
            c["pagina"] += 1
            if not articulos or c["pagina"] * 100 >= total:
                c["agotada"] = True

            nuevos = 0
            for a in articulos:
                medio = identificar_medio(a, medios)
                if medio and a.get("url") and a["url"] not in encontrados:
                    encontrados[a["url"]] = dict(a, medio=medio, tema=c["tema"])
                    nuevos += 1

            print("   [{}/{}] {} '{}' ({}) pág {}... ✅ {} artículos, {} de medios objetivo{}".format(
                i, len(consultas), c["tema"], c["kw"], c["est"], c["pagina"],
                len(articulos), nuevos, " (cache)" if desde_cache else ""))

        print("   Acumulado: {} artículos de medios objetivo | {} peticiones nuevas".format(
            len(encontrados), peticiones))

        if encontrados:
            eventos = agrupar_eventos(list(encontrados.values()), max_eventos)
            print("   Eventos (2+ medios) hasta ahora: {} / {}".format(len(eventos), max_eventos))

        if len(eventos) >= max_eventos:
            motivo = "se alcanzó --max-eventos ({})".format(max_eventos)
        elif all(c["agotada"] for c in consultas):
            motivo = "MediaStack no tiene más resultados para estas palabras clave"
        if motivo:
            break

    print("\n⏹  Búsqueda terminada: {}".format(motivo))
    return list(encontrados.values()), eventos, total_api, peticiones, motivo


# ---------------------------------------------------------------------------
# Texto completo (opcional)
# ---------------------------------------------------------------------------

class ExtractorParrafos(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.parrafos = []
        self._en_p = 0
        self._ignorar = 0
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "aside"):
            self._ignorar += 1
        elif tag == "p":
            self._en_p += 1
            self._buffer = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "aside") and self._ignorar:
            self._ignorar -= 1
        elif tag == "p" and self._en_p:
            self._en_p -= 1
            texto = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            if len(texto) > 60:
                self.parrafos.append(texto)

    def handle_data(self, data):
        if self._en_p and not self._ignorar:
            self._buffer.append(data)


def descargar_texto(url):
    try:
        resp = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) corpus-academico/1.0"})
        resp.raise_for_status()
        parser = ExtractorParrafos()
        parser.feed(resp.text)
        return " ".join(parser.parrafos)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Agrupación por evento
# ---------------------------------------------------------------------------

def fecha_de(articulo):
    try:
        return datetime.strptime(articulo["published_at"][:10], "%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def vectores_tfidf(articulos):
    docs = [Counter(tokenizar(((a.get("title") or "") + " ") * 2 + (a.get("description") or "")))
            for a in articulos]
    # El título se duplica para darle más peso que a la descripción.
    df = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(docs)
    vectores = []
    for d in docs:
        v = {t: tf * math.log((1 + n) / (1 + df[t])) + 1e-9 for t, tf in d.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vectores.append({t: x / norma for t, x in v.items()})
    return vectores


def coseno(v1, v2):
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(x * v2.get(t, 0.0) for t, x in v1.items())


def agrupar_eventos(articulos, max_eventos):
    """
    Agrupa artículos de distintos medios que hablan del mismo hecho:
    mismo tema, fechas cercanas y similitud TF-IDF >= UMBRAL_SIMILITUD.
    Devuelve solo grupos con 2+ medios distintos, con un artículo por medio.
    """
    articulos = [a for a in articulos if fecha_de(a)]
    for a, v in zip(articulos, vectores_tfidf(articulos)):
        a["_vec"] = v
        a["_fecha"] = fecha_de(a)

    # Pares candidatos (de medios distintos), ordenados por similitud. Solo se
    # comparan artículos del mismo tema dentro de la ventana de días, así el
    # costo crece con el tamaño de la ventana y no con el cuadrado del corpus.
    por_tema = defaultdict(list)
    for i, a in enumerate(articulos):
        por_tema[a["tema"]].append(i)

    pares = []
    procesados = 0
    for indices in por_tema.values():
        indices.sort(key=lambda k: articulos[k]["_fecha"])
        inicio = 0
        for pos, j in enumerate(indices):
            b = articulos[j]
            while (b["_fecha"] - articulos[indices[inicio]]["_fecha"]).days > VENTANA_DIAS:
                inicio += 1
            for i in indices[inicio:pos]:
                a = articulos[i]
                if a["medio"] == b["medio"]:
                    continue
                sim = coseno(a["_vec"], b["_vec"])
                if sim >= UMBRAL_SIMILITUD:
                    pares.append((sim, i, j))
            procesados += 1
            if procesados % 1000 == 0:
                print("   [Agrupando] {} artículos procesados...".format(procesados))
    pares.sort(reverse=True)

    # Unión de grupos: un grupo no puede tener dos artículos del mismo medio.
    grupo_de = {}
    grupos = {}
    for sim, i, j in pares:
        gi, gj = grupo_de.get(i), grupo_de.get(j)
        if gi is None and gj is None:
            gid = len(grupos)
            grupos[gid] = {i, j}
            grupo_de[i] = grupo_de[j] = gid
        elif gi is not None and gj is None:
            if articulos[j]["medio"] not in {articulos[k]["medio"] for k in grupos[gi]}:
                grupos[gi].add(j)
                grupo_de[j] = gi
        elif gj is not None and gi is None:
            if articulos[i]["medio"] not in {articulos[k]["medio"] for k in grupos[gj]}:
                grupos[gj].add(i)
                grupo_de[i] = gj
        elif gi != gj:
            medios_i = {articulos[k]["medio"] for k in grupos[gi]}
            medios_j = {articulos[k]["medio"] for k in grupos[gj]}
            if not medios_i & medios_j:
                for k in grupos[gj]:
                    grupo_de[k] = gi
                grupos[gi] |= grupos.pop(gj)

    eventos = [[articulos[k] for k in miembros] for miembros in grupos.values()]
    # Prioriza eventos cubiertos por más medios y más recientes.
    eventos.sort(key=lambda ev: (len(ev), max(a["published_at"] for a in ev)), reverse=True)
    return eventos[:max_eventos]


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def construir_corpus(eventos, campos, texto_completo):
    corpus = []
    total = sum(len(ev) for ev in eventos)
    n = 0
    ancho = max(3, len(str(len(eventos))))
    for idx, evento in enumerate(eventos, start=1):
        evento_id = "evento-{:0{}d}".format(idx, ancho)
        for a in sorted(evento, key=lambda x: x["medio"]):
            n += 1
            texto = limpiar_html(a.get("description"))
            if texto_completo:
                print("   📄 [{}/{}] Descargando texto: {}".format(n, total, a["url"][:80]))
                completo = descargar_texto(a["url"])
                if len(completo) > len(texto):
                    texto = completo
            registro = {
                "evento_id": evento_id,
                "medio": a["medio"],
                "titulo": limpiar_html(a.get("title")),
                "fecha": (a.get("published_at") or "")[:10],
                "url": a["url"],
                "texto": texto,
            }
            corpus.append({c: registro.get(c, "") for c in campos})
    return corpus


def main():
    parser = argparse.ArgumentParser(description="Genera corpus de eventos reales con MediaStack.")
    parser.add_argument("--todos-los-medios", action="store_true",
                        help="Incluir otros medios colombianos indexados por MediaStack.")
    parser.add_argument("--texto-completo", action="store_true",
                        help="Descargar el texto completo de cada artículo desde su URL.")
    parser.add_argument("--sin-cache", action="store_true",
                        help="No usar respuestas guardadas de MediaStack (gasta cuota).")
    parser.add_argument("--max-eventos", type=int, default=MAX_EVENTOS_DEFECTO, metavar="N",
                        help="Número de eventos a generar (por defecto {}).".format(MAX_EVENTOS_DEFECTO))
    parser.add_argument("--max-peticiones", type=int, default=MAX_PETICIONES_DEFECTO, metavar="N",
                        help="Tope de peticiones nuevas a MediaStack (por defecto {}).".format(
                            MAX_PETICIONES_DEFECTO))
    args = parser.parse_args()
    if args.max_eventos < 1:
        parser.error("--max-eventos debe ser mayor que 0")

    print("=" * 70)
    print("GENERADOR DE CORPUS DE EVENTOS REALES — MediaStack")
    print("=" * 70)

    campos = leer_referencia()
    medios = dict(MEDIOS)
    if args.todos_los_medios:
        medios.update(MEDIOS_EXTRA)
    print("✓ Medios objetivo: " + ", ".join(medios))
    print("✓ Eventos solicitados: {}  |  Tope de peticiones nuevas: {}".format(
        args.max_eventos, args.max_peticiones))

    inicio = time.time()
    print("🕐 Inicio: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    try:
        articulos, eventos, total_api, peticiones, motivo = buscar_y_agrupar(
            medios, not args.sin_cache, args.max_eventos, args.max_peticiones)
    except ErrorMediaStack as e:
        print("\n❌ Error de MediaStack: {}".format(e))
        sys.exit(1)

    print("\n" + "-" * 70)
    print("Resultados recibidos de la API: {}  |  Peticiones nuevas gastadas: {}".format(
        total_api, peticiones))
    print("Artículos de los medios objetivo: {}".format(len(articulos)))
    por_medio = Counter(a["medio"] for a in articulos)
    for m in medios:
        marca = "✓" if por_medio[m] >= MIN_ARTICULOS_POR_MEDIO else "⚠"
        print("   {} {:<18} {:>4} artículos".format(marca, m, por_medio[m]))

    if not articulos:
        print("\n❌ No se encontraron artículos de los medios objetivo.")
        print("   Sugerencias:")
        print("   · Prueba con palabras clave diferentes (edita el diccionario TEMAS).")
        print("   · MediaStack no indexa todos los medios colombianos; ejecuta con")
        print("     --todos-los-medios para incluir los que sí están disponibles.")
        sys.exit(2)

    if not eventos:
        print("\n⚠ Se encontraron artículos, pero ningún evento cubierto por 2+ medios.")
        print("   Sugerencias: usa otras palabras clave, ejecuta con --todos-los-medios,")
        print("   o baja UMBRAL_SIMILITUD (actual {}) en el script.".format(UMBRAL_SIMILITUD))
        sys.exit(2)

    corpus = construir_corpus(eventos, campos, args.texto_completo)

    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)

    duracion = time.time() - inicio
    tamano_mb = os.path.getsize(RUTA_SALIDA) / (1024 * 1024)
    print("🕐 Fin: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    print("\n" + "=" * 70)
    print("ESTADÍSTICAS FINALES")
    print("=" * 70)
    print("Eventos encontrados (2+ medios): {}".format(len(eventos)))
    print("Artículos en el corpus:          {}".format(len(corpus)))
    print("\nArtículos por medio en el corpus:")
    for m, c in Counter(r["medio"] for r in corpus).most_common():
        print("   {:<18} {:>4}".format(m, c))
    print("\nEventos por tema:")
    temas = Counter(ev[0]["tema"] for ev in eventos)
    for t, c in temas.most_common():
        print("   {:<26} {:>3}".format(t, c))
    print("\nEventos por número de medios:")
    for k, c in sorted(Counter(len(ev) for ev in eventos).items(), reverse=True):
        print("   {} medios: {} eventos".format(k, c))
    print("\n✓ Corpus guardado en: {}".format(RUTA_SALIDA))

    velocidad = len(eventos) / duracion if duracion > 0 else 0.0
    print("\n" + "=" * 70)
    print("RESULTADO FINAL:")
    print("=" * 70)
    print("⏱️  Tiempo: {:.1f} segundos ({:.1f} minutos)".format(duracion, duracion / 60))
    print("📁 Tamaño archivo: {:.2f} MB".format(tamano_mb))
    print("📊 Eventos: {} (solicitados: {})".format(len(eventos), args.max_eventos))
    print("📰 Artículos: {}".format(len(corpus)))
    print("📈 Velocidad: {:.2f} eventos/segundo".format(velocidad))
    print("🌐 Peticiones nuevas a MediaStack: {}".format(peticiones))
    if len(eventos) < args.max_eventos:
        print("⚠  Se generaron menos eventos de los solicitados: {}.".format(motivo))

    factor = float(EVENTOS_PROYECCION) / len(eventos)
    tiempo_est = duracion * factor
    print("\nPROYECCIÓN A {:,} EVENTOS:".format(EVENTOS_PROYECCION))
    print("⏱️  Tiempo estimado: {:.1f} minutos".format(tiempo_est / 60))
    print("📁 Tamaño estimado: {:.1f} MB".format(tamano_mb * factor))
    print("   (extrapolación lineal desde {} eventos; no considera la cuota de MediaStack".format(
        len(eventos)))
    print("    ni si la API tiene suficientes artículos; si se usó cache, el tiempo real será mayor)")


if __name__ == "__main__":
    main()
