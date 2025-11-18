FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema para tabula-py (Java)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre fontconfig fonts-dejavu fonts-liberation && rm -rf /var/lib/apt/lists/*

ENV PDFBOX_FONTCACHE=/var/cache/pdfbox
ENV JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8 -Dorg.slf4j.simpleLogger.defaultLogLevel=error -Dpdfbox.fontcache=/var/cache/pdfbox -Dorg.slf4j.simpleLogger.log.org.apache.pdfbox=error"

RUN mkdir -p /var/cache/pdfbox && chmod 777 /var/cache/pdfbox

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/

# Exponer el puerto
EXPOSE 8500

# Usar gunicorn para producción es más robusto

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "--timeout", "300", "-b", "0.0.0.0:8500", "app.main:app"]
