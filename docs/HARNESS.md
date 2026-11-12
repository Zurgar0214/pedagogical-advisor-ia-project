# Harness de desarrollo: orquestador + subagentes

Hay **dos capas de "agentes"** en este proyecto y conviene no mezclarlas:

1. **Capa de desarrollo** (este documento): cómo Claude Code construye el software.
2. **Capa de producto**: cómo la plataforma usa modelos de IA para evaluar laboratorios → ver [ARQUITECTURA.md](ARQUITECTURA.md#orquestación-de-modelos-en-la-evaluación).

## Roles y modelos

| Rol | Dónde vive | Modelo | Para qué |
|-----|-----------|--------|----------|
| **Orquestador** | Sesión principal de Claude Code | Claude Fable 5.2 (el más capaz hoy) u Opus 5.5 para ahorrar | Planificar, dividir tareas, decidir arquitectura, desbloquear subagentes, verificar resultados |
| `backend-dev` | `.claude/agents/backend-dev.md` | Sonnet 5.5 | API, modelos de datos, servicios, autenticación |
| `frontend-dev` | `.claude/agents/frontend-dev.md` | Sonnet 5.5 | UI, informe, mapa mental, página del equipo |
| `ia-evaluacion` | `.claude/agents/ia-evaluacion.md` | Sonnet 5.5 | Pipeline de evaluación, esquemas Pydantic, prompts, adaptadores de proveedor, sandbox |
| `tester` | `.claude/agents/tester.md` | Haiku 5.5 | Ejecutar pruebas/lint y reportar fallos con precisión |
| `revisor` | `.claude/agents/revisor.md` | Sonnet 5.5 | Revisar cambios contra reglas de oro y criterios de aceptación |
| `documentador` | `.claude/agents/documentador.md` | Haiku 5.5 | Bitácora de IA, README, documentación de despliegue |

El modelo del orquestador se elige en el selector de modelo de la app (no en un archivo). Los subagentes fijan su modelo
en el `model:` de su frontmatter.

Precios de referencia API (USD por millón de tokens, entrada/salida): Fable 5.2 $8/$40 · Opus 5.5 $4/$20 · Sonnet 5.5 $2/$10 · Haiku 5.5 $0,10/$0,50.

## Protocolo de escalamiento ("preguntarle al de arriba")

En Claude Code un subagente **no puede** hacerle una pregunta al orquestador a mitad de su ejecución; solo devuelve un
informe al terminar. Por eso el escalamiento se implementa así:

1. El subagente trabaja hasta donde pueda **sin adivinar** decisiones de diseño.
2. Si se bloquea (ambigüedad de requisito, decisión de arquitectura, error que no logra resolver en 2 intentos,
   cambio que tocaría archivos fuera de su alcance), **se detiene** y termina con este bloque:

   ```
   ESTADO: BLOQUEADO
   TAREA: <ID de requisito y resumen>
   PREGUNTA: <una pregunta concreta>
   CONTEXTO: <qué intentó, error exacto, archivos relevantes>
   OPCIONES: <A / B con pros y contras, y cuál recomienda>
   AVANCE: <qué quedó hecho y qué no>
   ```

3. El orquestador responde y **continúa el mismo subagente** con `SendMessage` (conserva su contexto), en lugar de
   lanzar uno nuevo. Si la decisión es de negocio o del equipo, el orquestador se la pregunta al usuario.
4. Si el subagente termina bien, cierra con `ESTADO: COMPLETADO`, archivos tocados y cómo verificó el criterio de aceptación.

## Ciclo por tarea

```
Orquestador: elige requisito → define tarea pequeña con criterio de aceptación y archivos permitidos
   → delega (backend-dev / frontend-dev / ia-evaluacion)
   → si BLOQUEADO: decide y continúa con SendMessage
   → tester ejecuta pruebas/lint
   → revisor valida contra reglas de oro (CLAUDE.md)
   → orquestador verifica, actualiza docs/REQUISITOS.md y pide entrada en la bitácora (documentador)
```

Reglas para el orquestador:
- Dos subagentes nunca escriben los mismos archivos al mismo tiempo.
- No marcar nada como ✅ basándose solo en el informe del subagente: revisar el diff o la salida de pruebas.
- Tareas de lectura amplia (buscar en el código) → subagente barato; decisiones → orquestador.
