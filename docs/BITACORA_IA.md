# Bitácora de desarrollo aumentado con IA

Entregable obligatorio (RNF-01). Registrar herramientas usadas, en qué actividad, qué aportaron, limitaciones
encontradas y qué decisión humana se tomó.

| Fecha | Fase | Herramienta / modelo | Actividad | Aporte | Limitaciones / correcciones humanas | Decisión |
|-------|------|----------------------|-----------|--------|-------------------------------------|----------|
| 2026-11-12 | Requisitos y diseño | Claude Code (Opus 5.5) | Lectura del enunciado, matriz de requisitos, propuesta de arquitectura y harness de agentes | Requisitos con IDs y criterios de aceptación; protocolo de escalamiento entre subagentes | El stack es una propuesta; falta validarlo con el equipo | Trabajar con orquestador + subagentes por componente |
| 2026-11-12 | Implementación | Claude Code: orquestador Opus 5.5 + 2 subagentes Sonnet 5.5 en paralelo | Esqueleto backend (FastAPI, validador de rúbricas RF-05, cálculo de nota RF-07) y frontend (React + Tailwind, página del proyecto RF-11); Docker Compose | 20 pruebas unitarias y lint en verde; frontend compila; stack levantado en Docker y verificado en navegador | El orquestador detectó desajustes de configuración entre agentes (formato de `CORS_ORIGINS`, nombre del proveedor de IA) y los corrigió; los subagentes no podían tocar archivos fuera de su carpeta | Los agentes trabajan en carpetas separadas; el orquestador integra y verifica |
