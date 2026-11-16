#!/usr/bin/env bash
# Reintenta crear la VM ARM "Always Free" (VM.Standard.A1.Flex) hasta que Oracle tenga capacidad.
# Se ejecuta en Oracle Cloud Shell (ícono >_ arriba a la derecha de la consola), que ya trae la CLI autenticada.
#
# Requisitos: una VCN con subred pública (Networking → Virtual Cloud Networks → Start VCN Wizard →
# "Create VCN with Internet Connectivity") y tu clave SSH pública.
#
# Uso:   bash oracle_crear_vm.sh "ssh-ed25519 AAAA... tu-clave-publica"
# Opcional: OCPUS=2 MEM=12 ESPERA=90 bash oracle_crear_vm.sh "..."
set -uo pipefail

CLAVE_PUB="${1:?Uso: bash oracle_crear_vm.sh \"ssh-ed25519 AAAA... (tu clave pública)\"}"
OCPUS="${OCPUS:-1}"
MEM="${MEM:-6}"
ESPERA="${ESPERA:-90}"
COMP="${OCI_TENANCY:?Ejecuta este script en Oracle Cloud Shell}"   # compartimento raíz

echo "Buscando datos de la cuenta..."
AD=$(oci iam availability-domain list -c "$COMP" --query 'data[0].name' --raw-output)
IMAGEN=$(oci compute image list -c "$COMP" --operating-system "Canonical Ubuntu" \
  --operating-system-version "24.04" --shape VM.Standard.A1.Flex \
  --sort-by TIMECREATED --sort-order DESC --query 'data[0].id' --raw-output)
SUBRED=$(oci network subnet list -c "$COMP" \
  --query 'data[?"prohibit-public-ip-on-vnic" == `false`].id | [0]' --raw-output)

if [ -z "$SUBRED" ] || [ "$SUBRED" = "null" ]; then
  echo "No hay una subred pública. Crea la VCN con el asistente (ver encabezado) y vuelve a ejecutar."
  exit 1
fi
echo "AD: $AD"
echo "Imagen: $IMAGEN"
echo "Subred: $SUBRED"
echo "Forma: VM.Standard.A1.Flex con $OCPUS OCPU y $MEM GB. Reintento cada ${ESPERA}s (Ctrl+C para parar)."

printf '%s\n' "$CLAVE_PUB" > /tmp/clave_asesor.pub
n=0
while true; do
  n=$((n + 1))
  salida=$(oci compute instance launch -c "$COMP" --availability-domain "$AD" \
    --shape VM.Standard.A1.Flex --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEM}" \
    --image-id "$IMAGEN" --subnet-id "$SUBRED" --assign-public-ip true \
    --display-name asesor-ia --ssh-authorized-keys-file /tmp/clave_asesor.pub \
    --wait-for-state RUNNING --max-wait-seconds 600 2>&1)
  if printf '%s' "$salida" | grep -q '"lifecycle-state": "RUNNING"'; then
    ID=$(printf '%s' "$salida" | grep -m1 '"id": "ocid1.instance' | cut -d'"' -f4)
    IP=$(oci compute instance list-vnics --instance-id "$ID" --query 'data[0]."public-ip"' --raw-output)
    echo
    echo "¡Máquina creada en el intento $n!"
    echo "IP pública: $IP"
    echo "Entra con:  ssh -i <tu-clave-privada> ubuntu@$IP"
    exit 0
  elif printf '%s' "$salida" | grep -qi "capacity"; then
    echo "$(date +%H:%M:%S) intento $n: sin capacidad todavía"
  elif printf '%s' "$salida" | grep -qi "TooManyRequests"; then
    echo "$(date +%H:%M:%S) intento $n: Oracle pide bajar el ritmo; espero 3 minutos"
    sleep 180
  else
    echo "Error distinto a falta de capacidad; se detiene para no insistir a ciegas:"
    printf '%s\n' "$salida" | tail -20
    exit 1
  fi
  sleep "$ESPERA"
done
