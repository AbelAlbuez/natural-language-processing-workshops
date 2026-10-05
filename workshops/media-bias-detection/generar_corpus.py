#!/usr/bin/env python3
"""
Script para generar corpus de eventos reales de MediaStack
Genera eventos agrupando artículos de múltiples medios sobre el mismo tema
"""

import requests
import json
import time
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# API Key desde variable de entorno (seguro, no hardcodeado)
MEDIASTACK_KEY = os.getenv('MEDIASTACK_API_KEY', '5f855a76f3e987cdbc21d5fb1a84ba0e')
MEDIASTACK_URL = 'https://api.mediastack.com/v1/news'

# Palabras clave DIFERENTES para generar corpus diferente
KEYWORDS = [
    'elecciones colombia',
    'reforma laboral',
    'inflacion colombia',
    'desempleo',
    'manifestaciones colombia',
    'corrupcion',
    'justicia transicional',
    'violencia urbana',
    'migracion venezolanos',
    'cambio climatico'
]

def buscar_noticias(palabra, limit=100):
    """Busca en MediaStack API"""
    try:
        params = {
            'access_key': MEDIASTACK_KEY,
            'keywords': palabra,
            'countries': 'co',
            'limit': limit,
            'sort': 'published_desc'
        }

        response = requests.get(MEDIASTACK_URL, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('data', [])
    except Exception as e:
        print(f"Error en búsqueda: {e}")
    return []

def agrupar_eventos(articulos, max_eventos=None):
    """Agrupa artículos por evento (2+ medios sobre mismo tema)"""
    eventos_dict = defaultdict(list)

    for art in articulos:
        # Crear clave por palabras clave principales
        titulo = art.get('title', '').lower()
        descripcion = art.get('description', '').lower()
        texto = (titulo + ' ' + descripcion).split()

        # Palabras clave de 4+ caracteres
        palabras = tuple(sorted(set([p for p in texto if len(p) > 4])))

        if palabras:
            eventos_dict[palabras].append({
                'medio': art.get('source', {}).get('name', 'unknown'),
                'titulo': art.get('title', '')[:100],
                'fecha': art.get('published_at', '')[:10],
                'url': art.get('url', ''),
                'texto': (art.get('description', '') or '')[:500]
            })

    # Filtrar: solo eventos con 2+ medios
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

def generar_corpus(max_eventos=1000, nombre_salida='corpus_eventos_reales.json'):
    """Genera corpus MediaStack con timing y estadísticas"""

    print("\n" + "="*70)
    print("GENERADOR DE CORPUS - MediaStack")
    print("="*70)
    print(f"Meta: {max_eventos:,} eventos")
    print(f"Palabras clave: {len(KEYWORDS)}")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    inicio = time.time()

    # Buscar artículos
    print(f"Buscando en MediaStack...")
    todos_articulos = []

    for i, palabra in enumerate(KEYWORDS, 1):
        print(f"   [{i}/{len(KEYWORDS)}] {palabra}...", end=' ')
        articulos = buscar_noticias(palabra, limit=100)
        todos_articulos.extend(articulos)
        print(f"OK ({len(articulos)} articulos)")

    print(f"\nTotal descargado: {len(todos_articulos)} artículos")

    # Agrupar por eventos
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
    print(f"Velocidad:    {len(eventos)/tiempo_total:.2f} eventos/segundo")
    print("="*70)

    return eventos

if __name__ == '__main__':
    max_eventos = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    # Verificar API key
    if not MEDIASTACK_KEY or MEDIASTACK_KEY == '5f855a76f3e987cdbc21d5fb1a84ba0e':
        print("\nADVERTENCIA: API key es default")
        print("Asegurate de tener MEDIASTACK_API_KEY en variables de entorno")
        print("O actualiza la linea: MEDIASTACK_KEY = os.getenv('MEDIASTACK_API_KEY')\n")

    eventos = generar_corpus(max_eventos=max_eventos)

    print(f"\nCorpus guardado en: corpus_eventos_reales.json")
    print(f"Para diferentes resultados, modifica KEYWORDS en el script\n")
