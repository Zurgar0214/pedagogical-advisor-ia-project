# Servicio orquestador de la sandbox: CLI de Docker + Python (solo biblioteca estándar).
FROM docker:27-cli

RUN apk add --no-cache python3

COPY servidor.py /app/servidor.py

EXPOSE 8100
ENTRYPOINT ["python3", "/app/servidor.py"]
