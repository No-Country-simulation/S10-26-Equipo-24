-- OpenBridge · 02 · Esquema vectorial de la tabla `repositories`
-- Ejecutar en el SQL Editor de Supabase. Es idempotente: se puede correr más de una vez sin romper nada.
--
-- Qué hace:
--   1) Se asegura de que pgvector esté activo.
--   2) Agrega 3 columnas a repositories: topics, embedding_text, embedding_model.
--   3) Fija la dimensión de `embedding` en 384 (modelo local paraphrase-multilingual-MiniLM-L12-v2).
--   4) Crea el índice HNSW (distancia coseno).
--
-- IMPORTANTE: el 384 tiene que coincidir con EMBEDDING_DIM en config.py.
-- Si algún día cambian de modelo, hay que vaciar la columna, cambiar este número y regenerar los embeddings.

-- 1) Extensión (si ya estaba activa, no hace nada)
create extension if not exists vector;

-- 2) Columnas nuevas
--    topics          : topics de GitHub (señal semántica fuerte). Los carga cargar_topics.py.
--    embedding_text  : el texto exacto que se convirtió en vector. Sirve para depurar y para saber si hay que re-embeber.
--    embedding_model : con qué modelo se generó cada vector (evita mezclar modelos sin darse cuenta).
alter table public.repositories add column if not exists topics          text[];
alter table public.repositories add column if not exists embedding_text  text;
alter table public.repositories add column if not exists embedding_model text;

-- 3) Dimensión de la columna `embedding`
--    Hoy es `vector` sin dimensión. Para crear el índice necesita una dimensión fija.
--    Protección: si ya hubiera vectores de otra dimensión, frena en vez de borrarlos.
do $$
declare
  tipo_actual text;
begin
  select format_type(a.atttypid, a.atttypmod)
    into tipo_actual
    from pg_attribute a
   where a.attrelid = 'public.repositories'::regclass
     and a.attname  = 'embedding'
     and not a.attisdropped;

  if tipo_actual is null then
    raise exception 'La tabla repositories no tiene la columna embedding.';
  elsif tipo_actual = 'vector(384)' then
    raise notice 'embedding ya es vector(384): no se cambia nada.';
  elsif exists (select 1 from public.repositories where embedding is not null) then
    raise exception
      'embedding es % y tiene vectores cargados. Para cambiar la dimensión primero vaciala: update public.repositories set embedding = null, embedding_text = null, embedding_model = null;',
      tipo_actual;
  else
    alter table public.repositories alter column embedding type vector(384);
    raise notice 'embedding pasó de % a vector(384).', tipo_actual;
  end if;
end
$$;

-- 4) Índice HNSW para búsqueda por similitud coseno.
--    Con ~100 repos una búsqueda exacta ya es instantánea y el índice no se nota,
--    pero queda listo para cuando el catálogo crezca.
create index if not exists repositories_embedding_idx
  on public.repositories using hnsw (embedding vector_cosine_ops);


-- ---------------------------------------------------------------------------------------------
-- VERIFICACIÓN (opcional): descomentá y corré estas consultas para comprobar el resultado.
-- ---------------------------------------------------------------------------------------------

-- a) ¿Existen las columnas nuevas y qué tipo tiene embedding?
-- select column_name, udt_name, data_type
--   from information_schema.columns
--  where table_schema = 'public' and table_name = 'repositories'
--    and column_name in ('topics', 'embedding_text', 'embedding_model', 'embedding');
--
-- select format_type(atttypid, atttypmod) as tipo_embedding
--   from pg_attribute
--  where attrelid = 'public.repositories'::regclass and attname = 'embedding';   -- esperado: vector(384)

-- b) ¿Cuántos repos ya tienen embedding? (después de correr generar_embeddings.py)
-- select count(*) filter (where embedding is not null) as con_embedding, count(*) as total
--   from public.repositories;

-- c) Revisar las políticas de acceso (RLS) de la tabla, para coordinar con el equipo.
--    Lo esperado: lectura pública para el catálogo y escritura solo con la service key (que ignora RLS).
-- select tablename, rowsecurity from pg_tables where schemaname = 'public' and tablename = 'repositories';
-- select policyname, cmd, roles from pg_policies where schemaname = 'public' and tablename = 'repositories';
