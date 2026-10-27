"""
OpenBridge · Paso 3: generar embeddings de los repos y probar la búsqueda semántica.

Uso:
    pip install openai supabase
    export SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...  OPENAI_API_KEY=...

    python 03_generar_embeddings.py --dry-run          # muestra los textos que se van a embeber (no llama a ninguna API)
    python 03_generar_embeddings.py                    # embebe solo los repos sin embedding
    python 03_generar_embeddings.py --all              # re-embebe todo (tras cambiar build_text o el modelo)
    python 03_generar_embeddings.py --probar "pasarela de cobros para marketplace"
    python 03_generar_embeddings.py --evaluar          # corre un set de consultas de negocio para revisar a ojo
"""
import argparse
import os

MODEL = "text-embedding-3-small"  # 1536 dims; debe coincidir con vector(1536) del SQL
BATCH = 50

# Topics de GitHub que no aportan significado al embedding.
TOPICS_RUIDO = {"hacktoberfest", "hacktoberfest2021", "hacktoberfest2022", "hacktoberfest2023", "hacktoberfest2024",
                "hacktoberfest2025", "awesome", "good-first-issue", "help-wanted", "open-source", "opensource"}

# Consultas para revisar a ojo si el retrieval tiene sentido (punto 5 de la ruta: evaluar).
CONSULTAS_EVAL = [
    "Estoy construyendo un e-commerce B2B de logística",
    "Necesito cobrar suscripciones y manejar facturación",
    "Quiero un buscador con autocompletado y tolerancia a errores de tipeo",
    "Autenticación con login social y SSO para empresas",
    "Monitorear la salud y las métricas de mis microservicios",
    "Procesar eventos y colas de mensajes entre servicios",
    "Agregar un asistente con modelos de lenguaje que corra en mi propio servidor",
    "Dashboards de ventas para el equipo comercial",
]


def get_clients():
    from openai import OpenAI
    from supabase import create_client

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    return sb, OpenAI()


def build_text(r: dict) -> str:
    """Texto que representa el *significado* del repo.

    Incluimos: nombre, categoría, lenguaje, descripción y topics.
    NO incluimos números (stars, health_score...): se usan para filtrar/ordenar, no como semántica.
    NO incluimos problem_solved / use_cases / consideraciones_integracion: hoy son texto genérico
    (idéntico en los 100 repos, o una copia de la descripción) y solo agregan ruido.
    NO incluimos resource_type: vale "Herramienta" en todos.
    """
    topics = ", ".join(t for t in (r.get("topics") or []) if t.lower() not in TOPICS_RUIDO)
    partes = [
        r["full_name"],
        f"Categoría: {r.get('original_category') or 'sin categoría'}",
        f"Lenguaje: {r.get('languages') or 'n/d'}",
        f"Descripción: {r.get('description') or ''}",
    ]
    if topics:
        partes.append(f"Topics: {topics}")
    # Cuando haya una ficha semántica generada con LLM, agregarla acá:
    # if r.get("semantic_summary"): partes.append(f"Resumen: {r['semantic_summary']}")
    return "\n".join(partes)


def embed(oai, textos: list[str]) -> list[list[float]]:
    resp = oai.embeddings.create(model=MODEL, input=textos)
    return [d.embedding for d in resp.data]


def cargar_repos(sb, todos: bool) -> list[dict]:
    q = sb.table("repositories").select("*")
    if not todos:
        q = q.is_("embedding", "null")
    return q.execute().data


def dry_run(todos: bool, n: int = 3) -> None:
    from supabase import create_client  # dry-run no necesita OpenAI ni su API key

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    repos = cargar_repos(sb, todos)
    sin_desc = [r["full_name"] for r in repos if not r.get("description")]
    sin_topics = [r["full_name"] for r in repos if not r.get("topics")]
    print(f"{len(repos)} repos a embeber | sin descripción: {len(sin_desc)} | sin topics: {len(sin_topics)}")
    if sin_topics:
        print("⚠ Hay repos sin topics: corré 02_backfill_topics.py primero.")
    for r in repos[:n]:
        print("\n" + "-" * 60 + "\n" + build_text(r))


def indexar(todos: bool) -> None:
    sb, oai = get_clients()
    repos = cargar_repos(sb, todos)
    print(f"{len(repos)} repos a embeber")

    for i in range(0, len(repos), BATCH):
        lote = repos[i : i + BATCH]
        textos = [build_text(r) for r in lote]
        vectores = embed(oai, textos)
        for r, texto, vec in zip(lote, textos, vectores):
            sb.table("repositories").update(
                {"embedding": vec, "embedding_text": texto, "embedding_model": MODEL}
            ).eq("id", r["id"]).execute()
        print(f"  {min(i + BATCH, len(repos))}/{len(repos)}")


def buscar(sb, oai, consulta: str, k: int = 8) -> list[dict]:
    vec = embed(oai, [consulta])[0]
    return sb.rpc(
        "match_repositories",
        {"query_embedding": vec, "match_count": k, "min_health": 0},
    ).execute().data


def imprimir(consulta: str, res: list[dict]) -> None:
    print(f"\nConsulta: {consulta}\n")
    for r in res:
        print(
            f"  {r['similarity']:.3f} | {r['full_name']:<38} | {r['original_category']:<24} "
            f"| {r['languages']} | health={r['health_score']}"
        )


def probar(consulta: str) -> None:
    sb, oai = get_clients()
    imprimir(consulta, buscar(sb, oai, consulta))


def evaluar() -> None:
    sb, oai = get_clients()
    for consulta in CONSULTAS_EVAL:
        imprimir(consulta, buscar(sb, oai, consulta, k=5))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="re-embeber todos los repos")
    ap.add_argument("--dry-run", action="store_true", help="mostrar los textos a embeber sin llamar a OpenAI")
    ap.add_argument("--probar", metavar="TEXTO", help="buscar repos similares a este texto")
    ap.add_argument("--evaluar", action="store_true", help="correr el set de consultas de prueba")
    args = ap.parse_args()

    if args.dry_run:
        dry_run(args.all)
    elif args.probar:
        probar(args.probar)
    elif args.evaluar:
        evaluar()
    else:
        indexar(args.all)
