#!/bin/sh
set -e
# Aplica las migraciones y luego arranca el comando del contenedor (uvicorn).
alembic upgrade head
exec "$@"