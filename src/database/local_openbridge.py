"""
OpenBridge · funciones compartidas para probar la búsqueda semántica SIN base de datos.

- Lee el catálogo desde un CSV o Excel (.xlsx).
- Guarda los embeddings en archivos locales (carpeta embeddings_local/).
- Replica la lógica de la función SQL `match_repositories` con numpy/pandas.

Dependencias:
    pip install pandas numpy openpyxl          # openpyxl solo si usás .xlsx
    pip install openai                         # proveedor "openai"
    pip install sentence-transformers          # proveedor "local" (gratis, sin API key)
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

DIR_INDICE = Path("embeddings_local")
BATCH = 50

# proveedor -> modelo. Cada uno produce vectores de distinta dimensión: no se pueden mezclar.
PROVIDERS = {
    "openai": "text-embedding-3-small",                # 1536 dims
    "local": "paraphrase-multilingual-MiniLM-L12-v2",  # 384 dims; entiende español e inglés
}

# Topics de GitHub que no aportan significado al embedding.
TOPICS_RUIDO = {
    "hacktoberfest", "hacktoberfest2021", "hacktoberfest2022", "hacktoberfest2023",
    "hacktoberfest2024", "hacktoberfest2025", "awesome", "good-first-issue",
    "help-wanted", "open-source", "opensource",
}

COLUMNAS_OBLIGATORIAS = ["nombre_completo", "categoria_busqueda", "descripcion", "lenguaje", "topics"]


# ----------------------------------------------------------------------------------------------
# Carga y normalización del catálogo
# ----------------------------------------------------------------------------------------------
def parsear_topics(valor) -> list[str]:
    """'api, webhook, queue' -> ['api', 'webhook', 'queue']"""
    if pd.isna(valor):
        return []
    return [t.strip() for t in str(valor).split(",") if t.strip()]


def _primero(df: pd.DataFrame, *cols: str) -> pd.Series:
    """Valor de la primera columna que lo tenga; si es NaN, usa la siguiente.
    Ej.: _primero(df, 'stars_actual', 'stars') prefiere el dato refrescado y cae al original."""
    serie = pd.Series([None] * len(df), index=df.index, dtype="object")
    for c in cols:
        if c in df.columns:
            serie = serie.where(serie.notna(), df[c])
    return serie


def _a_bool(serie: pd.Series) -> pd.Series:
    return serie.map(lambda v: str(v).strip().lower() in {"1", "1.0", "true", "verdadero", "si", "sí"})


def _a_fecha(serie: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(serie, utc=True, format="ISO8601", errors="coerce")
    except (ValueError, TypeError):  # pandas viejo sin soporte de ISO8601
        return pd.to_datetime(serie, utc=True, errors="coerce")


def cargar_catalogo(ruta) -> pd.DataFrame:
    """Lee el CSV/Excel y devuelve un DataFrame con los mismos nombres de columna que la tabla
    `repositories` de Supabase (full_name, description, languages, license, ...), para que después
    sea fácil pasar a la base."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No encuentro el archivo: {ruta}")
    if ruta.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(ruta)
    else:
        df = pd.read_csv(ruta)

    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Al archivo le faltan columnas obligatorias: {faltan}")

    ultima = _a_fecha(_primero(df, "ultima_actividad_actual", "ultima_actividad"))
    ahora = pd.Timestamp.now(tz="UTC")

    cat = pd.DataFrame({
        "full_name": df["nombre_completo"].astype(str).str.strip(),
        "original_category": df["categoria_busqueda"],
        "description": df["descripcion"].fillna("").astype(str).str.strip(),
        "languages": df["lenguaje"],
        "license": _primero(df, "licencia_actual", "licencia"),
        "topics": df["topics"].map(parsear_topics),
        "stars": pd.to_numeric(_primero(df, "stars_actual", "stars"), errors="coerce"),
        "forks": pd.to_numeric(_primero(df, "forks_actual", "forks"), errors="coerce"),
        "open_issues_y_prs": pd.to_numeric(
            _primero(df, "issues_y_pr_abiertos_actual", "issues_y_pr_abiertos"), errors="coerce"),
        "commits_90d": pd.to_numeric(
            _primero(df, "commits_90d_observados_actual", "commits_90d"), errors="coerce"),
        "archived": _a_bool(_primero(df, "archivado_actual", "archivado")),
        "last_activity": ultima,
        # Se recalcula con la fecha de hoy: la columna original quedó fija al momento de la descarga.
        "dias_sin_actividad": (ahora - ultima).dt.days,
        "html_url": df["url"] if "url" in df.columns else None,
    })
    return cat.reset_index(drop=True)


def _txt(valor, defecto: str) -> str:
    return defecto if pd.isna(valor) or str(valor).strip() == "" else str(valor).strip()


def build_text(r) -> str:
    """Texto que representa el *significado* del repo (lo que se convierte en vector).

    Incluye: nombre, categoría, lenguaje, descripción y topics.
    NO incluye números (stars, commits...): sirven para filtrar/ordenar, no como semántica.
    """
    topics = ", ".join(t for t in r["topics"] if t.lower() not in TOPICS_RUIDO)
    partes = [
        r["full_name"],
        f"Categoría: {_txt(r['original_category'], 'sin categoría')}",
        f"Lenguaje: {_txt(r['languages'], 'n/d')}",
        f"Descripción: {r['description']}",
    ]
    if topics:
        partes.append(f"Topics: {topics}")
    return "\n".join(partes)


def diagnostico(cat: pd.DataFrame) -> None:
    """Reporte rápido de calidad de datos antes de generar embeddings."""
    print(f"Repos: {len(cat)} | nombres duplicados: {cat.full_name.duplicated().sum()}")
    print("\nRepos por categoría:")
    print(cat.original_category.value_counts().to_string())

    chequeos = {
        "sin descripción": cat[cat.description == ""],
        "descripción muy corta (<40 caracteres)": cat[(cat.description != "") & (cat.description.str.len() < 40)],
        "sin lenguaje": cat[cat.languages.isna()],
        "sin licencia": cat[cat.license.isna()],
        "sin topics": cat[cat.topics.map(len) == 0],
        "sin dato de commits_90d": cat[cat.commits_90d.isna()],
        "archivados (se excluyen de la búsqueda)": cat[cat.archived],
        "sin actividad hace más de 365 días": cat[cat.dias_sin_actividad > 365],
    }
    print("\nChequeos:")
    for nombre, filas in chequeos.items():
        detalle = f": {', '.join(filas.full_name)}" if 0 < len(filas) <= 5 else ""
        print(f"  {nombre:<42} {len(filas):>3}{detalle}")

    lens = cat.apply(build_text, axis=1).str.len()
    print(f"\nLargo del texto a embeber (caracteres): mín {lens.min()} | prom {int(lens.mean())} | máx {lens.max()}")


# ----------------------------------------------------------------------------------------------
# Embeddings
# ----------------------------------------------------------------------------------------------
_modelos_locales: dict = {}


def embed_textos(textos: list[str], provider: str) -> np.ndarray:
    """Devuelve una matriz (n, dims) float32 con vectores normalizados (norma 1),
    de modo que el producto punto equivale a la similitud coseno."""
    if provider not in PROVIDERS:
        raise ValueError(f"Proveedor desconocido: {provider}. Opciones: {list(PROVIDERS)}")
    modelo = PROVIDERS[provider]

    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY (o usá --provider local).")
        from openai import OpenAI

        cliente = OpenAI()
        vecs: list = []
        for i in range(0, len(textos), BATCH):
            resp = cliente.embeddings.create(model=modelo, input=textos[i : i + BATCH])
            vecs += [d.embedding for d in resp.data]
        arr = np.array(vecs, dtype=np.float32)
    else:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError("Falta instalar: pip install sentence-transformers") from e
        if modelo not in _modelos_locales:
            m = SentenceTransformer(modelo)
            m.max_seq_length = 256  # por defecto corta en 128 tokens y perdería parte de los topics
            _modelos_locales[modelo] = m
        arr = np.asarray(_modelos_locales[modelo].encode(textos, show_progress_bar=False), dtype=np.float32)

    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


# ----------------------------------------------------------------------------------------------
# Almacenamiento local de los embeddings
# ----------------------------------------------------------------------------------------------
def guardar_indice(cat, textos, vectores, provider, directorio=DIR_INDICE) -> None:
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    np.save(directorio / "vectors.npy", vectores)
    meta = {
        "provider": provider,
        "model": PROVIDERS[provider],
        "dims": int(vectores.shape[1]),
        "creado": pd.Timestamp.now(tz="UTC").isoformat(),
        "full_names": cat.full_name.tolist(),
        "textos": textos,
    }
    (directorio / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def cargar_indice(directorio=DIR_INDICE):
    directorio = Path(directorio)
    if not (directorio / "vectors.npy").exists():
        raise FileNotFoundError("Todavía no hay embeddings: corré primero 02_generar_embeddings.py")
    vectores = np.load(directorio / "vectors.npy")
    meta = json.loads((directorio / "meta.json").read_text(encoding="utf-8"))
    return vectores, meta


# ----------------------------------------------------------------------------------------------
# Búsqueda (equivalente a la función SQL match_repositories)
# ----------------------------------------------------------------------------------------------
def buscar(
    consulta: str,
    cat: pd.DataFrame,
    vectores: np.ndarray,
    meta: dict,
    k: int = 8,
    licencias: list[str] | None = None,
    lenguajes: list[str] | None = None,
    categoria: str | None = None,
    min_stars: int = 0,
    max_dias_inactividad: int | None = None,
    incluir_archivados: bool = False,
) -> pd.DataFrame:
    """Top-k repos más parecidos a la consulta, con filtros duros.

    Nota: el CSV no trae `health_score`, así que en lugar de `min_health` se filtra por
    estrellas mínimas y días máximos sin actividad."""
    if cat.full_name.tolist() != meta["full_names"]:
        raise ValueError("El catálogo cambió desde que se generaron los embeddings. Corré de nuevo 02_generar_embeddings.py")

    q = embed_textos([consulta], meta["provider"])[0]
    similitud = vectores @ q

    mask = pd.Series(True, index=cat.index)
    if not incluir_archivados:
        mask &= ~cat.archived
    if licencias:
        mask &= cat.license.str.lower().isin([x.lower() for x in licencias])
    if lenguajes:
        mask &= cat.languages.str.lower().isin([x.lower() for x in lenguajes])
    if categoria:
        mask &= cat.original_category.str.lower() == categoria.lower()
    if min_stars:
        mask &= cat.stars.fillna(0) >= min_stars
    if max_dias_inactividad is not None:
        mask &= cat.dias_sin_actividad <= max_dias_inactividad

    res = cat.assign(similarity=similitud)[mask]
    return res.sort_values("similarity", ascending=False).head(k)
