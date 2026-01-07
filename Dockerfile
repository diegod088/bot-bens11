FROM python:3.10-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema (ffmpeg es útil para bots de media)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requerimientos e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1

# Exponer puerto por defecto (Railway asignará su propio puerto via variable PORT)
EXPOSE 5000

# Health check para Railway (usa variable de entorno PORT)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando para ejecutar bot + dashboard (usa debug.py para mejores logs en Railway)
CMD ["python", "start_debug.py"]
