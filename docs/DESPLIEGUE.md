# Despliegue en Oracle Cloud "Always Free" (RNF-06)

Resultado: la plataforma completa (PostgreSQL, API, frontend y **sandbox con Docker**) publicada en
`https://<tu-subdominio>.duckdns.org`, con HTTPS automático y sin costo.

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

**Respaldo diario** a las 3:00 a. m. Abre el cron con `crontab -e` y añade esta línea:

```
0 3 * * * cd /home/ubuntu/asesor && bash despliegue/respaldar.sh >> respaldos.log 2>&1
```

Los respaldos quedan en `~/asesor/respaldos/`. Para llevarlos a tu PC:

```bash
scp -i .\ssh-key-asesor.key -r ubuntu@<IP_PUBLICA>:asesor/respaldos .
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
