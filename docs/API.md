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

---

# Iteración 2: laboratorios, rúbricas versionadas y portafolio (RF-01, RF-02, RF-03, RF-05)

Regla de privacidad (RNF-08): un estudiante que pide una entrega o evidencia ajena recibe **404** (no 403), para no revelar que existe.

## Objetos

**Laboratorio**
```json
{ "id": 1, "cohorte": 1, "codigo": "C1-LAB01", "titulo": "Regresión lineal", "descripcion": "...", "objetivos": "...",
  "temas": ["aprendizaje supervisado", "regresión"],
  "rubrica_vigente": { "version_id": 3, "numero": 2, "valida": true } }
```
`rubrica_vigente` es la versión de número más alto, o `null` si no hay ninguna. `cohorte` ∈ {1, 2}.

**Contenido de rúbrica** = esquema `Rubrica` de `backend/app/schemas/rubrica.py`
(`competencias[{id,nombre,descripcion}]`, `criterios[{id,nombre,descripcion,competencia_id,peso,niveles[{nombre,descriptor,valor}]}]`).
Se añade `descripcion: str = ""` opcional a `Criterio`. El campo `version` del contenido lo ignora el servidor (el número lo asigna la tabla).

**RubricaVersion**
```json
{ "id": 3, "numero": 2, "valida": true, "inconsistencias": [], "contenido": { ... },
  "creado_por": { "id": 1, "nombre": "..." }, "creado_en": "..." }
```

**Evidencia**
```json
{ "id": 9, "tipo": "informe_pdf", "nombre_original": "informe.pdf", "url": null, "tamano_bytes": 123456,
  "sha256": "...", "creado_en": "...", "detalle": { "paginas": 12, "caracteres_texto": 18000 } }
```
Tipos: `informe_pdf`, `codigo_zip`, `repo_github`, `video`, `presentacion`, `imagen`.
`detalle` según tipo: PDF → `{paginas, caracteres_texto}`; ZIP → `{archivos, tamano_descomprimido_bytes, extensiones: {".py": n}}` (5 más comunes); repo → `{owner, repo}`.

**Entrega**
```json
{ "id": 5, "estado": "lista", "creado_en": "...",
  "estudiante": { "id": 2, "nombre": "..." },
  "laboratorio": { "id": 1, "codigo": "C1-LAB01", "titulo": "...", "cohorte": 1 },
  "rubrica_version": { "id": 3, "numero": 2 },
  "evidencias": [Evidencia],
  "faltantes": ["codigo"] }
```
Estados: `borrador` (faltan obligatorias) → `lista` (tiene `informe_pdf` y al menos uno de `codigo_zip`/`repo_github`) → `en_evaluacion` → `evaluada`.
El servidor recalcula `borrador`/`lista` al agregar o borrar evidencias. `faltantes` ⊆ {`informe_pdf`, `codigo`}.

## Endpoints

| Método y ruta | Rol | Notas |
|---------------|-----|-------|
| `GET /api/laboratorios?cohorte=` | autenticado | Ordenados por cohorte y código |
| `POST /api/laboratorios` | docente, admin | `{cohorte, codigo, titulo, descripcion, objetivos, temas}` → 201; 409 código repetido |
| `GET /api/laboratorios/{id}` | autenticado | |
| `PATCH /api/laboratorios/{id}` | docente, admin | Campos parciales |
| `GET /api/laboratorios/{id}/rubrica` | autenticado | `{ "vigente": RubricaVersion \| null, "versiones": [RubricaVersion sin contenido] }` |
| `POST /api/laboratorios/{id}/rubrica/versiones` | docente, admin | Cuerpo: contenido de rúbrica. **Siempre** crea una versión nueva (aunque sea inválida, para poder corregirla), ejecuta `validar_rubrica` y guarda `valida` + `inconsistencias`. 201 → RubricaVersion |
| `GET /api/rubrica-versiones/{id}` | autenticado | RubricaVersion con contenido (versiones antiguas siguen disponibles) |
| `POST /api/rubricas/validar` | docente, admin | Validación sin guardar: `{ "valida": bool, "inconsistencias": [str] }` |
| `GET /api/estudiantes` | docente, admin | Lista de usuarios con rol estudiante y activos: `[{id, nombre, correo}]` ordenada por nombre |
| `GET /api/portafolio?estudiante_id=` | autenticado | Estudiante: siempre el propio (ignora el parámetro). Docente/admin: obligatorio. → `{ "estudiante": {id,nombre,correo}, "cohortes": [{ "cohorte": 1, "laboratorios": [{ "laboratorio": Laboratorio, "entrega": Entrega resumida (sin evidencias) \| null }] }] }` con ambas cohortes aunque estén vacías |
| `GET /api/entregas?estudiante_id=&laboratorio_id=&estado=` | autenticado | Estudiante: solo las suyas |
| `POST /api/entregas` | autenticado | `{laboratorio_id, estudiante_id?}`; estudiante crea la propia (se ignora `estudiante_id`); docente/admin deben indicarlo y debe ser un estudiante. Fija la `rubrica_vigente` del laboratorio, que debe existir y ser **válida** (si no, 400 explicando por qué). 409 si ya existe. → 201 Entrega |
| `GET /api/entregas/{id}` | dueño, docente, admin | Entrega completa |
| `POST /api/entregas/{id}/evidencias` | dueño, docente, admin | `multipart/form-data`: `tipo` + `archivo`, o `tipo=repo_github` + `url`. Solo si estado es `borrador` o `lista`. → 201 Evidencia |
| `DELETE /api/entregas/{id}/evidencias/{evidencia_id}` | dueño, docente, admin | Solo en `borrador`/`lista`; borra también el archivo. 204 |
| `GET /api/evidencias/{id}/archivo` | dueño, docente, admin | Descarga con `Content-Disposition: attachment` y el nombre original saneado |

## Reglas de carga de evidencias

| Tipo | Formato aceptado | Validación |
|------|------------------|-----------|
| `informe_pdf` | PDF, máx. 20 MB, **uno por entrega** (409 si ya hay; se borra y se vuelve a subir) | Firma `%PDF`; texto extraíble con `pypdf` ≥ 200 caracteres, si no: 400 "El PDF no tiene texto legible…". El texto extraído se guarda para la evaluación |
| `codigo_zip` | ZIP, máx. 50 MB | Firma ZIP válida; ≤ 2000 entradas; tamaño descomprimido ≤ 200 MB; rechazar rutas absolutas o con `..`. **No se descomprime ni se ejecuta** en esta iteración |
| `repo_github` | URL | Debe ser `https://github.com/<owner>/<repo>` (opcional `.git` o `/`); no se clona todavía |
| `imagen` | PNG, JPEG, máx. 10 MB | Firma de imagen |
| `presentacion` | PDF o PPTX, máx. 50 MB | Firma |
| `video` | MP4 o WEBM, máx. 50 MB | Firma |

Almacenamiento: `STORAGE_DIR/entregas/<entrega_id>/<uuid4><ext>`; **nunca** se usa el nombre original en la ruta; se guarda SHA-256.
El tamaño se controla mientras se lee el archivo (no confiar en `Content-Length`). Archivos fuera de cualquier ruta servida públicamente.
