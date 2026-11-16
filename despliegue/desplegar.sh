#!/usr/bin/env bash
# Instala y despliega el Asesor Pedagógico Inteligente en un servidor Ubuntu 22.04/24.04 (ARM o x86),
# por ejemplo una máquina "Always Free" de Oracle Cloud. Guía: docs/DESPLIEGUE.md
#
# Uso (dentro del repositorio clonado en el servidor):
#   bash despliegue/desplegar.sh
#
# Es idempotente: la primera vez instala Docker, abre el firewall, crea .env con secretos aleatorios y
# levanta todo; las siguientes veces actualiza el código (git pull) y reconstruye los contenedores.
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE_ARCHIVOS=(-f docker-compose.yml -f docker-compose.prod.yml)

paso() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
aviso() { printf '\033[1;33m%s\033[0m\n' "$*"; }
secreto() { python3 -c 'import secrets; print(secrets.token_urlsafe(48))'; }

if [ "$(id -u)" -eq 0 ]; then
  aviso "Ejecuta este script con tu usuario normal (p. ej. 'ubuntu'), no como root; pedirá sudo cuando haga falta."
  exit 1
fi

# ---------- 1. Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  paso "Instalando Docker desde el repositorio oficial"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl git python3
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  sudo systemctl enable --now docker
fi
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then DOCKER=(sudo docker); fi

# ---------- 2. Firewall del sistema ----------
# Las imágenes Ubuntu de Oracle traen reglas iptables que rechazan todo salvo SSH: se abren 80 y 443.
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
  paso "Abriendo puertos 80 y 443 en ufw"
  sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
elif ! sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null; then
  paso "Abriendo puertos 80 y 443 en iptables"
  sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
  if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save
  else
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
    sudo netfilter-persistent save
  fi
fi

# ---------- 3. Código ----------
if [ -d .git ]; then
  paso "Actualizando el código (git pull)"
  git pull --ff-only || aviso "No se pudo hacer git pull (¿cambios locales?); se despliega el código actual."
fi

# ---------- 4. Configuración (.env) ----------
if [ ! -f .env ]; then
  paso "Creando .env con secretos aleatorios"
  read -rp "Dominio público (p. ej. asesor-ia.duckdns.org): " DOMINIO
  read -rp "Correo del administrador inicial: " ADMIN_CORREO
  read -rsp "ANTHROPIC_API_KEY (Enter para usar el proveedor de demostración): " CLAVE_IA
  echo
  PROVEEDOR=falso
  if [ -n "$CLAVE_IA" ]; then PROVEEDOR=claude; fi
  ADMIN_CONTRASENA="$(python3 -c 'import secrets; print(secrets.token_urlsafe(15))')"
  umask 077
  cat > .env <<EOF
# Generado por despliegue/desplegar.sh el $(date -Iseconds). NO subir al repositorio.
DOMINIO=${DOMINIO}
POSTGRES_DB=asesor
POSTGRES_USER=asesor
POSTGRES_PASSWORD=$(secreto)
SECRET_KEY=$(secreto)
SANDBOX_TOKEN=$(secreto)
CORS_ORIGINS=["https://${DOMINIO}"]

ADMIN_CORREO=${ADMIN_CORREO}
ADMIN_CONTRASENA=${ADMIN_CONTRASENA}

AI_PROVIDER=${PROVEEDOR}
ANTHROPIC_API_KEY=${CLAVE_IA}
IA_MODELO_PRINCIPAL=claude-haiku-5-5
IA_MODELO_ESCALAMIENTO=claude-sonnet-5-5
IA_UMBRAL_CONFIANZA=0.6
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODELO=qwen2.5-coder:7b
OLLAMA_NUM_CTX=16384
EOF
  umask 022
  aviso "Administrador inicial: ${ADMIN_CORREO}"
  aviso "Contraseña inicial:    ${ADMIN_CONTRASENA}"
  aviso "Guárdala ahora en un gestor de contraseñas y cámbiala al entrar; no se volverá a mostrar."
fi
DOMINIO="$(grep -E '^DOMINIO=' .env | cut -d= -f2-)"
if [ -z "$DOMINIO" ]; then
  aviso "Falta DOMINIO en .env"
  exit 1
fi

# ---------- 5. Construir y levantar ----------
paso "Construyendo y levantando los contenedores (la primera vez tarda varios minutos)"
"${DOCKER[@]}" compose "${COMPOSE_ARCHIVOS[@]}" up -d --build --remove-orphans
"${DOCKER[@]}" image prune -f >/dev/null

# ---------- 6. Verificación ----------
paso "Esperando a que https://${DOMINIO} responda (Caddy pide el certificado la primera vez)"
for _ in $(seq 1 60); do
  if curl -fsS "https://${DOMINIO}/api/salud" >/dev/null 2>&1; then
    curl -fsS "https://${DOMINIO}/api/salud"
    echo
    paso "Listo: https://${DOMINIO}"
    exit 0
  fi
  sleep 5
done
aviso "No respondió en 5 minutos. Revisa: el registro DNS de ${DOMINIO} apunta a la IP pública de este servidor,"
aviso "la Security List de Oracle permite 80 y 443, y los registros: docker compose ${COMPOSE_ARCHIVOS[*]} logs caddy api"
exit 1
