"""
OpenBridge · búsqueda semántica sobre Supabase, con conexión directa a Postgres (psycopg2).

Qué hace:
  - Convierte la consulta en un vector con el MISMO modelo local que generó los embeddings del catálogo.
  - Busca en la tabla `repositories` los repos más cercanos (distancia coseno, pgvector).
  - Aplica filtros duros (licencia, lenguaje, categoría, estrellas, inactividad) en la misma consulta SQL.
  - La conexión es de SOLO LECTURA: este script no puede modificar la base.
  - Usa get_conexion_db() de config.py (psycopg2 + DATABASE_URL del .env).
"""
import argparse
import csv
import json
import sys

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    sys.exit("Falta instalar: pip install psycopg2-binary")

from config import EMBEDDING_MAX_SEQ, EMBEDDING_MODEL, get_conexion_db

CONSULTAS_EVAL = [
    "B2B e-commerce platform for logistics and shipment tracking",
    "subscription billing and invoicing",
    "search engine with autocomplete and typo tolerance",
    "authentication with social login and enterprise SSO",
    "monitor metrics and health of microservices",
    "event streaming and message queues between services",
    "run a large language model assistant on my own server",
    "sales dashboards for the commercial team",
]

_modelo = None  # se carga una sola vez, la primera vez que se necesita


def embeber_consulta(texto: str) -> list[float]:
    """Vector de la consulta, con el mismo modelo que se usó para el catálogo."""
    global _modelo
    if _modelo is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError("Falta instalar: pip install sentence-transformers") from e
        _modelo = SentenceTransformer(EMBEDDING_MODEL)
        _modelo.max_seq_length = EMBEDDING_MAX_SEQ
    return _modelo.encode([texto], normalize_embeddings=True, show_progress_bar=False)[0].tolist()


def _vector_sql(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def buscar(
    conn,
    consulta: str,
    k: int = 8,
    licencias: list[str] | None = None,
    lenguajes: list[str] | None = None,
    categoria: str | None = None,
    min_stars: int = 0,
    max_dias_inactividad: int | None = None,
    min_health: float | None = None,
    min_sim: float | None = None,
    incluir_archivados: bool = False,
) -> list[dict]:
    params: dict = {"q": _vector_sql(embeber_consulta(consulta)), "modelo": EMBEDDING_MODEL, "k": k}
    condiciones = ["r.embedding is not null", "r.embedding_model = %(modelo)s"]

    if not incluir_archivados:
        condiciones.append("not coalesce(r.archived, false) and not coalesce(r.disabled, false)")
    if licencias:
        condiciones.append("lower(r.license) = any(%(licencias)s)")
        params["licencias"] = [x.lower() for x in licencias]
    if lenguajes:
        condiciones.append("lower(r.languages) = any(%(lenguajes)s)")
        params["lenguajes"] = [x.lower() for x in lenguajes]
    if categoria:
        condiciones.append("(lower(c.name) = lower(%(categoria)s) or lower(r.original_category) = lower(%(categoria)s))")
        params["categoria"] = categoria
    if min_stars:
        condiciones.append("coalesce(r.stars, 0) >= %(min_stars)s")
        params["min_stars"] = min_stars
    if max_dias_inactividad is not None:
        condiciones.append("r.fecha_ultimo_commit >= now() - make_interval(days => %(max_dias)s)")
        params["max_dias"] = max_dias_inactividad
    if min_health is not None:
        condiciones.append("coalesce(r.health_score, 0) >= %(min_health)s")
        params["min_health"] = min_health

    # Consulta SQL ampliada con columnas ricas para el LLM
    sql = f"""
        select
            r.id, r.github_id, r.full_name,
            c.name as category_name, r.original_category,
            r.languages, r.license, r.description, r.topics,
            r.problem_solved, r.use_cases, r.consideraciones_integracion,
            r.stars, r.forks, r.commits_90d, r.fecha_ultimo_commit, r.health_score, r.html_url,
            date_part('day', now() - r.fecha_ultimo_commit)::int as dias_sin_commit,
            1 - (r.embedding <=> %(q)s::vector) as similarity
        from public.repositories r
        left join public.categories c on c.id = r.category_id
        where {" and ".join(condiciones)}
        order by r.embedding <=> %(q)s::vector
        limit %(k)s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        filas = [dict(r) for r in cur.fetchall()]

    if min_sim is not None:
        filas = [r for r in filas if r["similarity"] >= min_sim]
    return filas


def contar_embebidos(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "select count(*) from public.repositories where embedding is not null and embedding_model = %s",
            (EMBEDDING_MODEL,),
        )
        return cur.fetchone()[0]


def _n(valor, defecto: str = "n/d") -> str:
    return defecto if valor is None else f"{valor:.0f}"


def imprimir(consulta: str, res: list[dict]) -> None:
    print(f"\nConsulta: {consulta}\n")
    if not res:
        print("  (sin resultados con esos filtros)")
        return
    for r in res:
        categoria = r["category_name"] or r["original_category"] or "sin categoría"
        dias = "n/d" if r["dias_sin_commit"] is None else f"{r['dias_sin_commit']}d desde el último commit"
        print(
            f"  {r['similarity']:.3f} | {r['full_name']:<38} | {categoria:<32} | {(r['languages'] or 'n/d'):<10} "
            f"| {(r['license'] or 'n/d'):<12} | ★{_n(r['stars'])} | {dias}"
        )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Búsqueda semántica en Supabase (psycopg2)")
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--probar", metavar="TEXTO", help="buscar repos parecidos a este texto (en inglés)")
    grupo.add_argument("--evaluar", action="store_true", help="correr el set de consultas de prueba")
    ap.add_argument("-k", type=int, default=8, help="cantidad de resultados (default 8)")
    ap.add_argument("--licencia", nargs="+", help="ej.: MIT Apache-2.0")
    ap.add_argument("--lenguaje", nargs="+", help="ej.: Go Python")
    ap.add_argument("--categoria", help='ej.: "Monitoreo & Observabilidad" (nombre en la tabla categories)')
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--max-dias-inactividad", type=int, help="descarta repos con último commit de hace más de N días")
    ap.add_argument("--min-health", type=float, help="health_score mínimo (apagado por defecto)")
    ap.add_argument("--min-sim", type=float, help="similitud mínima (ej. 0.35) para descartar resultados flojos")
    ap.add_argument("--incluir-archivados", action="store_true")
    ap.add_argument("--json", action="store_true", help="imprimir los resultados como JSON (solo con --probar)")
    args = ap.parse_args(argv)

    salida_info = sys.stderr if args.json else sys.stdout

    try:
        conn = get_conexion_db()
    except RuntimeError as e:
        sys.exit(str(e))
    except psycopg2.OperationalError as e:
        sys.exit(
            "No pude conectarme a la base. Revisá DATABASE_URL en el .env.\n"
            f"Detalle: {str(e).strip()}"
        )

    conn.set_session(readonly=True, autocommit=True)
    try:
        n = contar_embebidos(conn)
        print(f"Conectado. Repos con embedding de {EMBEDDING_MODEL}: {n}", file=salida_info)
        if n == 0:
            sys.exit("No hay repos con embeddings de este modelo. Corré generar_embeddings.py antes de buscar.")

        filtros = dict(
            licencias=args.licencia, lenguajes=args.lenguaje, categoria=args.categoria,
            min_stars=args.min_stars, max_dias_inactividad=args.max_dias_inactividad,
            min_health=args.min_health, min_sim=args.min_sim, incluir_archivados=args.incluir_archivados,
        )

        if args.probar:
            res = buscar(conn, args.probar, k=args.k, **filtros)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
            else:
                imprimir(args.probar, res)
        else:
            filas = []
            for consulta in CONSULTAS_EVAL:
                res = buscar(conn, consulta, k=5, **filtros)
                imprimir(consulta, res)
                for pos, r in enumerate(res, start=1):
                    filas.append({
                        "consulta": consulta, "posicion": pos, "repo": r["full_name"],
                        "categoria": r["category_name"] or r["original_category"],
                        "similarity": round(float(r["similarity"]), 4),
                    })
            with open("resultados_evaluacion.csv", "w", newline="", encoding="utf-8-sig") as f:
                escritor = csv.DictWriter(f, fieldnames=["consulta", "posicion", "repo", "categoria", "similarity"])
                escritor.writeheader()
                escritor.writerows(filas)
            print("\nResultados guardados en resultados_evaluacion.csv")
    finally:
        conn.close()


if __name__ == "__main__":
    main()