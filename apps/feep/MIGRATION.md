# Migrar la sección FEEP a su propio repositorio

Esta sección (`apps/feep/`) está diseñada para ser **autocontenida y portable**. No
importa código de ninguna otra app del repo `jokin-tools`, y sus datos viven en su
**propio fichero SQLite** (`feep.db`), separado de `jokin_tools.db`.

## Qué contiene la sección

```
apps/feep/
├── index.js               Router de la sección (portada + monta las sub-apps)
├── db.js                  Base de datos propia → feep.db (FEEP_DB_PATH)
├── MIGRATION.md           Este documento
├── public/                Assets de la sección (portada, estilos, y la UI de cada app)
│   ├── index.html         Portada (mini-hub de la fundación)
│   ├── feep.css           Estilos autocontenidos (sin fuentes/CDN externos)
│   ├── certificados.html  UI del certificado de asistencia
│   └── certificados.js
└── certificados/          App «Certificado de asistencia»
    ├── routes.js          API (crear, listar, PDF, email, predeterminados)
    └── pdf.js             Generación del PDF con pdfkit (sin navegador)
```

## Acoplamientos con el repo actual (los únicos puntos a resolver al migrar)

1. **Montaje** en `server.js`:
   ```js
   const feepDb = require('./apps/feep/db');
   const feepRouter = require('./apps/feep');
   app.use('/feep', requireApp('feep'), feepRouter);
   ```
   El login (`requireApp('feep')`) se aplica **en el montaje**, no dentro de la
   sección. En el repo nuevo solo hay que poner delante el middleware de auth de
   ese repo (cualquiera que ponga `req.user` con `id` y `email`).

2. **Registro en el hub**: entrada `feep` en `apps/auth/apps-registry.js`. En el
   repo nuevo, se lista donde corresponda (o se elimina si no hay hub).

3. **`req.user`**: las rutas usan `req.user.id` (propietario de cada certificado) y
   `req.user.email` (destinatario por defecto del email). Cualquier auth que
   rellene esos dos campos vale.

4. **Email** (opcional): reutiliza las variables SMTP del entorno
   (`SMTP_USER`, `SMTP_PASS`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `EMAIL_FROM`).

5. **Dependencias npm**: `express`, `better-sqlite3`, `pdfkit`, `nodemailer`
   (todas estándar; casi seguro ya están en el repo destino).

## Pasos de migración

1. Copiar la carpeta `apps/feep/` al repo nuevo.
2. Copiar el fichero **`feep.db`** al volumen del repo nuevo (o dejar que se cree
   vacío si se empieza de cero). Ruta configurable con `FEEP_DB_PATH`
   (por defecto `/data/feep.db`).
3. Añadir las dependencias npm listadas arriba a su `package.json`.
4. Montar el router en el servidor del repo nuevo, con su propio auth delante.
5. (Opcional) Configurar las variables SMTP para el envío por email.
6. En `jokin-tools`: borrar `apps/feep/`, la línea de montaje en `server.js` y la
   entrada `feep` de `apps/auth/apps-registry.js`.

No hay datos entrelazados ni migraciones de tablas: es una carpeta + un fichero de
base de datos + unas pocas líneas de cableado.

## Variables de entorno

| Variable        | Por defecto        | Uso                                   |
| --------------- | ------------------ | ------------------------------------- |
| `FEEP_DB_PATH`  | `/data/feep.db`    | Fichero SQLite de la sección          |
| `SMTP_USER`/`SMTP_PASS` | —          | Envío de certificados por email       |
| `SMTP_HOST`/`SMTP_PORT`/`SMTP_SECURE`/`EMAIL_FROM` | Gmail/587 | Config SMTP opcional |
