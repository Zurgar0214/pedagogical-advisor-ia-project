#!/usr/bin/env bash
# Respaldo de la base de datos y de las evidencias subidas. Conserva los 7 más recientes.
# Uso manual:  bash despliegue/respaldar.sh
# Diario (cron, 3:00 a. m.):  crontab -e  →  0 3 * * * cd /home/ubuntu/asesor && bash despliegue/respaldar.sh
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
if ! docker info >/dev/null 2>&1; then COMPOSE=(sudo "${COMPOSE[@]}"); fi

DESTINO="respaldos"
FECHA="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DESTINO"
chmod 700 "$DESTINO"

# Base de datos (formato SQL comprimido)
"${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' \
  | gzip > "$DESTINO/bd-$FECHA.sql.gz"

# Evidencias de los estudiantes (volumen storage de la API)
"${COMPOSE[@]}" exec -T api tar czf - -C /app storage > "$DESTINO/evidencias-$FECHA.tar.gz"

# Rotación: deja los 7 últimos de cada tipo
for tipo in bd evidencias; do
  ls -1t "$DESTINO"/"$tipo"-* 2>/dev/null | tail -n +8 | xargs -r rm -f
done

echo "Respaldo creado en $DESTINO/: bd-$FECHA.sql.gz y evidencias-$FECHA.tar.gz"
