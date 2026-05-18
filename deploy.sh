#!/usr/bin/env bash
# Despliegue directo a Cloud Run (sin Cloud Build)
# Ejecutar desde la raíz del repo: ./deploy.sh

set -euo pipefail

PROJECT_ID="aplicacionagro-461801"
GCP_ACCOUNT="jmgalindor9802@gmail.com"
REGION="us-central1"
SERVICE_NAME="procesador-boletines"
BQ_TABLE="aplicacionagro-461801.dataset_corabastos.precios_diarios"
ALLOWED_BUCKET="corabastos-boletines-diarios"

ENV_VARS="GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION},BQ_TABLE=${BQ_TABLE},ALLOWED_BUCKET=${ALLOWED_BUCKET}"

echo "Cuenta: ${GCP_ACCOUNT} | Proyecto: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --account="${GCP_ACCOUNT}" 2>/dev/null || true
gcloud config set account "${GCP_ACCOUNT}" 2>/dev/null || true

echo "Desplegando ${SERVICE_NAME} en ${REGION}..."

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --account="${GCP_ACCOUNT}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --platform=managed \
  --no-allow-unauthenticated \
  --timeout=300 \
  --memory=1Gi \
  --set-env-vars="${ENV_VARS}"

echo "Despliegue completado."
gcloud run services describe "${SERVICE_NAME}" \
  --account="${GCP_ACCOUNT}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)"
