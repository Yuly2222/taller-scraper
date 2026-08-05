/**
 * server.js
 * ---------
 * API REST que desacopla el scraper de Supabase.
 *
 *  POST /api/items  -> recibe { items: [...] } del scraper.py, valida y
 *                       hace un insert masivo en la tabla scraped_items.
 *  GET  /api/items   -> devuelve todos los registros, ordenados por
 *                       created_at descendente, para el frontend.
 *
 * Variables de entorno requeridas (ver .env.example):
 *  - SUPABASE_URL
 *  - SUPABASE_SERVICE_ROLE_KEY   (NUNCA exponer esta key al frontend)
 *  - PORT (opcional, default 3000)
 */

require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { createClient } = require("@supabase/supabase-js");

// --------------------------------------------------------------------------
// Validación de configuración al arrancar (fail-fast)
// --------------------------------------------------------------------------
const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, PORT = 3000 } = process.env;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error(
    "[FATAL] Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el archivo .env"
  );
  process.exit(1);
}

// El backend usa la service_role key porque es un cliente CONFIABLE
// (corre en nuestro servidor, nunca en el navegador). Esta key ignora
// RLS, por eso es la única pieza autorizada a escribir en la tabla.
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

// --------------------------------------------------------------------------
// App
// --------------------------------------------------------------------------
const app = express();

app.use(cors()); // permite que index.html (servido desde otro origen) consuma la API
app.use(express.json({ limit: "1mb" })); // limita tamaño de payload por seguridad

// --------------------------------------------------------------------------
// Validación de payload
// --------------------------------------------------------------------------
function validateItem(item) {
  if (typeof item !== "object" || item === null) return "item no es un objeto";
  if (typeof item.title !== "string" || item.title.trim() === "")
    return "falta 'title' (string no vacío)";
  if (typeof item.url !== "string" || item.url.trim() === "")
    return "falta 'url' (string no vacío)";
  if (item.source !== undefined && typeof item.source !== "string")
    return "'source' debe ser string";
  if (item.metadata !== undefined && typeof item.metadata !== "object")
    return "'metadata' debe ser un objeto";
  return null; // válido
}

// --------------------------------------------------------------------------
// POST /api/items
// --------------------------------------------------------------------------
app.post("/api/items", async (req, res) => {
  try {
    const { items } = req.body;

    if (!Array.isArray(items) || items.length === 0) {
      return res.status(400).json({
        error: "El body debe tener la forma { items: [...] } con al menos un item.",
      });
    }

    // Validar cada item antes de tocar la base de datos
    for (let i = 0; i < items.length; i++) {
      const error = validateItem(items[i]);
      if (error) {
        return res.status(400).json({ error: `Item inválido en índice ${i}: ${error}` });
      }
    }

    // Normalizar: solo dejamos pasar las columnas que existen en la tabla
    const rows = items.map((item) => ({
      title: item.title.trim(),
      url: item.url.trim(),
      source: item.source ?? null,
      metadata: item.metadata ?? {},
    }));

    // Insert masivo. onConflict evita error si la URL ya existe (ver índice único en schema.sql)
    const { data, error } = await supabase
      .from("scraped_items")
      .upsert(rows, { onConflict: "url", ignoreDuplicates: true })
      .select();

    if (error) {
      console.error("[Supabase insert error]", error);
      return res.status(502).json({ error: "Error al guardar en la base de datos." });
    }

    return res.status(201).json({
      message: "Items procesados correctamente.",
      inserted: data ? data.length : 0,
    });
  } catch (err) {
    console.error("[POST /api/items] Error inesperado:", err);
    return res.status(500).json({ error: "Error interno del servidor." });
  }
});

// --------------------------------------------------------------------------
// GET /api/items
// --------------------------------------------------------------------------
app.get("/api/items", async (req, res) => {
  try {
    const { data, error } = await supabase
      .from("scraped_items")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      console.error("[Supabase select error]", error);
      return res.status(502).json({ error: "Error al consultar la base de datos." });
    }

    return res.status(200).json({ items: data });
  } catch (err) {
    console.error("[GET /api/items] Error inesperado:", err);
    return res.status(500).json({ error: "Error interno del servidor." });
  }
});

// --------------------------------------------------------------------------
// Health check (útil para verificar que el server está vivo)
// --------------------------------------------------------------------------
app.get("/health", (req, res) => res.status(200).json({ status: "ok" }));

// --------------------------------------------------------------------------
// 404 y manejador de errores genérico
// --------------------------------------------------------------------------
app.use((req, res) => res.status(404).json({ error: "Ruta no encontrada." }));

app.use((err, req, res, next) => {
  console.error("[Unhandled error]", err);
  res.status(500).json({ error: "Error interno del servidor." });
});

app.listen(PORT, () => {
  console.log(`Servidor escuchando en http://localhost:${PORT}`);
});
