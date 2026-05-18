# Despliegue directo a Cloud Run (sin Cloud Build)
# Ejecutar desde la raíz del repo: .\deploy.ps1

$ErrorActionPreference = "Stop"

$PROJECT_ID = "aplicacionagro-461801"
$GCP_ACCOUNT = "jmgalindor9802@gmail.com"
$REGION = "us-central1"
$SERVICE_NAME = "procesador-boletines"
$BQ_TABLE = "aplicacionagro-461801.dataset_corabastos.precios_diarios"
$ALLOWED_BUCKET = "corabastos-boletines-diarios"

$ENV_VARS = "GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,BQ_TABLE=$BQ_TABLE,ALLOWED_BUCKET=$ALLOWED_BUCKET"

$CONFIG_NAME = "aplicacionagro"

$authAccounts = gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>$null
if ($authAccounts -notcontains $GCP_ACCOUNT) {
    Write-Host "La cuenta $GCP_ACCOUNT no está autenticada." -ForegroundColor Yellow
    Write-Host "Ejecuta primero: .\setup-gcloud.ps1" -ForegroundColor Yellow
    exit 1
}

$configExists = gcloud config configurations list --filter="name=$CONFIG_NAME" --format="value(name)" 2>$null
if ($configExists) {
    gcloud config configurations activate $CONFIG_NAME | Out-Null
} else {
    gcloud config set account $GCP_ACCOUNT | Out-Null
    gcloud config set project $PROJECT_ID | Out-Null
}

Write-Host "Cuenta: $GCP_ACCOUNT | Proyecto: $PROJECT_ID" -ForegroundColor Cyan

Write-Host "Desplegando $SERVICE_NAME en $REGION..." -ForegroundColor Cyan
Write-Host "NOTA: --source tarda 10-15 min (build en la nube). Para solo env vars usa: .\deploy-env.ps1" -ForegroundColor Yellow

gcloud run deploy $SERVICE_NAME `
  --source . `
  --account=$GCP_ACCOUNT `
  --project=$PROJECT_ID `
  --region=$REGION `
  --platform=managed `
  --no-allow-unauthenticated `
  --timeout=300 `
  --memory=1Gi `
  --set-env-vars=$ENV_VARS `
  --async

Write-Host ""
Write-Host "Deploy iniciado en segundo plano. Ver progreso:" -ForegroundColor Cyan
Write-Host "  gcloud builds list --project=$PROJECT_ID --ongoing" -ForegroundColor Gray
Write-Host "  gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID" -ForegroundColor Gray
Write-Host ""
Write-Host "Cuando termine, revisa la URL:" -ForegroundColor Cyan

if ($LASTEXITCODE -ne 0) {
    Write-Error "El despliegue falló (exit code $LASTEXITCODE)."
}

Write-Host "Despliegue completado." -ForegroundColor Green
gcloud run services describe $SERVICE_NAME `
  --account=$GCP_ACCOUNT `
  --project=$PROJECT_ID `
  --region=$REGION `
  --format="value(status.url)"
