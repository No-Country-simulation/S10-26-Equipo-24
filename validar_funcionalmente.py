
import csv
import os
import re
import time
from pathlib import Path

import requests


# ============================================
# CONFIGURACIÓN
# ============================================

INPUT = Path("data/propuestas_validacion.csv")
OUTPUT = Path("data/revision_funcional_asistida.csv")

# None = procesar todos los repositorios
LIMITE = None

API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN", "")

session = requests.Session()
session.headers.update({
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "nocountry-functional-review"
})

if TOKEN:
    session.headers["Authorization"] = f"Bearer {TOKEN}"


# ============================================
# PALABRAS CLAVE
# ============================================

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
    "NATS": r"\bnats\b",
    "SQLite": r"\bsqlite\b",
    "GraphQL": r"\bgraphql\b",
    "REST API": r"\brest(?:ful)?\s+api\b"
}

SECCIONES = {
    "funcionalidad": [
        "overview", "introduction", "about",
        "features", "what is", "why",
        "description", "key features",
        "caracteristicas", "funcionalidades",
        "descripcion", "introduccion",
        "概述", "简介", "功能", "特性"
    ],
    "casos_uso": [
        "use cases", "use case", "examples",
        "example", "usage", "quickstart",
        "getting started", "casos de uso",
        "ejemplos", "uso", "应用场景", "使用",
        "示例"
    ],
    "integracion": [
        "installation", "install",
        "requirements", "prerequisites",
        "dependencies", "setup",
        "configuration", "deployment",
        "getting started", "quickstart",
        "instalacion", "requisitos",
        "configuracion", "安装", "部署",
        "配置", "依赖"
    ]
}

CAMPOS_SALIDA = [
    "repo_id",
    "nombre_completo",
    "categoria_original",
    "categoria_propuesta",
    "categorias_secundarias_propuestas",
    "tipo_recurso_propuesto",
    "justificacion_propuesta",
    "confianza_heuristica",
    "descripcion_original",
    "problema_que_resuelve_borrador",
    "evidencia_funcional",
    "casos_de_uso_evidencia",
    "integracion_evidencia",
    "tecnologias_mencionadas",
    "lenguaje_principal_github",
    "enlace_evidencia",
    "enlace_readme",
    "fuente_evidencia",
    "cobertura_documental",
    "categoria_validada",
    "categorias_secundarias_validadas",
    "tipo_recurso_validado",
    "problema_que_resuelve_validado",
    "casos_de_uso_validados",
    "lenguajes_tecnologias_validados",
    "consideraciones_integracion_validadas",
    "justificacion_validacion",
    "estado_validacion",
    "requiere_revision_humana",
    "observaciones_analista",
    "observaciones_extraccion"
]


# ============================================
# CONSULTAS GITHUB
# ============================================

def consultar_github(url, accept=None):
    headers = {}

    if accept:
        headers["Accept"] = accept

    # Reintento limitado para errores temporales
    for intento in range(3):
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response, ""

            if response.status_code in (500, 502, 503, 504):
                if intento < 2:
                    time.sleep(2 * (intento + 1))
                    continue

            if response.status_code in (403, 429):
                # No insistir ante bloqueos de acceso,
                # límites o políticas de una organización.
                return None, (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )

            return None, (
                f"HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        except requests.RequestException as error:
            if intento < 2:
                time.sleep(2 * (intento + 1))
                continue
            return None, str(error)

    return None, "Error desconocido"


def obtener_metadatos(nombre):
    response, error = consultar_github(
        f"{API}/repos/{nombre}"
    )

    if response is None:
        return None, error

    try:
        return response.json(), ""
    except ValueError:
        return None, "JSON de metadatos inválido"


def obtener_readme(nombre):
    url = f"{API}/repos/{nombre}/readme"

    # Primero obtener la ubicación real del README.
    response, error = consultar_github(url)

    if response is None:
        return "", "", error

    try:
        datos = response.json()
    except ValueError:
        return "", "", "Metadatos del README inválidos"

    enlace = datos.get("html_url") or ""

    # La API proporciona el contenido del README.
    raw_response, raw_error = consultar_github(
        url,
        accept="application/vnd.github.raw+json"
    )

    if raw_response is None:
        return "", enlace, raw_error

    return raw_response.text[:60000], enlace, ""


# ============================================
# LIMPIEZA DE TEXTO
# ============================================

def limpiar_texto(texto):
    texto = texto or ""

    # Eliminar HTML y marcas Markdown sencillas.
    texto = re.sub(r"<[^>]+>", " ", texto)

    texto = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        " ",
        texto
    )

    texto = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        texto
    )

    texto = re.sub(r"[`*_#>|]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def es_ruido(linea):
    linea = linea.strip()

    if not linea:
        return True

    if linea.startswith((
        "![", "[![", "<img", "<svg",
        "<!--", "http://", "https://"
    )):
        return True

    if "img.shields.io" in linea:
        return True

    if "badge.svg" in linea:
        return True

    if re.match(r"^\|[-:\s|]+\|?$", linea):
        return True

    if re.match(r"^[-=]{3,}$", linea):
        return True

    return False


# ============================================
# EXTRAER SECCIONES DEL README
# ============================================

def normalizar_titulo(titulo):
    titulo = limpiar_texto(titulo).lower()
    titulo = re.sub(r"[^\w\s]", " ", titulo)
    titulo = re.sub(r"\s+", " ", titulo)
    return titulo.strip()


def dividir_readme_en_secciones(readme):
    secciones = []
    titulo_actual = "Introducción"
    lineas_actuales = []
    en_codigo = False

    def guardar_seccion():
        if lineas_actuales:
            secciones.append({
                "titulo": titulo_actual,
                "contenido": "\n".join(lineas_actuales)
            })

    for linea in (readme or "").splitlines():
        original = linea.strip()

        if original.startswith(("```", "~~~")):
            en_codigo = not en_codigo
            continue

        if en_codigo:
            continue

        # Detectar encabezados Markdown.
        encabezado = re.match(
            r"^#{1,6}\s+(.+)$",
            original
        )

        if encabezado:
            guardar_seccion()
            titulo_actual = limpiar_texto(
                encabezado.group(1)
            )
            lineas_actuales = []
            continue

        if es_ruido(original):
            continue

        linea_limpia = limpiar_texto(original)

        if not linea_limpia:
            continue

        # Conservar texto descriptivo y listas.
        if len(linea_limpia) >= 25:
            lineas_actuales.append(linea_limpia)

    guardar_seccion()

    return secciones


def seleccionar_secciones(secciones, tipo):
    palabras = SECCIONES[tipo]
    seleccionadas = []

    for seccion in secciones:
        titulo = normalizar_titulo(
            seccion["titulo"]
        )

        if any(
            palabra in titulo
            for palabra in palabras
        ):
            seleccionadas.append(seccion)

    return seleccionadas


def crear_fragmentos(secciones, max_fragmentos=3):
    fragmentos = []
    vistos = set()

    for seccion in secciones:
        titulo = seccion["titulo"]

        for linea in seccion["contenido"].splitlines():
            texto = limpiar_texto(linea)

            if len(texto) < 40:
                continue

            # Evitar enlaces sueltos y bloques
            # de documentación poco descriptiva.
            if re.search(r"https?://", texto):
                continue

            clave = texto.lower()

            if clave in vistos:
                continue

            vistos.add(clave)

            fragmentos.append(
                f"[{titulo}] {texto[:350]}"
            )

            if len(fragmentos) >= max_fragmentos:
                return " | ".join(fragmentos)

    return " | ".join(fragmentos)


# ============================================
# TECNOLOGÍAS
# ============================================

def detectar_tecnologias(
    descripcion, topics, readme
):
    texto = " ".join([
        descripcion or "",
        " ".join(topics or []),
        readme or ""
    ])

    resultados = []

    for tecnologia, patron in TECNOLOGIAS.items():
        if re.search(
            patron,
            texto,
            flags=re.IGNORECASE
        ):
            resultados.append(tecnologia)

    # Son menciones, no requisitos confirmados.
    return "; ".join(resultados)


# ============================================
# ANALIZAR UN REPOSITORIO
# ============================================

def analizar_repositorio(repo):
    nombre = repo.get(
        "nombre_completo", ""
    ).strip()

    resultado = {
        campo: "" for campo in CAMPOS_SALIDA
    }

    # Conservar propuestas previas.
    for campo in [
        "repo_id",
        "nombre_completo",
        "categoria_original",
        "categoria_propuesta",
        "categorias_secundarias_propuestas",
        "tipo_recurso_propuesto",
        "justificacion_propuesta",
        "confianza_heuristica"
    ]:
        resultado[campo] = repo.get(campo, "")

    resultado["nombre_completo"] = nombre
    resultado["estado_validacion"] = "Pendiente"
    resultado["requiere_revision_humana"] = "Sí"
    resultado["enlace_evidencia"] = (
        f"https://github.com/{nombre}"
    )

    observaciones = []

    if not nombre or "/" not in nombre:
        resultado["observaciones_extraccion"] = (
            "Nombre del repositorio inválido"
        )
        resultado["cobertura_documental"] = (
            "Sin información"
        )
        return resultado

    datos, error_meta = obtener_metadatos(nombre)

    if datos is None:
        resultado["observaciones_extraccion"] = (
            f"Metadatos no disponibles: {error_meta}"
        )
        resultado["cobertura_documental"] = (
            "Sin información"
        )
        return resultado

    descripcion = datos.get("description") or ""
    topics = datos.get("topics") or []
    lenguaje = datos.get("language") or ""

    resultado["descripcion_original"] = descripcion
    resultado["lenguaje_principal_github"] = lenguaje
    resultado["enlace_evidencia"] = (
        datos.get("html_url")
        or resultado["enlace_evidencia"]
    )

    # La descripción es un borrador.
    # No afirmar que es validación funcional.
    resultado["problema_que_resuelve_borrador"] = (
        limpiar_texto(descripcion)
    )

    readme, enlace_readme, error_readme = (
        obtener_readme(nombre)
    )

    resultado["enlace_readme"] = enlace_readme

    if error_readme:
        observaciones.append(
            f"README no disponible: {error_readme}"
        )

    if readme:
        secciones = dividir_readme_en_secciones(
            readme
        )

        funcionales = seleccionar_secciones(
            secciones, "funcionalidad"
        )

        casos = seleccionar_secciones(
            secciones, "casos_uso"
        )

        integracion = seleccionar_secciones(
            secciones, "integracion"
        )

        resultado["evidencia_funcional"] = (
            crear_fragmentos(funcionales)
        )

        resultado["casos_de_uso_evidencia"] = (
            crear_fragmentos(casos)
        )

        resultado["integracion_evidencia"] = (
            crear_fragmentos(integracion)
        )

        resultado["fuente_evidencia"] = (
            "GitHub API y README"
        )

        if not funcionales:
            observaciones.append(
                "No se identificó sección funcional"
            )

        if not casos:
            observaciones.append(
                "No se identificó sección de casos de uso"
            )

        if not integracion:
            observaciones.append(
                "No se identificó sección de integración"
            )

    else:
        resultado["fuente_evidencia"] = (
            "Solo metadatos GitHub"
        )

    resultado["tecnologias_mencionadas"] = (
        detectar_tecnologias(
            descripcion,
            topics,
            readme
        )
    )

    campos_evidencia = [
        "evidencia_funcional",
        "casos_de_uso_evidencia",
        "integracion_evidencia"
    ]

    cantidad = sum(
        bool(resultado[campo])
        for campo in campos_evidencia
    )

    if not readme:
        cobertura = "Sin README"
    elif cantidad == 3:
        cobertura = "Tres tipos de evidencia"
    elif cantidad == 2:
        cobertura = "Dos tipos de evidencia"
    elif cantidad == 1:
        cobertura = "Un tipo de evidencia"
    else:
        cobertura = "Sin fragmentos identificados"

    resultado["cobertura_documental"] = cobertura

    if not resultado["evidencia_funcional"]:
        observaciones.append(
            "Función principal requiere revisión manual"
        )

    resultado["observaciones_extraccion"] = (
        " | ".join(observaciones)
    )

    return resultado


# ============================================
# PROCESAMIENTO Y EXPORTACIÓN
# ============================================

def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {INPUT}"
        )

    with INPUT.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:
        repositorios = list(
            csv.DictReader(archivo)
        )

    if not repositorios:
        raise ValueError(
            "El CSV de entrada está vacío"
        )

    if LIMITE is not None:
        repositorios = repositorios[:LIMITE]

    nombres = [
        repo["nombre_completo"].strip()
        for repo in repositorios
    ]

    if len(nombres) != len(set(nombres)):
        raise ValueError(
            "Hay repositorios duplicados en la entrada"
        )

    resultados = []

    for indice, repo in enumerate(
        repositorios, start=1
    ):
        nombre = repo["nombre_completo"]

        print(
            f"[{indice}/{len(repositorios)}] "
            f"{nombre}",
            flush=True
        )

        try:
            resultado = analizar_repositorio(repo)
        except Exception as error:
            # Preservar el registro pendiente.
            resultado = {
                campo: ""
                for campo in CAMPOS_SALIDA
            }

            resultado["repo_id"] = repo.get(
                "repo_id", ""
            )

            resultado["nombre_completo"] = nombre

            resultado["estado_validacion"] = (
                "Pendiente"
            )

            resultado["requiere_revision_humana"] = (
                "Sí"
            )

            resultado["observaciones_extraccion"] = (
                f"Error: {error}"
            )

        resultados.append(resultado)

        # Pausa pequeña para evitar ráfagas.
        time.sleep(0.5)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:
        writer = csv.DictWriter(
            archivo,
            fieldnames=CAMPOS_SALIDA
        )

        writer.writeheader()
        writer.writerows(resultados)

    print("\nPROCESO FINALIZADO")
    print(f"Repositorios: {len(resultados)}")
    print(f"Archivo generado: {OUTPUT}")

    con_readme = sum(
        "README" in r["fuente_evidencia"]
        for r in resultados
    )

    print(f"Con README: {con_readme}")

    fallidos = sum(
        r["cobertura_documental"]
        in ("Sin información", "Sin README")
        for r in resultados
    )

    print(
        f"Sin información suficiente inicial: "
        f"{fallidos}"
    )

    print(
        "Todos los repositorios quedan "
        "pendientes de validación humana."
    )


if __name__ == "__main__":
    main()
