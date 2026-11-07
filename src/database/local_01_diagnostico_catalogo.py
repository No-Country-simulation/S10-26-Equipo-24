"""
OpenBridge · Paso 1 (versión local): leer el catálogo y revisar la calidad de los datos.

Reemplaza a 01_pgvector.sql y 02_backfill_topics.py: acá no hay base que preparar; los topics ya se
parsean al leer el archivo. Sirve para detectar problemas ANTES de generar embeddings.

Uso:
    python 01_diagnostico_catalogo.py catalogo_actualizado.csv
    python 01_diagnostico_catalogo.py catalogo_actualizado.csv --ver 3     # muestra 3 textos a embeber
"""
import argparse

from local_openbridge import build_text, cargar_catalogo, diagnostico

ap = argparse.ArgumentParser()
ap.add_argument("archivo", help="CSV o Excel del catálogo")
ap.add_argument("--ver", type=int, default=2, help="cuántos textos de ejemplo mostrar (default 2)")
args = ap.parse_args()

cat = cargar_catalogo(args.archivo)
diagnostico(cat)

print("\nEjemplos del texto que se va a embeber:")
for _, fila in cat.head(args.ver).iterrows():
    print("\n" + "-" * 60 + "\n" + build_text(fila))
