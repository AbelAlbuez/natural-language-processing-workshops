#!/usr/bin/env python3
"""
Script para generar corpus con NewsAPI
ADVERTENCIA: NewsAPI tiene limitaciones (100 resultados max, 30 días)
y NO indexa El Tiempo, Caracol, Blu Radio
"""

import requests
import json
import time
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# API Key NewsAPI desde variable de entorno
NEWSAPI_KEY = os.getenv('NEWSAPI_KEY', 'd8e82adf19434eb0a1b3a57925071b8c')
NEWSAPI_URL = 'https://newsapi.org/v2/everything'

KEYWORDS = [
    'reforma tributaria',
    'acuerdo paz',
    'reforma pensional',
    'elecciones',
    'gobierno colombia'
]

def buscar_noticias_newsapi(palabra, limit=100):
    """Busca en NewsAPI"""
    try:
        params = {
            'q': palabra,
            'apiKey': NEWSAPI_KEY,
            'sortBy': 'publishedAt',
            'language': 'es',
            'pageSize': min(limit, 100)  # NewsAPI limita a 100
        }

        response = requests.get(NEWSAPI_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'articles' in data:
                return data.get('articles', [])
            elif 'error' in data:
                print(f"   ERROR NewsAPI: {data['error'].get('message', 'Unknown')}")
                return []
    except Exception as e:
        print(f"   Error: {e}")
    return []

def agrupar_eventos(articulos, max_eventos=None):
    """Agrupa artículos por evento"""
    eventos_dict = defaultdict(list)

    for art in articulos:
        titulo = art.get('title', '').lower()
        descripcion = art.get('description', '').lower() if art.get('description') else ''
        texto = (titulo + ' ' + descripcion).split()

        palabras = tuple(sorted(set([p for p in texto if len(p) > 4])))

        if palabras:
            eventos_dict[palabras].append({
                'medio': art.get('source', {}).get('name', 'unknown'),
                'titulo': art.get('title', '')[:100],
                'fecha': art.get('publishedAt', '')[:10],
                'url': art.get('url', ''),
                'texto': (art.get('description', '') or '')[:500]
            })

    # Filtrar: 2+ medios
    eventos = []
    for i, (palabras, grupo) in enumerate(eventos_dict.items(), 1):
        if len(grupo) >= 2:
            eventos.append({
                'evento_id': f'evento-{i:06d}',
                'fecha': grupo[0]['fecha'],
                'titulo': grupo[0]['titulo'],
                'medios_encontrados': len(set(a['medio'] for a in grupo)),
                'articulos': grupo
            })

        if max_eventos and len(eventos) >= max_eventos:
            break

    return eventos

def generar_corpus_newsapi(max_eventos=1000, nombre_salida='corpus_eventos_newsapi.json'):
    """Genera corpus con NewsAPI"""

    print("\n" + "="*70)
    print("GENERADOR DE CORPUS - NewsAPI")
    print("="*70)
    print(f"Meta: {max_eventos:,} eventos")
    print(f"ADVERTENCIA: NewsAPI limitado a 100 resultados/consulta")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    inicio = time.time()

    # Buscar
    print(f"Buscando en NewsAPI...")
    todos_articulos = []

    for i, palabra in enumerate(KEYWORDS, 1):
        print(f"   [{i}/{len(KEYWORDS)}] {palabra}...", end=' ')
        articulos = buscar_noticias_newsapi(palabra, limit=100)
        todos_articulos.extend(articulos)
        print(f"OK ({len(articulos)} articulos)")
        time.sleep(0.5)  # Rate limit

    print(f"\nTotal: {len(todos_articulos)} artículos")

    # Agrupar
    print(f"Agrupando por eventos (2+ medios)...")
    eventos = agrupar_eventos(todos_articulos, max_eventos=max_eventos)

    # Guardar
    print(f"Guardando {len(eventos)} eventos...")
    with open(nombre_salida, 'w', encoding='utf-8') as f:
        json.dump(eventos, f, indent=2, ensure_ascii=False)

    # Estadísticas
    tiempo_total = time.time() - inicio
    tamaño_mb = Path(nombre_salida).stat().st_size / (1024 * 1024)

    print("\n" + "="*70)
    print("RESULTADO FINAL")
    print("="*70)
    print(f"Tiempo:       {tiempo_total:.1f} segundos ({tiempo_total/60:.1f} minutos)")
    print(f"Archivo:      {nombre_salida}")
    print(f"Tamaño:       {tamaño_mb:.2f} MB")
    print(f"Eventos:      {len(eventos)} (solicitados: {max_eventos})")
    print(f"Artículos:    {sum(len(e['articulos']) for e in eventos)}")
    if len(eventos) > 0:
        print(f"Velocidad:    {len(eventos)/tiempo_total:.2f} eventos/segundo")
    print("="*70)

    if len(eventos) == 0:
        print("\nADVERTENCIA: No se encontraron eventos (0 artículos con 2+ medios)")
        print("NewsAPI no indexa El Tiempo, Caracol, Blu Radio")

    return eventos

if __name__ == '__main__':
    max_eventos = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    if not NEWSAPI_KEY or NEWSAPI_KEY == 'd8e82adf19434eb0a1b3a57925071b8c':
        print("\nADVERTENCIA: Usando API key default")
        print("Asegurate de tener NEWSAPI_KEY en variables de entorno\n")

    eventos = generar_corpus_newsapi(max_eventos=max_eventos)
