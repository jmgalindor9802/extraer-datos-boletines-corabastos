# Configuración única de gcloud para este proyecto (cuenta + proyecto)
# Ejecutar: .\setup-gcloud.ps1

$ErrorActionPreference = "Stop"

$CONFIG_NAME = "aplicacionagro"
$GCP_ACCOUNT = "jmgalindor9802@gmail.com"
$PROJECT_ID = "aplicacionagro-461801"
$REGION = "us-central1"

Write-Host "Iniciando sesión con $GCP_ACCOUNT (se abrirá el navegador)..." -ForegroundColor Cyan
gcloud auth login $GCP_ACCOUNT

$exists = gcloud config configurations list --filter="name=$CONFIG_NAME" --format="value(name)" 2>$null
if (-not $exists) {
    gcloud config configurations create $CONFIG_NAME
}

gcloud config configurations activate $CONFIG_NAME
gcloud config set account $GCP_ACCOUNT
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

Write-Host ""
Write-Host "Configuración '$CONFIG_NAME' activa:" -ForegroundColor Green
gcloud config list

Write-Host ""
Write-Host "Ahora puedes desplegar con: .\deploy.ps1" -ForegroundColor Green
