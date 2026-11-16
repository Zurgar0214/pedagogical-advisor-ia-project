# Imagen de ejecución de pruebas del estudiante (RNF-04). Se lanza SIEMPRE con los flags de
# aislamiento definidos en sandbox/servicio/servidor.py (sin red, solo lectura, límites, usuario sin privilegios).
FROM python:3.13-slim

ENV MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir \
    pytest==8.3.4 \
    numpy==2.2.1 \
    pandas==2.2.3 \
    scikit-learn==1.6.0 \
    matplotlib==3.10.0

COPY ejecutar.py /opt/ejecutar.py

USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "/opt/ejecutar.py"]
# Timeout interno por defecto (segundos); el servicio lo sobrescribe como argumento.
CMD ["45"]
