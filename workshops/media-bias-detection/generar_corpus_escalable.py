#!/usr/bin/env python3
"""
Script escalable para generar corpus con 1K y 17K eventos
Mide tiempo de ejecución y tamaño de archivo
"""

import requests
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import sys

MEDIASTACK_KEY = '5f855a76f3e987cdbc21d5fb1a84ba0e'
MEDIASTACK_URL = 'https://api.mediastack.com/v1/news'

KEYWORDS = [
    'reforma tributaria',
    'acuerdo paz',
    'reforma pensional',
    'elecciones',
    'gobierno colombia',
    'crisis economia',
    'seguridad colombia',
    'conflicto armado',
    'educacion colombia',
    'salud colombia'
]

def buscar_noticias(palabra, limit=100):
    """Busca en MediaStack"""
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
    except:
        pass
    return []

def agrupar_eventos(articulos, max_eventos=None):
    """Agrupa artículos por evento"""
    eventos_dict = defaultdict(list)

    for art in articulos:
        # Crear clave por palabras clave
        palabras = set()
        titulo = art.get('title', '').lower().split()
        descripcion = art.get('description', '').lower().split()

        palabras = tuple(sorted(set([p for p in titulo + descripcion if len(p) > 4])))

        if palabras:
            eventos_dict[palabras].append({
                'medio': art.get('source', 'unknown'),
                'titulo': art.get('title', '')[:100],
                'fecha': art.get('published_at', '')[:10],
                'url': art.get('url', ''),
                'texto': (art.get('description', '') + ' ' + art.get('content', ''))[:500]
            })

    # Filtrar eventos con 2+ medios
    eventos = []
    for i, (palabras, grupo) in enumerate(eventos_dict.items(), 1):
        if len(grupo) >= 2:
            eventos.append({
                'evento_id': f'evento-{i:06d}',
                'fecha': grupo[0]['fecha'],
                'titulo': grupo[0]['titulo'],
                'articulos': grupo
            })

        if max_eventos and len(eventos) >= max_eventos:
            break

    return eventos

def generar_corpus(max_eventos=1000, nombre_salida='corpus_eventos_reales.json'):
    """Genera corpus con timing"""
    print(f"\n{'='*80}")
    print(f"🚀 GENERANDO CORPUS: {max_eventos} eventos")
    print(f"{'='*80}\n")

    inicio = time.time()

    # Buscar
    print(f"📡 Buscando en MediaStack ({len(KEYWORDS)} palabras clave)...")
    todos_articulos = []

    for palabra in KEYWORDS:
        print(f"   • {palabra}...", end=' ')
        articulos = buscar_noticias(palabra, limit=100)
        todos_articulos.extend(articulos)
        print(f"✅ {len(articulos)} artículos")

    # Agrupar
    print(f"\n🔗 Agrupando por eventos...")
    eventos = agrupar_eventos(todos_articulos, max_eventos=max_eventos)

    # Guardar
    print(f"\n💾 Guardando {len(eventos)} eventos...")
    with open(nombre_salida, 'w', encoding='utf-8') as f:
        json.dump(eventos, f, indent=2, ensure_ascii=False)

    # Estadísticas
    tiempo_total = time.time() - inicio
    tamaño_mb = Path(nombre_salida).stat().st_size / (1024 * 1024)

    print(f"\n{'='*80}")
    print(f"✅ COMPLETADO")
    print(f"{'='*80}")
    print(f"⏱️  Tiempo: {tiempo_total:.2f} segundos ({tiempo_total/60:.2f} minutos)")
    print(f"📁 Archivo: {nombre_salida}")
    print(f"📊 Eventos: {len(eventos)}")
    print(f"📄 Tamaño: {tamaño_mb:.2f} MB")
    print(f"📈 Velocidad: {len(eventos)/tiempo_total:.0f} eventos/segundo")

    return tiempo_total, tamaño_mb, len(eventos)

if __name__ == '__main__':
    max_eventos = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    print(f"\n🧪 TEST DE ESCALABILIDAD")
    print(f"   Meta: {max_eventos:,} eventos")
    print(f"   Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tiempo, tamaño, eventos = generar_corpus(max_eventos)

    print(f"\n💡 Para 17K eventos:")
    tiempo_estimado_17k = tiempo * (17000 / max_eventos)
    print(f"   ⏱️  Tiempo estimado: {tiempo_estimado_17k/60:.1f} minutos")
    print(f"   📁 Tamaño estimado: {tamaño * (17000 / max_eventos):.1f} MB")
