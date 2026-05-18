# Actualiza solo variables de entorno (~1 min, sin reconstruir imagen)
# Uso: .\deploy-env.ps1

$ErrorActionPreference = "Stop"

$PROJECT_ID = "aplicacionagro-461801"
$GCP_ACCOUNT = "jmgalindor9802@gmail.com"
$REGION = "us-central1"
$SERVICE_NAME = "procesador-boletines"
$ENV_VARS = "GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,BQ_TABLE=aplicacionagro-461801.dataset_corabastos.precios_diarios,ALLOWED_BUCKET=corabastos-boletines-diarios"

Write-Host "Actualizando env vars de $SERVICE_NAME (sin rebuild)..." -ForegroundColor Cyan

gcloud run services update $SERVICE_NAME `
  --account=$GCP_ACCOUNT `
  --project=$PROJECT_ID `
  --region=$REGION `
  --set-env-vars=$ENV_VARS

Write-Host "Listo." -ForegroundColor Green
