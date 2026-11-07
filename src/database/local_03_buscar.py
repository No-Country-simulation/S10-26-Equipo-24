"""
OpenBridge · Paso 3 (versión local): búsqueda semántica con filtros y evaluación.

Reemplaza a la función SQL match_repositories y a los modos --probar / --evaluar del script anterior.

Uso:
    python 03_buscar.py catalogo_actualizado.csv --probar "pasarela de cobros para marketplace"
    python 03_buscar.py catalogo_actualizado.csv --probar "login con SSO" --licencia MIT Apache-2.0 --lenguaje Go Java
    python 03_buscar.py catalogo_actualizado.csv --probar "monitoreo" --categoria Monitoreo --min-stars 1000
    python 03_buscar.py catalogo_actualizado.csv --evaluar        # corre 8 consultas y guarda resultados_evaluacion.csv
"""
import argparse

import pandas as pd

from local_openbridge import DIR_INDICE, buscar, cargar_catalogo, cargar_indice

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


def imprimir(consulta: str, res: pd.DataFrame) -> None:
    print(f"\nConsulta: {consulta}\n")
    if res.empty:
        print("  (sin resultados con esos filtros)")
        return
    for _, r in res.iterrows():
        print(
            f"  {r.similarity:.3f} | {r.full_name:<38} | {r.original_category:<24} | {r.languages:<10} "
            f"| {str(r.license):<12} | ★{r.stars:.0f} | {r.dias_sin_actividad:.0f}d sin actividad"
        )


ap = argparse.ArgumentParser()
ap.add_argument("archivo", help="el mismo CSV/Excel usado en el paso 2")
grupo = ap.add_mutually_exclusive_group(required=True)
grupo.add_argument("--probar", metavar="TEXTO", help="buscar repos parecidos a este texto")
grupo.add_argument("--evaluar", action="store_true", help="correr el set de consultas de prueba")
ap.add_argument("-k", type=int, default=8, help="cantidad de resultados (default 8)")
ap.add_argument("--licencia", nargs="+", help="ej.: MIT Apache-2.0")
ap.add_argument("--lenguaje", nargs="+", help="ej.: Go Python")
ap.add_argument("--categoria", help="ej.: Pagos")
ap.add_argument("--min-stars", type=int, default=0)
ap.add_argument("--max-dias-inactividad", type=int, help="descarta repos sin actividad hace más de N días")
ap.add_argument("--incluir-archivados", action="store_true")
ap.add_argument("--dir", default=str(DIR_INDICE), help="carpeta con los embeddings")
args = ap.parse_args()

cat = cargar_catalogo(args.archivo)
vectores, meta = cargar_indice(args.dir)
print(f"Embeddings: {meta['provider']} / {meta['model']} ({meta['dims']} dims)")

filtros = dict(
    licencias=args.licencia,
    lenguajes=args.lenguaje,
    categoria=args.categoria,
    min_stars=args.min_stars,
    max_dias_inactividad=args.max_dias_inactividad,
    incluir_archivados=args.incluir_archivados,
)

if args.probar:
    imprimir(args.probar, buscar(args.probar, cat, vectores, meta, k=args.k, **filtros))
else:
    filas = []
    for consulta in CONSULTAS_EVAL:
        res = buscar(consulta, cat, vectores, meta, k=5, **filtros)
        imprimir(consulta, res)
        for pos, (_, r) in enumerate(res.iterrows(), start=1):
            filas.append({
                "consulta": consulta, "posicion": pos, "repo": r.full_name,
                "categoria": r.original_category, "similarity": round(float(r.similarity), 4),
            })
    pd.DataFrame(filas).to_csv("resultados_evaluacion.csv", index=False, encoding="utf-8-sig")
    print("\nResultados guardados en resultados_evaluacion.csv")
