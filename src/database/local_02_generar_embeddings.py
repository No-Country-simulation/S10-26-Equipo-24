"""
OpenBridge · Paso 2 (versión local): generar embeddings y guardarlos en archivos (embeddings_local/).

Reemplaza a 03_generar_embeddings.py (que escribía en Supabase).

Uso:
    python 02_generar_embeddings.py catalogo_actualizado.csv                     # OpenAI (necesita OPENAI_API_KEY)
    python 02_generar_embeddings.py catalogo_actualizado.csv --provider local    # gratis, corre en tu máquina
    python 02_generar_embeddings.py catalogo_actualizado.csv --dry-run           # solo muestra textos y costo estimado

Importante: la búsqueda (paso 3) usa automáticamente el mismo proveedor con el que generaste los embeddings.
Si cambiás de proveedor, hay que volver a correr este paso.
"""
import argparse

from local_openbridge import DIR_INDICE, PROVIDERS, build_text, cargar_catalogo, embed_textos, guardar_indice

ap = argparse.ArgumentParser()
ap.add_argument("archivo", help="CSV o Excel del catálogo")
ap.add_argument("--provider", choices=list(PROVIDERS), default="openai")
ap.add_argument("--dir", default=str(DIR_INDICE), help="carpeta donde guardar los embeddings")
ap.add_argument("--dry-run", action="store_true", help="no llama a ningún modelo")
args = ap.parse_args()

cat = cargar_catalogo(args.archivo)
textos = [build_text(r) for _, r in cat.iterrows()]
tokens = sum(len(t) for t in textos) // 4  # aproximación: ~4 caracteres por token
print(f"{len(textos)} repos | ~{tokens:,} tokens | modelo: {PROVIDERS[args.provider]}")

if args.dry_run:
    for t in textos[:3]:
        print("\n" + "-" * 60 + "\n" + t)
else:
    vectores = embed_textos(textos, args.provider)
    guardar_indice(cat, textos, vectores, args.provider, args.dir)
    print(f"Listo: {vectores.shape[0]} vectores de {vectores.shape[1]} dimensiones guardados en {args.dir}/")
