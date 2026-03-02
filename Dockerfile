FROM python:3.10-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
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

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Exponer puerto
EXPOSE 8080

# Comando para ejecutar bot + dashboard
CMD ["python", "railway_start.py"]
