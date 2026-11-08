# armar_entregable.ps1
# Crea la carpeta "entregable" (hermana de "proyecto") a partir de TU proyecto actual + los aportes de repo_aportes.zip.
# Ejecutar DENTRO de workshops\taller-rag\proyecto:   powershell -ExecutionPolicy Bypass -File .\armar_entregable.ps1
param(
  [string]$Destino = "..\entregable",
  [string]$Aportes = "$env:USERPROFILE\Downloads\repo_aportes"
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\docker-compose.yml")) { throw "Ejecuta este script dentro de la carpeta proyecto (donde esta docker-compose.yml)." }
if (-not (Test-Path "$Aportes\app\solr_backend.py")) { throw "No encuentro los aportes en $Aportes. Descomprime repo_aportes.zip alli." }

Write-Host "1/5 Copiando tu proyecto actual a $Destino (sin .env, parquet, zip ni caches)..."
robocopy . $Destino /E /XD __pycache__ .git .pytest_cache .venv node_modules /XF .env *.parquet *.zip *.bak /NFL /NDL /NJH /NJS /NP | Out-Null

Write-Host "2/5 Superponiendo los aportes (API con Solr, indexadores, evaluadores, gold, docs, tests, reports)..."
Copy-Item "$Aportes\*" $Destino -Recurse -Force

Write-Host "3/5 Moviendo los resultados crudos de data\ a reports\crudos\ ..."
New-Item -ItemType Directory -Force "$Destino\reports\crudos" | Out-Null
Get-ChildItem .\data -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^(evaluacion_|exp_)' -and $_.Extension -in '.json','.jsonl' } |
  ForEach-Object { Copy-Item $_.FullName "$Destino\reports\crudos" -Force; Remove-Item "$Destino\data\$($_.Name)" -Force -ErrorAction SilentlyContinue }
if (Test-Path ".\reports\demo_trazas.md") { Copy-Item ".\reports\demo_trazas.md" "$Destino\reports" -Force }
foreach ($f in "comparacion_milvus_solr.md","comparacion_milvus_solr.tex") { if (Test-Path ".\reports\$f") { Copy-Item ".\reports\$f" "$Destino\reports" -Force } }

Write-Host "4/5 Asegurando que no se suban datos restringidos ni secretos (.gitignore)..."
$gi = "$Destino\.gitignore"
$lineas = @(".env", "data/*.parquet", "data/chunks_*", "data/embeddings_*", "reports/rag_runs.jsonl", "__pycache__/", "*.pyc")
if (-not (Test-Path $gi)) { New-Item -ItemType File $gi | Out-Null }
$actual = Get-Content $gi -ErrorAction SilentlyContinue
foreach ($l in $lineas) { if ($actual -notcontains $l) { Add-Content $gi $l } }

Write-Host "5/5 Verificando que esta lo imprescindible..."
$necesarios = @(
  "docker-compose.yml", "Dockerfile", ".env.example", "ENTREGABLE.md", "README.md",
  "app\api.py", "app\rag.py", "app\solr_backend.py", "app\milvus_schema.py",
  "scripts\ingest_milvus.py", "scripts\ingest_solr.py", "scripts\ejecutar_experimento_robusto.py", "scripts\demo_rag.py", "scripts\comparar_backends.py",
  "data\ingest_gold.py", "data\evaluar_gold.py", "data\gold\gold.jsonl", "data\gold\queries.csv", "docs\gold_standard.csv",
  "docs\EJECUCION.md", "docs\SOLR.md", "reports\RESULTADOS.md", "reports\informe_evaluacion_rag.pdf", "tests\test_solr_backend.py"
)
$faltan = @()
foreach ($n in $necesarios) { if (-not (Test-Path "$Destino\$n")) { $faltan += $n } }
if ($faltan.Count -eq 0) { Write-Host "OK: no falta nada." -ForegroundColor Green }
else { Write-Host "FALTAN:" -ForegroundColor Yellow; $faltan | ForEach-Object { Write-Host "  $_" } }
if (-not (Select-String -Path "$Destino\docker-compose.yml" -Pattern "solr" -Quiet)) {
  Write-Host "AVISO: docker-compose.yml todavia NO incluye Solr. Reemplazalo por la version integrada (ver instrucciones)." -ForegroundColor Yellow
}
Write-Host "Carpeta lista en: $((Resolve-Path $Destino).Path)"
