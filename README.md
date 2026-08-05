# Taller: Web Scraper + API REST + Supabase + Frontend

Solución end-to-end: un scraper en Python extrae datos de la web, los envía
a una API en Node.js/Express, que los guarda en Supabase (PostgreSQL); un
frontend en HTML/JS los consume y los muestra en tarjetas.

```
scraper (Python) --POST--> backend (Node/Express) --> Supabase (Postgres)
                                    ^
                                    |
                          frontend (HTML/JS) --GET--
```

## Estructura del proyecto

```
taller-scraper/
├── scraper/
│   ├── scraper.py          # Web scraper
│   └── requirements.txt
├── backend/
│   ├── server.js           # API REST
│   ├── package.json
│   └── .env.example
├── frontend/
│   └── index.html          # Dashboard
├── sql/
│   └── schema.sql          # Tabla + RLS para Supabase
├── .gitignore
└── README.md
```

---

## Paso 1 — Crear el proyecto en Supabase

1. Ve a [supabase.com](https://supabase.com) y crea un proyecto nuevo (gratis).
2. Una vez creado, entra a **SQL Editor > New query**, pega el contenido de
   `sql/schema.sql` y ejecútalo (botón Run). Esto crea:
   - la tabla `scraped_items` (id, title, url, source, metadata, created_at)
   - un índice único en `url` (evita duplicados si corres el scraper varias veces)
   - RLS (Row Level Security) activado en la tabla
3. Ve a **Project Settings > API** y copia:
   - `Project URL` → lo necesitarás como `SUPABASE_URL`
   SUPABASE_URL= https://mwpnasdfssovcmtezrgq.supabase.co
   - `service_role` key (⚠️ **no** la `anon` key) → `SUPABASE_SERVICE_ROLE_KEY`
   SUPABASE_SERVICE_ROLE_KEY= eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im13cG5hc2Rmc3NvdmNtdGV6cmdxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTkzMDkxMSwiZXhwIjoyMTAxNTA2OTExfQ.fO7lCAriksXGwG6zyvbP-ttUuQmYoKPzdYDoreAqspo

   La `service_role` key tiene permisos totales y **debe quedarse solo en el
   backend**, nunca en el frontend ni en un repositorio público. Por eso el
   `.gitignore` excluye `.env`.

---

## Paso 2 — Levantar el backend (server.js)

```bash
cd backend
npm install
cp .env.example .env
```

Edita `.env` con tus valores reales de Supabase:

```
SUPABASE_URL=https://tuproyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...
PORT=3000
```

Arranca el servidor:

```bash
npm start
```

Deberías ver: `Servidor escuchando en http://localhost:3000`

**Cómo funciona `server.js`:**
- Usa `express` para exponer dos rutas HTTP.
- Usa `@supabase/supabase-js` para hablar con la base de datos con la
  `service_role` key (esta key ignora RLS porque el backend es un cliente
  de confianza — corre en tu servidor, no en el navegador del usuario).
- `POST /api/items`: recibe `{ items: [...] }`, valida que cada item tenga
  `title` y `url`, y hace un `upsert` (insert que ignora duplicados por `url`)
  en la tabla.
- `GET /api/items`: hace un `select *` ordenado por `created_at descendente`
  y lo devuelve como JSON.
- Tiene manejo de errores en cada ruta (try/catch), validación de entrada,
  y un límite de tamaño de payload (`1mb`) para evitar abusos.

Puedes probarlo sin el scraper, con curl:

```bash
curl -X POST http://localhost:3000/api/items \
  -H "Content-Type: application/json" \
  -d '{"items":[{"title":"Prueba","url":"https://example.com","source":"Manual","metadata":{"points":10}}]}'

curl http://localhost:3000/api/items
```

---

## Paso 3 — Correr el scraper (scraper.py)

```bash
cd scraper
python3 -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python scraper.py
```

**Cómo funciona `scraper.py`:**
- `fetch_html()` hace un `GET` a Hacker News (`https://news.ycombinator.com/`)
  con `requests`, con timeout y manejo de errores de red.
- `parse_items()` usa `BeautifulSoup` para recorrer cada fila `tr.athing`
  (cada post de HN) y extraer título, enlace, puntos, autor y cantidad de
  comentarios.
- `send_to_api()` empaqueta la lista en `{ "items": [...] }` y hace un
  `POST` a `http://localhost:3000/api/items` (configurable con la variable
  de entorno `API_URL`).
- Tiene modo `--dry-run` para probar el scraping sin tocar el backend:
  ```bash
  python scraper.py --dry-run
  ```

Si todo va bien verás en la consola algo como:
```
[INFO] Se extrajeron 30 items.
[INFO] POST exitoso: 30 items enviados, 30 insertados.
```

---

## Paso 4 — Abrir el frontend (index.html)

Con el backend corriendo (`npm start` en otra terminal), simplemente abre
`frontend/index.html` con doble clic, o sírvelo con un servidor estático:

```bash
cd frontend
python3 -m http.server 5500
# abre http://localhost:5500
```

**Cómo funciona `index.html`:**
- Al cargar la página, `loadItems()` hace un `fetch GET` a
  `http://localhost:3000/api/items`.
- Renderiza cada item como una tarjeta (título clicable, fuente, puntos,
  autor, fecha).
- El botón **Actualizar** vuelve a llamar `loadItems()` para traer los
  registros más recientes que haya insertado el scraper.
- Usa `escapeHtml()` antes de insertar cualquier dato de la API en el DOM,
  para evitar XSS si algún título contuviera HTML/scripts.
- Si el backend no responde, muestra un mensaje de error en vez de romperse.

Nota: `API_BASE_URL` en `index.html` está hardcodeado a
`http://localhost:3000`. Si despliegas el backend en otro host, cambia esa
constante.

---

## Flujo completo de extremo a extremo

1. `npm start` (backend) — queda escuchando en el puerto 3000.
2. `python scraper.py` — extrae datos de Hacker News y los POSTea al backend,
   que los guarda en Supabase.
3. Abres `index.html` (o recargas si ya estaba abierto) y ves las tarjetas
   con los datos recién guardados.
4. Puedes volver a correr `scraper.py` cuando quieras y darle "Actualizar"
   en el frontend para ver los nuevos registros (los duplicados por `url`
   se ignoran automáticamente gracias al índice único + `upsert`).

---

## Consideraciones de seguridad

- La `service_role` key **nunca** se expone al frontend; solo vive en
  `backend/.env` (excluido de git vía `.gitignore`).
- RLS está activo en `scraped_items`; solo el backend (con `service_role`)
  puede escribir. Se agregó una política de lectura pública opcional por si
  en el futuro quieres consultar la tabla directamente desde el navegador
  con la `anon` key — pero en este diseño no es necesaria porque el
  frontend siempre pasa por el backend.
- El backend valida la estructura de cada item antes de insertarlo (evita
  guardar basura o payloads malformados).
- El frontend escapa todo el contenido dinámico antes de insertarlo en el
  DOM (previene XSS).
- El scraper identifica un `User-Agent` propio y respeta timeouts, en línea
  con buenas prácticas de scraping.


El `.gitignore` ya excluye `node_modules/`, `.env` y archivos de entornos
virtuales de Python, así que no subirás secretos ni dependencias pesadas.
