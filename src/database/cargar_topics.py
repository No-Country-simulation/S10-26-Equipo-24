"""
OpenBridge · carga los `topics` del CSV en la columna repositories.topics.

- Actualiza filas existentes (UPDATE por id). NUNCA borra ni inserta filas.
- Busca cada repo por github_id y, si no lo encuentra, por full_name.
- Solo toca la columna `topics`; no modifica el resto de la tabla ni el embedding.
- Si un repo no trae topics en el CSV, no pisa lo que ya hubiera en la base.

Uso:
    python cargar_topics.py data/catalogo_actualizado.csv --dry-run   # muestra qué haría, sin escribir
    python cargar_topics.py data/catalogo_actualizado.csv             # carga

Requisito: haber corrido antes 02_esquema_vectores.sql (crea la columna topics).
"""
import argparse
import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

# El CSV de catálogo usa repo_id / nombre_completo; el de integraciones usa github_id / full_name.
OPCIONES_ID = ("github_id", "repo_id")
OPCIONES_NOMBRE = ("full_name", "nombre_completo")


def _columna(df: pd.DataFrame, opciones: tuple[str, ...]) -> str | None:
    return next((c for c in opciones if c in df.columns), None)


def _a_entero(valor) -> int | None:
    try:
        return None if pd.isna(valor) else int(valor)
    except (TypeError, ValueError):
        return None


def parsear_topics(valor) -> list[str]:
    """Convierte el string de topics del CSV en una lista de strings limpia."""
    if pd.isna(valor) or not str(valor).strip():
        return []
    # Si viene separado por comas
    if isinstance(valor, str):
        return [t.strip() for t in valor.replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(",") if t.strip()]
    return []


def main(ruta_csv: str, dry_run: bool) -> None:
    if not DATABASE_URL:
        sys.exit("❌ Falta configurar DATABASE_URL en el archivo .env")

    df = pd.read_csv(ruta_csv)
    col_id = _columna(df, OPCIONES_ID)
    col_nombre = _columna(df, OPCIONES_NOMBRE)
    
    if "topics" not in df.columns:
        sys.exit("El CSV no tiene la columna 'topics'.")
    if col_id is None and col_nombre is None:
        sys.exit(f"El CSV necesita al menos una de estas columnas: {OPCIONES_ID + OPCIONES_NOMBRE}")

    print("🔌 Conectando a Supabase PostgreSQL...")
    conn = psycopg2.connect(
        DATABASE_URL,
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "15")),
        sslmode=os.getenv("DB_SSLMODE", "require")
    )
    cur = conn.cursor()

    try:
        # Traer todos los repos de la base de datos usando SQL directo
        cur.execute("SELECT id, github_id, full_name, topics FROM repositories;")
        rows = cur.fetchall()
        
        repos = []
        for r in rows:
            repos.append({
                "id": r[0],
                "github_id": r[1],
                "full_name": r[2],
                "topics": r[3]
            })

        por_github_id = {r["github_id"]: r for r in repos if r.get("github_id") is not None}
        por_nombre: dict[str, list[dict]] = {}
        for r in repos:
            nombre_repo = r.get("full_name")
            if nombre_repo:
                por_nombre.setdefault(nombre_repo.strip().lower(), []).append(r)

        stats = {"actualizados": 0, "sin_cambios": 0, "sin_topics_en_csv": 0, "errores": 0}
        por_id_gh = por_nombre_n = 0
        no_encontrados: list[str] = []
        ambiguos: list[str] = []
        vistos: set[str] = set()

        for _, fila in df.iterrows():
            nombre = str(fila[col_nombre]).strip() if col_nombre else f"(github_id {fila[col_id]})"
            topics = parsear_topics(fila["topics"])
            if not topics:
                stats["sin_topics_en_csv"] += 1
                continue

            # 1) Buscar el repo en la base: primero por github_id, respaldo por full_name
            repo = None
            gh_id = _a_entero(fila[col_id]) if col_id else None
            if gh_id is not None and gh_id in por_github_id:
                repo, por_id_gh = por_github_id[gh_id], por_id_gh + 1
            elif col_nombre:
                candidatos = por_nombre.get(nombre.lower(), [])
                if len(candidatos) == 1:
                    repo, por_nombre_n = candidatos[0], por_nombre_n + 1
                elif len(candidatos) > 1:
                    ambiguos.append(nombre)
                    continue
            
            if repo is None:
                no_encontrados.append(nombre)
                continue
            vistos.add(repo["id"])

            # 2) Actualizar solo si cambió
            topics_actuales = repo.get("topics") or []
            if set(topics_actuales) == set(topics):
                stats["sin_cambios"] += 1
                continue

            if dry_run:
                stats["actualizados"] += 1
                continue

            try:
                # Actualización directa por SQL usando psycopg2
                cur.execute(
                    "UPDATE repositories SET topics = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                    (topics, repo["id"])
                )
                stats["actualizados"] += 1
            except Exception as e:
                stats["errores"] += 1
                print(f"  ERROR en {nombre}: {e}")

        if not dry_run:
            conn.commit()

        # ---- resumen ----
        print(f"\n{'[DRY-RUN] ' if dry_run else ''}Resumen sobre {len(df)} filas del CSV y {len(repos)} repos en la base:")
        print(f"  Actualizados{' (se actualizarían)' if dry_run else ''}: {stats['actualizados']}")
        print(f"  Sin cambios (ya tenían esos topics):  {stats['sin_cambios']}")
        print(f"  Sin topics en el CSV (no se tocan):   {stats['sin_topics_en_csv']}")
        print(f"  Encontrados por github_id: {por_id_gh} | por full_name: {por_nombre_n}")
        if stats["errores"]:
            print(f"  Errores al escribir: {stats['errores']}")
        if ambiguos:
            print(f"  Ambiguos (full_name repetido en la base, se omiten): {ambiguos[:10]}")
        if no_encontrados:
            print(f"  Del CSV pero NO están en la base ({len(no_encontrados)}): {no_encontrados[:10]}"
                  f"{' ...' if len(no_encontrados) > 10 else ''}")

    except Exception as e:
        if conn:
            conn.rollback()
        sys.exit(f"Error procesando la base de datos: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Carga los topics del CSV en repositories.topics usando PostgreSQL directo")
    ap.add_argument("archivo", help="CSV del catálogo")
    ap.add_argument("--dry-run", action="store_true", help="no escribe en la base")
    args = ap.parse_args()
    main(args.archivo, args.dry_run)