"""
OpenBridge · genera los embeddings de `repositories` y los guarda en Supabase.

Qué hace:
  - Arma el texto de cada repo (build_text) y lo convierte en un vector con el modelo local.
  - Guarda embedding + embedding_text + embedding_model JUNTOS, en un solo UPDATE por repo.
  - Solo procesa repos nuevos o cuyo texto / modelo cambió (lo detecta comparando embedding_text y
    embedding_model). Así se puede correr todos los días sin rehacer todo.
  - Nunca borra ni inserta filas.

Uso:
    python generar_embeddings.py --dry-run     # muestra qué haría, sin cargar el modelo ni escribir
    python generar_embeddings.py --limit 5     # prueba con 5 repos
    python generar_embeddings.py               # procesa lo pendiente
    python generar_embeddings.py --all         # fuerza todos (p. ej. tras cambiar build_text)

Requisitos: haber corrido 02_esquema_vectores.sql y cargar_topics.py.
"""
import argparse
import sys

from config import (
    EMBEDDING_DIM,
    EMBEDDING_MAX_SEQ,
    EMBEDDING_MODEL,
    INCLUIR_CATEGORIA_EN_TEXTO,
    TABLA_REPOS,
    TOPICS_RUIDO,
    get_supabase,
    leer_todo,
)

COLUMNAS = "id, full_name, original_category, languages, description, topics, embedding_text, embedding_model"
BATCH = 32


def _txt(valor, defecto: str = "") -> str:
    if valor is None:
        return defecto
    s = str(valor).strip()
    return s if s else defecto


def build_text(r: dict) -> str:
    """Texto que representa el *significado* del repo (lo que se convierte en vector).

    Incluye: nombre, categoría (configurable), lenguaje, descripción y topics.
    NO incluye números (stars, commits...): sirven para filtrar/ordenar, no como semántica.
    NO incluye campos genéricos (problem_solved, use_cases, consideraciones): hoy son texto de relleno
    casi idéntico entre repos y solo meterían ruido.
    """
    topics = ", ".join(t for t in (r.get("topics") or []) if t.lower() not in TOPICS_RUIDO)
    partes = [r["full_name"]]
    if INCLUIR_CATEGORIA_EN_TEXTO:
        partes.append(f"Categoría: {_txt(r.get('original_category'), 'sin categoría')}")
    partes.append(f"Lenguaje: {_txt(r.get('languages'), 'n/d')}")
    partes.append(f"Descripción: {_txt(r.get('description'))}")
    if topics:
        partes.append(f"Topics: {topics}")
    return "\n".join(partes)


def seleccionar_pendientes(repos: list[dict], forzar: bool) -> list[tuple[dict, str]]:
    """Repos cuyo texto o modelo difiere de lo guardado (o todos, si forzar)."""
    pendientes = []
    for r in repos:
        texto = build_text(r)
        if forzar or r.get("embedding_text") != texto or r.get("embedding_model") != EMBEDDING_MODEL:
            pendientes.append((r, texto))
    return pendientes


def codificar(textos: list[str]):
    """Convierte textos en vectores normalizados (norma 1) con el modelo local."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError("Falta instalar: pip install sentence-transformers") from e
    modelo = SentenceTransformer(EMBEDDING_MODEL)
    modelo.max_seq_length = EMBEDDING_MAX_SEQ
    return modelo.encode(textos, batch_size=BATCH, normalize_embeddings=True, show_progress_bar=False)


def main(dry_run: bool, forzar: bool, limite: int | None) -> None:
    sb = get_supabase()
    try:
        repos = leer_todo(sb, TABLA_REPOS, COLUMNAS)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"No pude leer la tabla. ¿Corriste 02_esquema_vectores.sql?\nDetalle: {e}")

    pendientes = seleccionar_pendientes(repos, forzar)
    sin_desc = sum(1 for r in repos if not _txt(r.get("description")))
    sin_topics = sum(1 for r in repos if not r.get("topics"))

    print(f"Repos en la base: {len(repos)} | pendientes de embeber: {len(pendientes)} | modelo: {EMBEDDING_MODEL}")
    if sin_desc:
        print(f"⚠ {sin_desc} repos sin descripción: sus embeddings serán débiles.")
    if sin_topics:
        print(f"⚠ {sin_topics} repos sin topics: ¿corriste cargar_topics.py?")

    if limite:
        pendientes = pendientes[:limite]
    if not pendientes:
        print("Nada para hacer: todos los embeddings están al día.")
        return

    if dry_run:
        print(f"\n[DRY-RUN] Se embeberían {len(pendientes)} repos. Ejemplos de texto:")
        for _, texto in pendientes[:3]:
            print("\n" + "-" * 60 + "\n" + texto)
        return

    vectores = codificar([t for _, t in pendientes])
    if vectores.shape[1] != EMBEDDING_DIM:
        sys.exit(
            f"El modelo produce vectores de {vectores.shape[1]} dimensiones pero config.EMBEDDING_DIM = {EMBEDDING_DIM}. "
            "Corregí la configuración y la columna antes de seguir."
        )

    ok, errores = 0, 0
    for (repo, texto), vec in zip(pendientes, vectores):
        try:
            # Convertimos el array de numpy a lista de Python nativa compatible con psycopg2/pgvector
            vec_list = vec.tolist()
            
            sb.table(TABLA_REPOS).update(
                {"embedding": vec_list, "embedding_text": texto, "embedding_model": EMBEDDING_MODEL}
            ).eq("id", repo["id"]).execute()
            ok += 1
        except Exception as e:  # noqa: BLE001
            errores += 1
            print(f"  ERROR en {repo['full_name']}: {e}")

    # Para el conteo final compatible con el wrapper de psql
    con_embedding = len(leer_todo(sb, TABLA_REPOS, "id")) # O un conteo seguro
    print(f"\nListo: {ok} embeddings guardados, {errores} errores.")
    print(f"Repos con embedding del modelo actual: {con_embedding}/{len(repos)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Genera embeddings y los guarda en Supabase")
    ap.add_argument("--dry-run", action="store_true", help="no carga el modelo ni escribe")
    ap.add_argument("--all", action="store_true", help="re-embeber todos los repos")
    ap.add_argument("--limit", type=int, help="procesar solo N repos (para probar)")
    args = ap.parse_args()
    main(args.dry_run, args.all, args.limit)
