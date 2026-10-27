"""
OpenBridge · Paso 2: cargar los `topics` del CSV en Supabase y verificar que la base tenga datos completos.

Los topics de GitHub no estaban en la tabla `repositories` y son de las mejores señales semánticas.
Este script los carga haciendo match por full_name, y de paso avisa si la base quedó con datos incompletos
(por ejemplo, si se cargó una versión vieja del CSV).

Uso:
    pip install supabase pandas
    export SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...
    python 02_backfill_topics.py catalogo_enriquecido_100_1.csv
"""
import os
import sys

import pandas as pd
from supabase import create_client


def parsear_topics(valor) -> list[str]:
    """'api, webhook, queue' -> ['api', 'webhook', 'queue']"""
    if pd.isna(valor):
        return []
    return [t.strip() for t in str(valor).split(",") if t.strip()]


def main(ruta_csv: str) -> None:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    df = pd.read_csv(ruta_csv)

    # 1) Backfill de topics
    no_encontrados = []
    for _, fila in df.iterrows():
        res = (
            sb.table("repositories")
            .update({"topics": parsear_topics(fila["topics"])})
            .eq("full_name", fila["nombre_completo"])
            .execute()
        )
        if not res.data:
            no_encontrados.append(fila["nombre_completo"])

    print(f"Topics cargados: {len(df) - len(no_encontrados)}/{len(df)}")
    if no_encontrados:
        print("No están en la base (¿se cargó otro CSV?):")
        for n in no_encontrados:
            print("  -", n)

    # 2) Diagnóstico: ¿la base tiene los datos completos del CSV?
    filas = sb.table("repositories").select("description, license, languages, issues_abiertos").execute().data
    total = len(filas)
    sin_desc = sum(1 for f in filas if not f["description"])
    sin_lic = sum(1 for f in filas if not f["license"])
    print(f"\nEn la base hay {total} repos: {sin_desc} sin descripción, {sin_lic} sin licencia.")
    if sin_desc > 5:
        print("⚠ Muchos repos sin descripción: la base probablemente tiene un CSV viejo/incompleto.")
        print("  Recargá la tabla con el CSV completo antes de generar embeddings.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python 02_backfill_topics.py <archivo.csv>")
    main(sys.argv[1])