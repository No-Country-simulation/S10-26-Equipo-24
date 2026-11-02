import csv
from pathlib import Path
from collections import Counter

ORIGEN = Path("data/integraciones/integraciones_enriquecidas_revision.csv")
CATALOGO = Path("data/catalogo_actualizado.csv")
SALIDA = Path("reportes/auditoria_enriquecidas.csv")

def leer_csv(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def valor(fila, *campos):
    for campo in campos:
        dato = fila.get(campo)
        if dato is not None and str(dato).strip():
            return str(dato).strip()
    return ""

if not ORIGEN.exists() or not CATALOGO.exists():
    raise SystemExit("ERROR: No se encontro el CSV de integraciones o el catalogo.")

integraciones = leer_csv(ORIGEN)
catalogo = leer_csv(CATALOGO)

ids_catalogo = {r["repo_id"] for r in catalogo}
conteo_ids = Counter(
    valor(r, "github_id", "repo_id") for r in integraciones
)

auditoria = []

for fila in integraciones:
    identificador = valor(fila, "github_id", "repo_id")
    nombre = valor(fila, "full_name", "nombre_completo")
    tipo = valor(fila, "integration_type")
    snippet = valor(fila, "code_snippet")
    dificultad = valor(fila, "difficulty_level")
    compatibilidad = valor(fila, "stack_compatibility")
    fuente = valor(fila, "fuente_documentacion")
    evidencia = valor(fila, "evidencia_readme")

    problemas = []

    if identificador not in ids_catalogo:
        problemas.append("ID fuera del catalogo")
    if conteo_ids[identificador] > 1:
        problemas.append("ID duplicado")
    if not tipo:
        problemas.append("Tipo de integracion faltante")
    if not compatibilidad:
        problemas.append("Compatibilidad pendiente")
    if not dificultad:
        problemas.append("Dificultad pendiente")
    if not fuente.startswith("https://"):
        problemas.append("Fuente faltante o invalida")
    if not evidencia:
        problemas.append("Evidencia faltante")

    readme = Path("data/readmes") / f"{identificador}.md"
    if not readme.exists():
        problemas.append("README no disponible")
    elif evidencia:
        contenido = readme.read_text(
            encoding="utf-8", errors="replace"
        )
        if evidencia not in contenido:
            problemas.append("Evidencia textual no confirmada")

    auditoria.append({
        "github_id": identificador,
        "full_name": nombre,
        "integration_type": tipo,
        "tiene_snippet": bool(snippet),
        "problemas": "; ".join(problemas),
        "cantidad_problemas": len(problemas),
        "estado": (
            "pendiente_revision_tecnica"
            if not problemas else "requiere_correccion"
        )
    })

SALIDA.parent.mkdir(parents=True, exist_ok=True)

with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=auditoria[0].keys())
    writer.writeheader()
    writer.writerows(auditoria)

print("\nAUDITORIA COMPLETADA")
print("Integraciones:", len(integraciones))
print("Catalogo:", len(catalogo))
print("Estados:", dict(Counter(r["estado"] for r in auditoria)))
print("Reporte:", SALIDA)
print("Supabase no fue modificado.")
