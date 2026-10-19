
import os
import csv
import re
import time
import requests
from pathlib import Path

# =====================================
# CONFIGURACIÓN
# =====================================

INPUT = Path("data/propuestas_validacion.csv")
OUTPUT = Path("data/revision_funcional_asistida.csv")

# Piloto inicial con 10 repositorios
LIMITE = 10

API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN", "")

session = requests.Session()

session.headers.update({
    "Accept": "application/vnd.github+json",
    "User-Agent": "nocountry-functional-review",
    "X-GitHub-Api-Version": "2022-11-28"
})

if TOKEN:
    session.headers["Authorization"] = f"Bearer {TOKEN}"


# =====================================
# CONSULTAS A GITHUB
# =====================================

def consultar_github(url, accept=None):
    headers = {}

    if accept:
        headers["Accept"] = accept

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=25
        )

        if response.status_code in (403, 429):
            try:
                mensaje = response.json().get(
                    "message", "Acceso restringido"
                )
            except ValueError:
                mensaje = "Acceso restringido"

            return None, f"HTTP {response.status_code}: {mensaje}"

        response.raise_for_status()
        return response, ""

    except requests.RequestException as exc:
        return None, str(exc)


def obtener_metadatos(nombre):
    response, error = consultar_github(
        f"{API}/repos/{nombre}"
    )

    if response is None:
        return None, error

    return response.json(), ""


def obtener_readme(nombre):
    response, error = consultar_github(
        f"{API}/repos/{nombre}/readme",
        accept="application/vnd.github.raw+json"
    )

    if response is None:
        return "", error

    return response.text[:30000], ""


# =====================================
# ANÁLISIS DOCUMENTAL
# =====================================

TECNOLOGIAS = {
    "Python": r"\bpython\b",
    "JavaScript": r"\bjavascript\b",
    "TypeScript": r"\btypescript\b",
    "Java": r"\bjava\b",
    "Go": r"\bgolang\b|\bgo language\b",
    "Rust": r"\brust\b",
    "Dart": r"\bdart\b",
    "PHP": r"\bphp\b",
    "PostgreSQL": r"\bpostgres(?:ql)?\b",
    "MySQL": r"\bmysql\b",
    "MongoDB": r"\bmongodb\b",
    "Redis": r"\bredis\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b",
    "Node.js": r"\bnode\.?js\b",
    "Bun": r"\bbun\b",
    "React": r"\breact\b",
    "Spring Boot": r"\bspring boot\b",
    "NATS": r"\bnats\b"
}


def limpiar_texto(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    texto = re.sub(r"[`*_#>|]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def extraer_tecnologias(descripcion, topics, readme):
    texto = " ".join([
        descripcion or "",
        " ".join(topics),
        readme or ""
    ])

    encontradas = []

    for nombre, patron in TECNOLOGIAS.items():
        if re.search(patron, texto, flags=re.IGNORECASE):
            encontradas.append(nombre)

    return "; ".join(encontradas)


def extraer_fragmentos(readme, palabras, max_fragmentos=2):
    """
    Extrae fragmentos documentales que contienen
    términos relacionados con una funcionalidad.

    Son evidencias candidatas, no conclusiones.
    """
    fragmentos = []

    for linea in (readme or "").splitlines():
        linea = limpiar_texto(linea)

        if not 35 <= len(linea) <= 500:
            continue

        if any(
            re.search(
                rf"\b{re.escape(palabra)}\b",
                linea,
                flags=re.IGNORECASE
            )
            for palabra in palabras
        ):
            if linea not in fragmentos:
                fragmentos.append(linea[:300])

        if len(fragmentos) >= max_fragmentos:
            break

    return " | ".join(fragmentos)


def analizar_repositorio(repo):
    nombre = repo["nombre_completo"].strip()

    datos, error_meta = obtener_metadatos(nombre)

    if datos is None:
        return {
            "repo_id": repo["repo_id"],
            "nombre_completo": nombre,
            "categoria_propuesta": repo.get(
                "categoria_propuesta", ""
            ),
            "categorias_secundarias_propuestas": repo.get(
                "categorias_secundarias_propuestas", ""
            ),
            "tipo_recurso_propuesto": repo.get(
                "tipo_recurso_propuesto", ""
            ),
            "problema_que_resuelve_borrador": "",
            "casos_de_uso_evidencia": "",
            "tecnologias_mencionadas": "",
            "integracion_evidencia": "",
            "evidencia_funcional": "",
            "enlace_evidencia": f"https://github.com/{nombre}",
            "fuente_evidencia": "No consultada",
            "categoria_validada": "",
            "tipo_recurso_validado": "",
            "justificacion_validada": "",
            "estado_validacion": "Pendiente",
            "requiere_revision_humana": "Sí",
            "observaciones": error_meta
        }

    descripcion = datos.get("description") or ""
    topics = datos.get("topics") or []

    readme, error_readme = obtener_readme(nombre)

    # Descripción proporcionada por el repositorio:
    # sirve como borrador del problema, no como
    # problema funcional confirmado.
    problema = limpiar_texto(descripcion)

    casos = extraer_fragmentos(
        readme,
        [
            "use case", "use cases", "use-case",
            "example", "examples", "scenario",
            "applications"
        ]
    )

    integracion = extraer_fragmentos(
        readme,
        [
            "install", "installation", "requirements",
            "dependencies", "docker", "deploy",
            "configuration", "getting started"
        ]
    )

    evidencia = extraer_fragmentos(
        readme,
        [
            "framework", "platform", "database",
            "messaging", "authentication",
            "monitoring", "analytics", "payment",
            "search", "api"
        ]
    )

    tecnologias = extraer_tecnologias(
        descripcion, topics, readme
    )

    fuente = (
        "Metadatos y README"
        if readme
        else "Metadatos solamente"
    )

    observaciones = []

    if error_readme:
        observaciones.append(
            f"README no disponible: {error_readme}"
        )

    if not casos:
        observaciones.append(
            "Casos de uso sin evidencia explícita extraída"
        )

    if not integracion:
        observaciones.append(
            "Integración pendiente de revisión"
        )

    return {
        "repo_id": repo["repo_id"],
        "nombre_completo": nombre,
        "categoria_propuesta": repo.get(
            "categoria_propuesta", ""
        ),
        "categorias_secundarias_propuestas": repo.get(
            "categorias_secundarias_propuestas", ""
        ),
        "tipo_recurso_propuesto": repo.get(
            "tipo_recurso_propuesto", ""
        ),
        "problema_que_resuelve_borrador": problema,
        "casos_de_uso_evidencia": casos,
        "tecnologias_mencionadas": tecnologias,
        "integracion_evidencia": integracion,
        "evidencia_funcional": evidencia,
        "enlace_evidencia": f"https://github.com/{nombre}",
        "fuente_evidencia": fuente,
        "categoria_validada": "",
        "tipo_recurso_validado": "",
        "justificacion_validada": "",
        "estado_validacion": "Pendiente",
        "requiere_revision_humana": "Sí",
        "observaciones": " | ".join(observaciones)
    }


# =====================================
# EJECUCIÓN PRINCIPAL
# =====================================

def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"No existe el archivo de entrada: {INPUT}"
        )

    with INPUT.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError(
            "El archivo de propuestas está vacío."
        )

    seleccionados = rows[:LIMITE]
    resultados = []

    for numero, repo in enumerate(
        seleccionados, start=1
    ):
        nombre = repo["nombre_completo"]

        print(
            f"[{numero}/{len(seleccionados)}] "
            f"Revisando {nombre}",
            flush=True
        )

        resultado = analizar_repositorio(repo)
        resultados.append(resultado)

        time.sleep(1)

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    with OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(resultados[0].keys())
        )

        writer.writeheader()
        writer.writerows(resultados)

    print(
        f"\nRepositorios procesados: {len(resultados)}"
    )
    print(f"Archivo generado: {OUTPUT}")
    print("Estado: pendiente de validación humana")


if __name__ == "__main__":
    main()
