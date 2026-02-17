FROM python:3.11-slim

# Evita la creación de archivos .pyc y habilita el buffering inmediato de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Puerto por defecto de Cloud Run
ENV PORT=8080
EXPOSE 8080

# Arrancar con gunicorn (1 worker, timeout amplio para esperar a Gemini)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "300", "main:app"]
