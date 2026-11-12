-- OpenBridge · Paso 1: preparar Supabase para búsqueda semántica
-- Ejecutar en el SQL Editor de Supabase.

-- 1) Extensión
create extension if not exists vector;

-- 2) Columnas nuevas
--    topics: los topics de GitHub son una de las mejores señales semánticas y hoy no están en la tabla.
--            (están en el CSV; hay que hacer un backfill con un UPDATE desde Python)
alter table repositories add column if not exists topics text[];
alter table repositories add column if not exists embedding_text text;    -- el texto exacto que se embebió (útil para depurar)
alter table repositories add column if not exists embedding_model text;   -- para saber con qué modelo se generó

-- 3) Fijar la dimensión del vector (text-embedding-3-small = 1536).
--    Funciona si la columna está vacía (todo NULL). Si cambiás de modelo, cambiá este número.
alter table repositories alter column embedding type vector(1536);

-- 4) Índice HNSW con distancia coseno.
--    Con ~100 repos no hace falta (un scan exacto es instantáneo), pero queda listo para crecer.
create index if not exists repositories_embedding_idx
  on repositories using hnsw (embedding vector_cosine_ops);

-- 5) Búsqueda por similitud con filtros duros (SQL) + vector, en una sola query.
create or replace function match_repositories(
  query_embedding  vector(1536),
  match_count      int     default 8,
  min_health       float8  default 0,
  filter_license   text[]  default null,
  filter_language  text[]  default null,
  filter_category  text    default null
)
returns table (
  id                uuid,
  full_name         varchar,
  description       text,
  original_category varchar,
  languages         varchar,
  license           varchar,
  stars             int,
  health_score      float8,
  html_url          varchar,
  similarity        float8
)
language sql stable
as $$
  select
    r.id, r.full_name, r.description, r.original_category, r.languages,
    r.license, r.stars, r.health_score, r.html_url,
    1 - (r.embedding <=> query_embedding) as similarity
  from repositories r
  where r.embedding is not null
    and coalesce(r.archived, false)  = false
    and coalesce(r.disabled, false)  = false
    and coalesce(r.health_score, 0) >= min_health
    and (filter_license  is null or r.license   = any(filter_license))
    and (filter_language is null or r.languages = any(filter_language))
    and (filter_category is null or r.original_category = filter_category)
  order by r.embedding <=> query_embedding
  limit match_count;
$$;
