-- ============================================================
-- schema.sql
-- Ejecutar este script en: Supabase Dashboard > SQL Editor > New query
-- ============================================================

-- 1. Tabla principal donde se guardan los ítems extraídos por el scraper
create table if not exists public.scraped_items (
    id          bigint generated always as identity primary key,
    title       text not null,
    url         text not null,
    source      text,
    metadata    jsonb default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

-- Índice para acelerar el ORDER BY created_at que usa GET /api/items
create index if not exists idx_scraped_items_created_at
    on public.scraped_items (created_at desc);

-- Evita duplicados exactos si el scraper se corre varias veces sobre la misma URL
create unique index if not exists idx_scraped_items_url
    on public.scraped_items (url);

-- 2. Row Level Security (RLS)
-- La activamos siempre, incluso si el backend usa la service_role key
-- (esa key ignora RLS, pero así ningún otro cliente con la anon key
-- puede leer/escribir sin que nosotros lo autoricemos explícitamente).
alter table public.scraped_items enable row level security;

-- 2.1 Política de lectura pública (opcional).
-- Solo necesaria si en el futuro el FRONTEND fuera a consultar Supabase
-- directamente con la anon key, en lugar de pasar por nuestro backend.
-- En este taller el frontend NUNCA habla con Supabase directamente,
-- así que esta política es opcional pero se deja documentada.
create policy "Permitir lectura publica"
    on public.scraped_items
    for select
    to anon
    using (true);

-- 2.2 NO se crea política de INSERT para "anon".
-- Los inserts los hace exclusivamente el backend (server.js) usando
-- la SUPABASE_SERVICE_ROLE_KEY, que por diseño de Supabase omite RLS.
-- Esto es intencional: así ningún cliente externo (ni el frontend,
-- ni un curl malicioso) puede escribir directamente en la tabla.
