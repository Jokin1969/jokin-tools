# Jokin's Tools

**Research Utilities Hub** — Plataforma web modular con herramientas especializadas para investigación científica.

---

## Stack

- **Backend:** Node.js + Express
- **Base de datos:** SQLite con `better-sqlite3` (volumen Railway `/data`)
- **Scheduling:** `node-cron` (cron diario 06:50 Madrid)
- **Email:** Nodemailer (SMTP)
- **Export:** Dropbox API v2 con refresh token
- **Frontend:** HTML/CSS/JS vanilla (hub) + HTML/CSS/JS (Re-memory)
- **Deploy:** Railway

---

## Estructura

```
jokin-tools/
├── apps/
│   └── re-memory/          # Micro-app Re-memory
│       ├── db.js            # SQLite schema + CRUD
│       ├── routes.js        # Express router + API
│       ├── email.js         # Nodemailer + HTML email builder
│       ├── cron.js          # node-cron scheduler
│       ├── dropbox.js       # Dropbox API v2 export
│       └── public/          # Frontend Re-memory
│           ├── index.html
│           ├── app.css
│           └── app.js
├── public/                  # Assets compartidos (favicons)
├── src/                     # Frontend hub principal
│   ├── index.html
│   └── hub.css
├── server.js                # Express server principal
├── package.json
├── railway.toml
└── .env.example
```

---

## Variables de entorno

Copia `.env.example` a `.env` para desarrollo local:

```bash
cp .env.example .env
```

Configura todas las variables en **Railway → Project → Variables**:

| Variable | Descripción |
|---|---|
| `PORT` | Puerto del servidor (Railway lo asigna automáticamente) |
| `NODE_ENV` | `production` |
| `BASE_URL` | URL pública del deploy, ej. `https://jokin-tools.railway.app` |
| `DB_PATH` | `/data/jokin_tools.db` (CRÍTICO: siempre `/data/`) |
| `SMTP_HOST` | Servidor SMTP, ej. `smtp.gmail.com` |
| `SMTP_PORT` | Puerto SMTP, ej. `587` |
| `SMTP_SECURE` | `false` para TLS/STARTTLS, `true` para SSL |
| `SMTP_USER` | Usuario SMTP (tu email) |
| `SMTP_PASS` | App password de Gmail (no la contraseña normal) |
| `EMAIL_FROM` | Remitente, ej. `"Re-memory <tu@gmail.com>"` |
| `EMAIL_TO` | Destinatario de los recordatorios |
| `DROPBOX_APP_KEY` | App Key de tu Dropbox App |
| `DROPBOX_APP_SECRET` | App Secret de tu Dropbox App |
| `DROPBOX_REFRESH_TOKEN` | Refresh token (obtener con el flujo OAuth2 — ver abajo) |
| `DROPBOX_FOLDER` | Carpeta en Dropbox, ej. `/JokinTools/ReMemory/exports/` |
| `DEACTIVATION_SECRET` | Clave HMAC para links de desactivación en emails (string aleatorio largo) |

---

## Despliegue en Railway

### 1. Crear proyecto y conectar repo

```bash
# En Railway dashboard:
# New Project → Deploy from GitHub repo → jokin1969/jokin-tools
```

### 2. Configurar volumen persistente

**CRÍTICO:** Sin el volumen, la base de datos se borra en cada redeploy.

1. Railway dashboard → tu proyecto → **Add Volume**
2. Mount path: `/data`
3. El servidor creará automáticamente `/data/jokin_tools.db` y `/data/uploads/` al arrancar

### 3. Configurar variables de entorno

En Railway → tu proyecto → **Variables**, añadir todas las variables del `.env.example`.

Para generar `DEACTIVATION_SECRET`:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### 4. Configurar Gmail (SMTP)

1. Activa la verificación en 2 pasos en tu cuenta Google
2. Ve a **Cuenta Google → Seguridad → Contraseñas de aplicaciones**
3. Genera una contraseña para "Correo" + "Otro dispositivo"
4. Usa esa contraseña como `SMTP_PASS`

---

## Obtener Dropbox Refresh Token (primera vez)

### Paso 1: Crear una Dropbox App

1. Ve a [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. **Create app** → **Scoped access** → **Full Dropbox** (o App folder)
3. Nombre: `jokin-tools` (o el que prefieras)
4. En la pestaña **Permissions**, activa: `files.content.write`, `files.content.read`
5. En **Settings**, añade a **Redirect URIs**: `https://tu-dominio.railway.app/re-memory/auth/dropbox/callback`
6. Copia **App key** y **App secret** → ponlos en Railway como `DROPBOX_APP_KEY` y `DROPBOX_APP_SECRET`

### Paso 2: Completar el flujo OAuth2

Una vez desplegada la app con las variables configuradas:

1. Visita: `https://tu-dominio.railway.app/re-memory/auth/dropbox`
2. Autoriza la app en Dropbox
3. Serás redirigido a `/re-memory/auth/dropbox/callback`
4. La página mostrará el `refresh_token` en JSON
5. Copia el `refresh_token` → añádelo como `DROPBOX_REFRESH_TOKEN` en Railway
6. **Seguridad:** Una vez obtenido el token, considera eliminar o proteger las rutas `/auth/dropbox` comentándolas en `apps/re-memory/routes.js`

---

## Desarrollo local

```bash
# Instalar dependencias
npm install

# Crear .env con tus valores
cp .env.example .env
# Editar .env: cambiar DB_PATH a ./data/jokin_tools.db para local

# Crear directorio de datos local
mkdir -p ./data/uploads

# Arrancar
npm run dev
# o
npm start
```

La app estará disponible en `http://localhost:3000`.

---

## Rutas principales

| Ruta | Descripción |
|---|---|
| `GET /` | Hub principal |
| `GET /re-memory` | App Re-memory |
| `GET /re-memory/api/memories` | Listar memorias (con filtros) |
| `POST /re-memory/api/memories` | Crear memoria |
| `PUT /re-memory/api/memories/:id` | Actualizar memoria |
| `DELETE /re-memory/api/memories/:id` | Borrar memoria |
| `PATCH /re-memory/api/memories/:id/toggle` | Toggle activo/inactivo |
| `POST /re-memory/api/memories/:id/image` | Subir imagen |
| `POST /re-memory/api/test-email/:id` | Enviar email de prueba |
| `GET /re-memory/api/export/csv` | Exportar CSV a Dropbox |
| `GET /re-memory/api/deactivate/:id/:token` | Desactivar desde link email |
| `GET /re-memory/auth/dropbox` | Iniciar OAuth2 Dropbox |
| `GET /re-memory/auth/dropbox/callback` | Callback OAuth2 Dropbox |

---

## Verificar que el despliegue es correcto

1. **Volumen:** Los logs deben mostrar `[db] Database initialized at: /data/jokin_tools.db`
2. **Cron:** Los logs deben mostrar `[cron] Re-memory daily job scheduled (06:50 Europe/Madrid)`
3. **Email:** Usa el endpoint `POST /re-memory/api/test-email/:id` para verificar SMTP
4. **Dropbox:** Usa el botón "Exportar CSV" desde la app y verifica que el archivo aparece en Dropbox

---

## Licencia

MIT

---

## Batchwork

Herramienta de operaciones por lotes sobre ficheros, accesible en `/batchwork`.

### Operaciones disponibles

| # | Operación | Entrada | Salida |
|---|-----------|---------|--------|
| 1 | Inventariar carpeta → Excel | Selector de carpeta (`webkitdirectory`) | `.xlsx` |
| 2 | Renombrar desde lista | Ficheros + `.txt` con nombres | ZIP |
| 3 | Transparentar PNG (conservando negro) | PNG / JPG | ZIP de PNG |
| 4 | Ajustar TIFF a 300 ppp / tamaño máximo | TIFF | ZIP de TIFF |
| 5 | DOCX → PDF | `.docx` | ZIP de PDF |
| 6 | PDF → DOCX | `.pdf` | ZIP de DOCX |
| 7 | Unificar carpeta a PDF (normalización DNI) | Ficheros mixtos | ZIP de PDF renombrados |
| 8 | Unir PDFs en uno solo | `.pdf` | ZIP con PDF unificado |
| 9 | Dividir PDFs | `.pdf` | ZIP con subcarpetas |

### Variables de entorno de Batchwork

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BATCHWORK_MAX_UPLOAD_MB` | `500` | Límite de subida por lote en MB |
| `BATCHWORK_TMP_DIR` | `/tmp/batchwork` | Directorio de sesiones temporales |
| `BATCHWORK_SESSION_TTL_MIN` | `30` | TTL de sesiones en minutos |
| `PYTHON_BIN` | `python3` | Ruta al intérprete Python |

### Dependencias de sistema

Batchwork requiere:
- **Python 3** con los paquetes: `Pillow>=10.0.0`, `pypdf>=4.0.0`, `pdf2docx>=0.5.8`
- **LibreOffice Writer** para conversión DOCX→PDF (op. 5 y op. 7 con ficheros .docx)

En Railway con nixpacks, añadir `libreoffice` a `nixpacks.toml` bajo `nixPkgs`. Los paquetes Python se instalan vía `pip3` en la fase de instalación.

### API de Batchwork

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/batchwork` | SPA frontend |
| `POST` | `/batchwork/api/session` | Crear sesión (devuelve UUID) |
| `POST` | `/batchwork/api/session/:id/upload` | Subir ficheros al lote |
| `POST` | `/batchwork/api/session/:id/execute` | Lanzar operación |
| `GET` | `/batchwork/api/session/:id/status` | Estado de la ejecución |
| `POST` | `/batchwork/api/session/:id/resolve` | Resolver decisión del usuario |
| `GET` | `/batchwork/api/session/:id/download` | Descargar resultado |
| `DELETE` | `/batchwork/api/session/:id` | Eliminar sesión |
