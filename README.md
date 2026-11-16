# Asesor Pedagógico Inteligente

Proyecto final de Inteligencia Artificial, Universidad de Manizales. Autor: **Juan Diego Varón Valencia**.

**URL pública:** <https://asesor-ia-jvaron.northcentralus.cloudapp.azure.com>

La plataforma recibe los laboratorios de un estudiante (cohortes 1 y 2), los evalúa con IA contra su rúbrica y calcula
la nota de 0,0 a 5,0 **en el backend**. Con eso genera un informe integral y un mapa mental interactivo de
competencias. Nada llega al estudiante sin revisión y aprobación del docente.

## Qué hace

| Requisito | Funcionalidad |
|-----------|---------------|
| RF-01 a RF-03 | Laboratorios por cohorte, portafolio del estudiante, evidencias (PDF, ZIP o GitHub) y rúbricas versionadas |
| RF-04, RF-05 | Editor visual de rúbricas, importación desde PDF o texto con IA y validación (pesos = 100 %) |
| RF-06 a RF-08 | Evaluación por criterio con evidencias citadas, nota calculada en el backend, revisión, ajuste y aprobación docente |
| RF-09, RF-10 | Informe integral (web y PDF) y mapa mental de competencias (descarga PNG, SVG y JSON) |
| RF-11 | Página del proyecto y del equipo |
| RNF-03, RNF-04 | Sintaxis, análisis estático y **pruebas unitarias del estudiante en una sandbox** sin red y con límites de recursos |
| RNF-05 | Proveedor de IA configurable: Claude (nube), Ollama (local) o demostración |
| RNF-07 | Trazabilidad completa: evidencias, versión de rúbrica, modelo, prompt, uso, costo, pruebas y ajustes |

Detalle y estado de cada requisito en [docs/REQUISITOS.md](docs/REQUISITOS.md).

## Tecnologías

- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic y PostgreSQL 16.
- **Frontend:** React con Vite, Tailwind y React Flow.
- **IA:** SDK de Anthropic (Claude Haiku 5.5 con escalamiento a Sonnet 5.5) y Ollama.
- **Infraestructura:** Docker Compose, Caddy con HTTPS y GitHub Actions.

## Ejecutar en local

```bash
cp .env.example .env
```

Edita `.env` con secretos propios y, si quieres, `AI_PROVIDER`. Después:

```bash
docker compose up -d --build
```

Abre <http://localhost> (o el puerto definido en `WEB_PORT`) y entra con `ADMIN_CORREO` y `ADMIN_CONTRASENA`.

Pruebas:

```bash
cd backend && python -m pytest -q
```

## Documentación

- [Enunciado original](Proyecto_Final_IA_Asesor_Pedagogico_V3_Rubricas_Verificacion.md)
- [Requisitos y criterios de aceptación](docs/REQUISITOS.md)
- [Arquitectura y decisiones](docs/ARQUITECTURA.md)
- [Contrato de la API](docs/API.md)
- [Despliegue (Azure / Oracle)](docs/DESPLIEGUE.md)
- [Bitácora de uso de IA](docs/BITACORA_IA.md)
- [Cómo se trabajó con agentes de IA](docs/HARNESS.md)
