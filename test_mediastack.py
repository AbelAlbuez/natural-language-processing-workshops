#!/usr/bin/env python3
"""
Script simple para probar MediaStack API
Busca noticias de Colombia y los 3 outlets principales
"""

import requests
import json
from datetime import datetime, timedelta

# API Key
MEDIASTACK_KEY = '5f855a76f3e987cdbc21d5fb1a84ba0e'
MEDIASTACK_URL = 'https://api.mediastack.com/v1/news'

# Palabras clave colombianas
KEYWORDS = [
    'reforma tributaria',
    'acuerdo paz',
    'reforma pensional',
    'elecciones',
    'gobierno colombia'
]

# Outlets objetivo
OUTLETS = ['el tiempo', 'caracol', 'blu radio']

print("=" * 80)
print("🧪 TEST MEDIASTACK API - NOTICIAS COLOMBIA")
print("=" * 80)
print(f"\nAPI Key: {MEDIASTACK_KEY[:20]}...")
print(f"Endpoints: {MEDIASTACK_URL}")
print(f"Palabras clave: {len(KEYWORDS)}")
print(f"Outlets: {', '.join(OUTLETS)}")

# Test 1: Conexión básica
print("\n" + "-" * 80)
print("TEST 1: Conexión básica")
print("-" * 80)

try:
    params = {
        'access_key': MEDIASTACK_KEY,
        'keywords': 'test',
        'limit': 1
    }

    response = requests.get(MEDIASTACK_URL, params=params, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            print("✅ API funciona - Retorna datos")
        elif 'error' in data:
            print(f"❌ Error de API: {data['error']['info']}")
        else:
            print(f"⚠️  Respuesta inesperada: {list(data.keys())}")
    else:
        print(f"❌ HTTP {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Buscar noticias de Colombia
print("\n" + "-" * 80)
print("TEST 2: Buscar noticias - Palabra clave 1")
print("-" * 80)

try:
    params = {
        'access_key': MEDIASTACK_KEY,
        'keywords': KEYWORDS[0],  # 'reforma tributaria'
        'countries': 'co',
        'limit': 10,
        'sort': 'published_desc',
        'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    }

    print(f"Búsqueda: '{KEYWORDS[0]}' en Colombia (últimos 30 días)")

    response = requests.get(MEDIASTACK_URL, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        articulos = data.get('data', [])

        print(f"✅ {len(articulos)} artículos encontrados")

        # Filtrar por outlets
        articulos_outlets = []
        for art in articulos:
            source = art.get('source', '').lower()
            for outlet in OUTLETS:
                if outlet in source:
                    articulos_outlets.append({
                        'outlet': outlet.upper(),
                        'titulo': art.get('title', '')[:70],
                        'fecha': art.get('published_at', '')[:10]
                    })
                    break

        if articulos_outlets:
            print(f"\n   Filtrados por outlets: {len(articulos_outlets)}")
            for art in articulos_outlets[:5]:
                print(f"   • [{art['outlet']}] {art['titulo']}")
                print(f"     📅 {art['fecha']}")
        else:
            print(f"   ❌ Ninguno de los outlets encontrados")
            print(f"   Fuentes en respuesta:")
            sources = set()
            for art in articulos[:5]:
                src = art.get('source', 'unknown')
                sources.add(src)
            for src in sources:
                print(f"      - {src}")
    else:
        print(f"❌ HTTP {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Búsqueda múltiple
print("\n" + "-" * 80)
print("TEST 3: Búsqueda múltiple")
print("-" * 80)

total_articulos = 0
total_outlets = 0

for palabra in KEYWORDS[:3]:  # Primeras 3 palabras
    try:
        params = {
            'access_key': MEDIASTACK_KEY,
            'keywords': palabra,
            'countries': 'co',
            'limit': 20,
            'sort': 'published_desc'
        }

        response = requests.get(MEDIASTACK_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            articulos = data.get('data', [])
            total_articulos += len(articulos)

            # Contar outlets
            outlets_encontrados = set()
            for art in articulos:
                source = art.get('source', '').lower()
                for outlet in OUTLETS:
                    if outlet in source:
                        outlets_encontrados.add(outlet)

            total_outlets += len(outlets_encontrados)

            print(f"'{palabra}': {len(articulos)} arts, {len(outlets_encontrados)} outlets")
    except:
        pass

print("\n" + "=" * 80)
print("📊 RESUMEN FINAL")
print("=" * 80)

if total_articulos > 0:
    print(f"""
✅ MEDIASTACK FUNCIONA
   • Total artículos: {total_articulos}
   • Outlets encontrados: {total_outlets}

SIGUIENTE:
   1. Ejecuta este script en Google Colab
   2. Si retorna >0 artículos → corpus automático
   3. Si falla → descarga manual (10 min)
""")
else:
    print(f"""
❌ MEDIASTACK NO RETORNA ARTÍCULOS
   (Puede ser: API key inválida, sin cobertura CO, o bloqueado)

ALTERNATIVA:
   1. Usa RSS feeds (El Tiempo + El Espectador)
   2. O descarga manual (10 min)
   3. Copia 10 artículos x outlet
   4. Guarda en corpus_eventos_reales.json
""")
