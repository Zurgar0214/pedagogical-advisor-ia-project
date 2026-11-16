# Despliegue (RNF-06)

**Producción actual:** <https://asesor-ia-jvaron.northcentralus.cloudapp.azure.com>. Corre en Azure for Students:
una máquina Standard_B2als_v2 (2 vCPU, 4 GiB, Ubuntu 24.04) en North Central US, por unos 0,0376 USD/h que salen del
crédito de estudiante.

La plataforma completa (PostgreSQL, API, frontend y **sandbox con Docker**) se publica con HTTPS automático.
Los mismos archivos sirven en cualquier servidor Ubuntu con Docker; abajo están los pasos para **Azure for Students**
(lo que se usó) y para **Oracle Cloud Always Free** (alternativa gratuita que no tuvo capacidad ARM en Bogotá).

```
Internet ──443/80──► Caddy (HTTPS) ──► nginx (frontend + /api) ──► API FastAPI ──► PostgreSQL
                                                                      │
                                                                      └──► sandbox ──► docker run aislado (sin red)
```

Solo Caddy publica puertos. La base de datos, la API, nginx y la sandbox quedan en la red interna de Docker.

Archivos que intervienen:

| Archivo | Para qué |
|---------|----------|
| `docker-compose.prod.yml` | Se suma al `docker-compose.yml`: añade Caddy, cierra el puerto de nginx y rota registros |
| `despliegue/Caddyfile` | HTTPS con Let's Encrypt, cabeceras de seguridad y límite de 50 MB por petición |
| `despliegue/desplegar.sh` | Instala Docker, abre el firewall, crea `.env` con secretos aleatorios, levanta todo y verifica. Se vuelve a ejecutar para actualizar |
| `despliegue/respaldar.sh` | Respaldo de la base de datos y de las evidencias (guarda los 7 últimos) |

Tiempo estimado: 30–45 minutos la primera vez.

> Las pantallas de Oracle cambian a menudo; los nombres de menús pueden variar un poco.

---

## A. Azure for Students (lo que se usó)

1. En <https://portal.azure.com>, con el correo de la universidad: **Microsoft Azure for Students → Inicio**. Se
   comprueba el crédito en **Education → Información general**: 100 USD por 12 meses y sin tarjeta.
2. **Elegir región y tamaño permitidos.** Las suscripciones de estudiante bloquean muchos tamaños por región
   (`NotAvailableForSubscription`). Para ver cuáles sirven, se abre Cloud Shell (`>_`, Bash) y se ejecuta:

   ```bash
   for r in eastus2 centralus southcentralus westus3 eastus northcentralus canadacentral brazilsouth mexicocentral; do echo "== $r"; az vm list-skus -l $r --resource-type virtualMachines --query "[?length(restrictions[?type=='Location'])==\`0\`].name" -o tsv | grep -E '^Standard_(B2s|B2ms|B1ms|B2als_v2|B2as_v2|B2ats_v2|D2als_v6|F2als_v6)$'; done
   ```

   En noviembre de 2026 solo **North Central US** ofrecía la serie B (B2als_v2: 4 GiB, unos 27 USD/mes). Las demás
   regiones solo tenían D/F v6, que cuestan el doble.
3. **Máquinas virtuales → Crear:**

   | Campo | Valor |
   |-------|-------|
   | Grupo de recursos | `asesor-rg` (nuevo) |
   | Nombre | `asesor-ia` |
   | Región | North Central US |
   | Imagen | Ubuntu Server 24.04 LTS – x64 Gen2 |
   | Tamaño | Standard_B2als_v2 |
   | Autenticación | Clave SSH, usuario `azureuser`, generar par de claves |
   | Puertos de entrada | 22, 80, 443 |
   | Disco | SSD estándar |
   | Redes | Eliminar IP pública y NIC con la VM |
   | Apagado automático | Desactivado |

4. Se descarga `asesor-ia_key.pem` y se guarda **fuera de OneDrive** (`~\.ssh\`), con permisos solo para el usuario
   (`icacls <ruta> /inheritance:r /grant:r "%USERNAME%:(R)"`).
5. **IP pública → Configuración → Etiqueta de nombre DNS:** `asesor-ia-jvaron`. Así se obtiene
   `asesor-ia-jvaron.northcentralus.cloudapp.azure.com` gratis, sin DuckDNS.
6. Se instala y despliega con un solo comando desde el PC:

   ```bash
   ssh -t -i ~/.ssh/asesor-ia_key.pem azureuser@asesor-ia-jvaron.northcentralus.cloudapp.azure.com "git clone https://github.com/Zurgar0214/pedagogical-advisor-ia-project.git asesor && cd asesor && bash despliegue/desplegar.sh"
   ```

   El script pide el dominio, el correo del administrador y la clave de Anthropic (opcional), y muestra una sola vez
   la contraseña del administrador.

**Ahorro de crédito:** al **detener** la máquina desde el portal (estado *Desasignada*) no se cobra el cómputo, solo
el disco y la IP (unos 6 USD/mes). Para la revisión se pulsa *Iniciar* y los contenedores arrancan solos
(`restart: unless-stopped`).

**Verificación hecha el 2026-11-16:**
- `/api/salud` responde.
- Certificado de Let's Encrypt válido.
- HTTP redirige a HTTPS con 308.
- Las cabeceras de seguridad están presentes.
- Los puertos 5432, 8000, 8080, 8100 y 11434 están cerrados desde internet.
- Sandbox ejecutada en el servidor: 3 pruebas, 1 pasa, 2 fallan; una de ellas por `Network is unreachable`.
- No quedan contenedores huérfanos.

---

## B. Alternativa: Oracle Cloud "Always Free"

Gratis de forma indefinida (ARM, hasta 4 OCPU y 24 GB), pero suele responder *Out of host capacity*. Para reintentar
automáticamente desde Cloud Shell de Oracle está `despliegue/oracle_crear_vm.sh`.

## 1. Crear la cuenta de Oracle Cloud

1. Entra a <https://www.oracle.com/cloud/free/> y pulsa **Start for free**.
2. **Home Region:** elige una cercana y con capacidad, como **Brazil East (São Paulo)** o **Colombia Central (Bogotá)** si aparece. **No se puede cambiar después.**
3. Oracle pide una tarjeta solo para verificar identidad. No cobra mientras uses recursos marcados como *Always Free*.
4. Espera el correo de bienvenida; la cuenta puede tardar unos minutos en activarse.

## 2. Crear la máquina virtual

1. Menú ☰ → **Compute → Instances → Create instance**.
2. **Name:** `asesor-ia`.
3. **Image and shape → Edit:**
   - **Image:** *Canonical Ubuntu 24.04*. Elige la variante para **aarch64**; suele seleccionarse sola al elegir la forma ARM.
   - **Shape:** *Ampere* → **VM.Standard.A1.Flex** con **2 OCPU y 12 GB de RAM**. Es suficiente y deja margen gratuito para otra máquina; el máximo gratuito es 4 OCPU y 24 GB.
4. **Networking:** deja que cree una VCN nueva con subred pública y marca **Assign a public IPv4 address**.
5. **Add SSH keys:** elige **Generate a key pair for me** y **descarga la clave privada** (`.key`). Sin ella no podrás entrar.
6. **Boot volume:** el tamaño por defecto (unos 47 GB) es suficiente.
7. Pulsa **Create**. Cuando el estado pase a **Running**, copia la **Public IP address**.

**Si aparece "Out of host capacity":** no hay máquinas ARM libres en ese momento. Prueba otro *Availability Domain* (AD-1, AD-2, AD-3), vuelve a intentarlo en otra hora, o convierte la cuenta a *Pay As You Go*. Esta última opción mantiene gratis lo que sea *Always Free* y da prioridad, pero no crees recursos sin la etiqueta *Always Free*.

## 3. Abrir los puertos 80 y 443 en Oracle

1. En la instancia, entra al enlace de la **Subnet** → **Security Lists** → *Default Security List*.
2. **Add Ingress Rules**, una por puerto:

   | Source CIDR | IP Protocol | Destination Port |
   |-------------|-------------|------------------|
   | `0.0.0.0/0` | TCP | `80` |
   | `0.0.0.0/0` | TCP | `443` |

El firewall interno de Ubuntu (iptables) lo abre el script en el paso 6.

## 4. Subdominio gratuito con DuckDNS

1. Entra a <https://www.duckdns.org> e inicia sesión con Google o GitHub.
2. Crea un subdominio, por ejemplo `asesor-ia`, que queda como `asesor-ia.duckdns.org`.
3. En **current ip** pega la **IP pública** de la máquina y pulsa **update ip**.
4. Comprueba desde tu PC que resuelve: `nslookup asesor-ia.duckdns.org` debe devolver esa IP.

## 5. Entrar al servidor por SSH

En Windows, desde PowerShell, en la carpeta donde descargaste la clave:

```bash
ssh -i .\ssh-key-asesor.key ubuntu@<IP_PUBLICA>
```

Si Windows dice que la clave es "demasiado abierta", restringe sus permisos a tu usuario en
Propiedades → Seguridad → Avanzado → Deshabilitar herencia, dejando solo tu usuario.

## 6. Instalar y desplegar

Ya dentro del servidor:

```bash
git clone https://github.com/Zurgar0214/pedagogical-advisor-ia-project.git asesor
```

```bash
cd asesor && bash despliegue/desplegar.sh
```

El script pregunta tres cosas:

- **Dominio:** por ejemplo `asesor-ia.duckdns.org`.
- **Correo del administrador inicial.**
- **ANTHROPIC_API_KEY:** opcional, y no se muestra mientras la escribes. Si la dejas vacía, se usa el proveedor de demostración (`falso`).

Después, el script:

1. Instala Docker desde el repositorio oficial.
2. Abre los puertos 80 y 443 en iptables.
3. Crea `.env` con secretos aleatorios (permisos `600`).
4. Construye las imágenes; la primera vez tarda entre 10 y 15 minutos en ARM.
5. Espera a que `https://<dominio>/api/salud` responda.

Al final **muestra una sola vez la contraseña del administrador**: guárdala y cámbiala al entrar.

## 7. Verificar

1. Abre `https://<dominio>`: debe cargar con candado.
2. Inicia sesión como administrador y crea un docente y un estudiante.
3. Como docente, crea un laboratorio con su rúbrica (o impórtala con IA).
4. Como estudiante, sube un PDF y un ZIP que incluya un `test_*.py`.
5. Como docente, evalúa la entrega. En el detalle deben aparecer las **pruebas ejecutadas en la sandbox**.

## Operación

**Actualizar** a la última versión de `main` (hace `git pull`, reconstruye y verifica):

```bash
cd ~/asesor && bash despliegue/desplegar.sh
```

**Ver registros:**

```bash
cd ~/asesor && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100 api caddy
```

**Respaldo diario** a las 3:00 a. m. (`<usuario>` es `azureuser` en Azure y `ubuntu` en Oracle). Abre el cron con `crontab -e` y añade esta línea:

```
0 3 * * * cd /home/<usuario>/asesor && bash despliegue/respaldar.sh >> respaldos.log 2>&1
```

Los respaldos quedan en `~/asesor/respaldos/`. Para llevarlos a tu PC:

```bash
scp -i .\ssh-key-asesor.key -r ubuntu@<IP_PUBLICA>:asesor/respaldos .
```

**Datos de demostración (sustentación):** en producción existen un docente (`docente.demo@asesor.local`) y un
estudiante (`estudiante.demo@asesor.local`) con 6 laboratorios (3 por cohorte) evaluados y publicados, un ajuste docente
en C2-LAB01, pruebas ejecutadas en la sandbox (C1-LAB01: 2 de 2 pasan; C2-LAB01: 1 de 3 falla) y un informe integral
con su mapa mental. Las contraseñas se generaron al azar y están solo en el servidor:

```bash
cat ~/credenciales_demo.json
```

**Cambiar el proveedor de IA:** edita `~/asesor/.env` (`AI_PROVIDER`, `ANTHROPIC_API_KEY`) y vuelve a ejecutar `desplegar.sh`.

## Opcional: Ollama en el mismo servidor (sin costo, lento)

Con 4 OCPU y 24 GB, `qwen2.5-coder:7b` corre en CPU. Una evaluación tarda varios minutos; sirve para
demostrar el modo local, no para uso diario.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

```bash
sudo systemctl edit ollama
```

En el editor que se abre, añade estas dos líneas para que el contenedor de la API lo alcance por la red de Docker:

```
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

```bash
sudo systemctl restart ollama && ollama pull qwen2.5-coder:7b
```

Permite que **solo las redes internas de Docker** lleguen a Ollama. Las reglas de iptables de Oracle lo bloquean por defecto:

```bash
sudo iptables -I INPUT 1 -s 172.16.0.0/12 -p tcp --dport 11434 -j ACCEPT && sudo netfilter-persistent save
```

Luego, en `.env`: `AI_PROVIDER=ollama` e `IA_MAX_CARACTERES_CONTEXTO=40000`. Vuelve a ejecutar `desplegar.sh`.
El puerto 11434 **no** se abre en la Security List ni a internet, así que Ollama no queda expuesto.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| El navegador no conecta | Falta la regla 80/443 en la Security List | Paso 3 |
| `desplegar.sh` espera 5 minutos y falla | DuckDNS no apunta a la IP, o el puerto 80 está cerrado (Let's Encrypt lo necesita) | Revisa `nslookup` y los registros de `caddy` |
| `Configuración insegura: SECRET_KEY…` en los registros de `api` | `.env` con secretos de ejemplo | Borra `.env` y vuelve a ejecutar el script, o pon valores de 32 o más caracteres |
| Las pruebas dicen "La sandbox de ejecución no está configurada" | Falta `SANDBOX_TOKEN` o el servicio `sandbox` no está arriba | `docker compose … ps` y registros de `sandbox` |
| `permission denied … docker.sock` | Tu usuario aún no está en el grupo `docker` | Cierra la sesión SSH y vuelve a entrar (el script usa `sudo` mientras tanto) |
| Oracle detuvo la máquina | Recuperación de instancias gratuitas inactivas | Iníciala desde la consola; el respaldo diario evita perder datos |
