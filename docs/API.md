# Contrato de la API

Fuente de verdad compartida entre backend y frontend. Si un agente necesita cambiarlo, escala al orquestador.
Base: `/api`. JSON en español. Autenticación: `Authorization: Bearer <token>` (JWT HS256, expira en 8 h).

## Roles

| Rol | Puede |
|-----|-------|
| `admin` | Todo, incluida la gestión de usuarios |
| `docente` | Gestionar laboratorios y rúbricas, ver todos los portafolios, revisar y aprobar evaluaciones |
| `estudiante` | Ver y cargar su propio portafolio; ver solo sus evaluaciones **publicadas** |

## Errores

Siempre `{"detail": "<mensaje en español>"}` con el código HTTP adecuado (400 validación, 401 sin sesión o token inválido,
403 sin permiso, 404 no existe, 409 conflicto como correo repetido).

## Usuario (objeto)

```json
{ "id": 1, "nombre": "Ana Pérez", "correo": "ana@umanizales.edu.co", "rol": "estudiante", "activo": true, "creado_en": "2026-11-12T15:00:00Z" }
```

## Endpoints de esta iteración

| Método y ruta | Rol | Cuerpo | Respuesta |
|---------------|-----|--------|-----------|
| `GET /api/salud` | público | — | `{"estado":"ok","version":"0.1.0"}` |
| `POST /api/auth/login` | público | `{"correo","contrasena"}` | `{"access_token","token_type":"bearer","usuario":Usuario}`; 401 si credenciales inválidas o usuario inactivo (mismo mensaje en ambos casos) |
| `GET /api/auth/yo` | autenticado | — | `Usuario` |
| `GET /api/usuarios` | admin | query opcional `rol` | `Usuario[]` |
| `POST /api/usuarios` | admin | `{"nombre","correo","contrasena","rol"}` (contraseña ≥ 8 caracteres) | `Usuario` (201); 409 si el correo existe |
| `PATCH /api/usuarios/{id}` | admin | cualquiera de `{"nombre","rol","activo","contrasena"}` | `Usuario`; un admin no puede desactivarse ni quitarse el rol a sí mismo (400) |

Primer arranque: si no hay usuarios, el backend crea un admin con `ADMIN_CORREO` y `ADMIN_CONTRASENA` del entorno.
