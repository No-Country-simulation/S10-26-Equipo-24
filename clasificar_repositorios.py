
import os
import re
import csv
import time
import requests
from pathlib import Path

# CONFIGURACIÓN
INPUT = Path("data/catalogo_base.csv")
OUTPUT = Path("data/propuestas_validacion.csv")
LIMITE = 10  # Primera prueba: solo 10 repositorios

API = "https://api.github.com"

TOKEN = os.getenv("GITHUB_TOKEN", "")

session = requests.Session()
session.headers.update({
    "Accept": "application/vnd.github+json",
    "User-Agent": "nocountry-catalog-classifier",
    "X-GitHub-Api-Version": "2022-11-28"
})

if TOKEN:
    session.headers["Authorization"] = f"Bearer {TOKEN}"


# REGLAS DE CLASIFICACIÓN
CATEGORIAS = {
    "Autenticación": [
        "authentication", "authorization", "oauth", "openid",
        "identity", "single-sign-on", "keycloak"
    ],
    "Bases de datos": [
        "database", "postgresql", "mysql", "mongodb",
        "sqlite", "redis", "vector-database"
    ],
    "Pagos": [
        "payment", "payments", "billing", "checkout",
        "stripe", "payment-gateway"
    ],
    "Inteligencia artificial": [
        "machine-learning", "artificial-intelligence",
        "large-language-model", "llm", "generative-ai",
        "inference"
    ],
    "Analítica": [
        "analytics", "business-intelligence", "data-analytics",
        "product-analytics", "web-analytics"
    ],
    "Búsqueda": [
        "search-engine", "full-text-search", "search-platform",
        "elasticsearch", "opensearch"
    ],
    "Backend / APIs": [
        "backend", "backend-framework", "api-framework",
        "rest-api", "web-framework", "asgi",
        "microservices", "server-framework"
    ],
    "DevOps": [
        "devops", "kubernetes", "ci-cd", "infrastructure-as-code",
        "terraform", "deployment", "container-orchestration"
    ],
    "Mensajería": [
        "messaging", "message-queue", "event-streaming",
        "message-broker", "pubsub", "kafka"
    ],
    "Monitoreo": [
        "monitoring", "observability", "tracing",
        "metrics-collection", "application-monitoring",
        "prometheus"
    ]
}


def obtener_json(url):
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        return response.json(), ""
    except requests.RequestException as exc:
        return None, str(exc)


def obtener_readme(repo):
    url = f"{API}/repos/{repo}/readme"

    try:
        response = session.get(
            url,
            headers={"Accept": "application/vnd.github.raw+json"},
            timeout=20
        )
        response.raise_for_status()
        return response.text[:12000], ""
    except requests.RequestException as exc:
        return "", str(exc)


def contiene_termino(texto, termino):
    patron = r"(?<![a-z0-9])" + re.escape(termino) + r"(?![a-z0-9])"
    return bool(re.search(patron, texto.lower()))


def proponer_categoria(descripcion, topics, readme):
    descripcion = (descripcion or "").lower()
    topics_texto = " ".join(topics).lower()
    readme = (readme or "").lower()

    resultados = []

    for categoria, palabras in CATEGORIAS.items():
        puntaje = 0
        evidencia = []

        for palabra in palabras:
            if contiene_termino(topics_texto, palabra):
                puntaje += 5
                evidencia.append(palabra)
            elif contiene_termino(descripcion, palabra):
                puntaje += 4
                evidencia.append(palabra)
            elif contiene_termino(readme[:2000], palabra):
                puntaje += 1
                evidencia.append(palabra)

        # Reducir confusión entre usar una BD y ser una BD.
        if categoria == "Bases de datos":
            señales_bd = [
                "database engine",
                "database management system",
                "database server",
                "vector database",
                "distributed database",
                "database platform",
                "postgres database"
            ]

            texto_principal = descripcion + " " + topics_texto

            if not any(
                contiene_termino(texto_principal, señal)
                for señal in señales_bd
            ):
                puntaje = min(puntaje, 2)

        if puntaje > 0:
            resultados.append((puntaje, categoria, evidencia))

    if not resultados:
        return "", "", "Sin evidencia suficiente", ""

    resultados.sort(key=lambda x: x[0], reverse=True)

    principal = resultados[0][1]
    mejor_puntaje = resultados[0][0]

    secundarias = [
        categoria
        for puntaje, categoria, _ in resultados[1:]
        if puntaje >= max(4, mejor_puntaje * 0.5)
    ]

    segundo_puntaje = resultados[1][0] if len(resultados) > 1 else 0

    confianza = (
        "Media"
        if mejor_puntaje >= 4 and mejor_puntaje > segundo_puntaje
        else "Baja"
    )

    evidencia = ", ".join(resultados[0][2][:5])

    return principal, "; ".join(secundarias), confianza, evidencia


def proponer_tipo(descripcion, topics, readme):
    descripcion = (descripcion or "").lower()
    topics_texto = " ".join(topics).lower()
    readme = (readme or "").lower()

    principal = descripcion + " " + topics_texto
    secundario = readme[:2000]

    reglas = [
        (
            "Motor de búsqueda",
            ["search engine", "search-engine", "metasearch"]
        ),
        (
            "Servidor / broker de mensajería",
            ["message broker", "messaging server",
             "nats-server", "message queue server"]
        ),
        (
            "Herramienta de seguridad",
            ["vulnerability scanner", "security scanner",
             "container security", "vulnerability scanning"]
        ),
        (
            "Plantilla / ejemplo",
            ["boilerplate", "starter", "template",
             "scaffold", "scaffolding", "example project"]
        ),
        (
            "Framework",
            ["framework", "web-framework", "api-framework"]
        ),
        (
            "Biblioteca / SDK",
            ["library", "sdk", "client library"]
        ),
        (
            "Plataforma / servidor",
            ["platform", "self-hosted", "database server"]
        ),
        (
            "Generador de código",
            ["code generator", "code-generator", "codegen"]
        ),
        (
            "Herramienta",
            ["cli", "command-line", "developer tool"]
        )
    ]

    for tipo, palabras in reglas:
        if any(contiene_termino(principal, p) for p in palabras):
            return tipo

    for tipo, palabras in reglas:
        if any(contiene_termino(secundario, p) for p in palabras):
            return tipo

    return "Por determinar"

def generar_justificacion(categoria, tipo, evidencia, descripcion):
    if not categoria:
        return (
            "No se encontró evidencia suficiente para proponer "
            "una categoría funcional. Requiere revisión manual."
        )

    detalle = (
        f" Coincidencias encontradas: {evidencia}."
        if evidencia else ""
    )

    resumen = (descripcion or "").strip()
    if len(resumen) > 180:
        resumen = resumen[:177] + "..."

    return (
        f"Se propone la categoría '{categoria}' y el tipo "
        f"'{tipo}' según la documentación y los metadatos "
        f"del repositorio.{detalle} "
        f"Descripción: {resumen}"
    )


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {INPUT}"
        )

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError("El catálogo de entrada está vacío.")

    propuestas = []

    for numero, repo in enumerate(rows[:LIMITE], start=1):
        nombre = repo["nombre_completo"].strip()

        print(f"[{numero}/{min(LIMITE, len(rows))}] {nombre}")

        datos, error_api = obtener_json(
            f"{API}/repos/{nombre}"
        )

        if datos:
            descripcion = datos.get("description") or ""
            topics = datos.get("topics") or []
            readme, error_readme = obtener_readme(nombre)

            (
                categoria,
                secundarias,
                confianza,
                evidencia
            ) = proponer_categoria(
                descripcion, topics, readme
            )

            tipo = proponer_tipo(
                descripcion, topics, readme
            )

            justificacion = generar_justificacion(
                categoria, tipo, evidencia, descripcion
            )

            observaciones = error_readme

        else:
            categoria = ""
            secundarias = ""
            tipo = "Por determinar"
            confianza = "Sin evidencia suficiente"
            evidencia = ""
            justificacion = (
                "No se pudo consultar la información necesaria."
            )
            observaciones = error_api

        propuestas.append({
            "repo_id": repo["repo_id"],
            "nombre_completo": nombre,
            "categoria_original": repo.get(
                "categoria_busqueda", ""
            ),
            "categoria_propuesta": categoria,
            "categorias_secundarias_propuestas": secundarias,
            "tipo_recurso_propuesto": tipo,
            "justificacion_propuesta": justificacion,
            "evidencia_detectada": evidencia,
            "confianza_heuristica": confianza,
            "estado_validacion": "Pendiente",
            "requiere_revision_humana": "Sí",
            "observaciones_extraccion": observaciones
        })

        time.sleep(1)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(propuestas[0].keys())
        )
        writer.writeheader()
        writer.writerows(propuestas)

    print(f"\nPropuestas generadas: {len(propuestas)}")
    print(f"Archivo creado: {OUTPUT}")
    print("Todas las propuestas requieren revisión humana.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
