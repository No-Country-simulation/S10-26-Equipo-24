
#!/usr/bin/env python3
"""
OpenBridge - Extraccion de metadata de 100 repositorios.

Fuente: GitHub GraphQL API
Alternativa: GitHub REST API para Trivy

NO modifica Supabase.
Guarda los resultados en reportes/.
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from pathlib import Path


CATALOGO = Path("data/catalogo_actualizado.csv")
SALIDA = Path("reportes/metadata_github_verificada.csv")
ERRORES = Path("reportes/metadata_github_errores.csv")

TAMANO = 10

CAMPOS = [
    "repo_id",
    "full_name",
    "consultado_utc",
    "issues_abiertos",
    "issues_cerrados",
    "prs_abiertos",
    "prs_cerrados",
    "languages",
    "archived",
    "disabled",
    "tiene_release",
    "tiene_tags",
    "fecha_ultimo_release",
    "num_releases",
    "num_tags",
]


def token():
    valor = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )

    if valor:
        return valor

    if os.environ.get("GITHUB_ACTIONS"):
        raise RuntimeError(
            "GITHUB_TOKEN ausente en GitHub Actions"
        )

    try:
        resultado = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if resultado.returncode == 0:
            if resultado.stdout.strip():
                return resultado.stdout.strip()

    except (OSError, subprocess.TimeoutExpired):
        pass

    raise RuntimeError(
        "Falta autenticacion de GitHub"
    )


def query_for(grupo):
    partes = []

    for indice, (_, full_name) in enumerate(grupo):
        owner, nombre = full_name.split("/", 1)

        partes.append(
            f"""
            r{indice}: repository(
                owner: {json.dumps(owner)}
                name: {json.dumps(nombre)}
            ) {{
                databaseId
                nameWithOwner
                isArchived
                isDisabled

                issuesOpen: issues(states: OPEN) {{
                    totalCount
                }}

                issuesClosed: issues(states: CLOSED) {{
                    totalCount
                }}

                prsOpen: pullRequests(states: OPEN) {{
                    totalCount
                }}

                prsClosed: pullRequests(
                    states: [CLOSED, MERGED]
                ) {{
                    totalCount
                }}

                languages(
                    first: 5
                    orderBy: {{
                        field: SIZE
                        direction: DESC
                    }}
                ) {{
                    nodes {{
                        name
                    }}
                }}

                releases(
                    first: 1
                    orderBy: {{
                        field: CREATED_AT
                        direction: DESC
                    }}
                ) {{
                    totalCount
                    nodes {{
                        publishedAt
                    }}
                }}

                refs(
                    refPrefix: "refs/tags/"
                    first: 1
                ) {{
                    totalCount
                }}
            }}
            """
        )

    return (
        "query OpenBridgeMetadata {\n"
        + "\n".join(partes)
        + "\n}"
    )


def request_graphql(secret, consulta):
    payload = json.dumps({
        "query": consulta
    }).encode("utf-8")

    peticion = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {secret}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "OpenBridge-Metadata-Audit",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        peticion, timeout=90
    ) as respuesta:
        datos = json.loads(
            respuesta.read().decode("utf-8")
        )

    # Conservar respuestas validas aunque GraphQL
    # devuelva errores parciales de otros repositorios.
    if not isinstance(datos.get("data"), dict):
        raise RuntimeError(
            "Respuesta GraphQL sin datos: "
            + str(datos.get("errors", []))[:650]
        )

    return datos


def rest_json_public(url):
    peticion = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "OpenBridge-Metadata-Audit",
        },
    )

    with urllib.request.urlopen(
        peticion, timeout=45
    ) as respuesta:
        datos = json.loads(
            respuesta.read().decode("utf-8")
        )
        links = respuesta.headers.get("Link", "")

    return datos, links


def total_paginado(elementos, link):
    patron = (
        r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"'
    )

    coincidencia = re.search(patron, link)

    if coincidencia:
        return int(coincidencia.group(1))

    if 'rel="next"' in link:
        raise RuntimeError(
            "Paginacion REST sin total verificable"
        )

    return len(elementos)


def rest_fallback_public(repo_id, full_name, ahora):
    """
    Alternativa REST para el repositorio restringido
    en GraphQL.

    Si un dato no puede verificarse, registra error.
    No inventa ceros.
    """

    base = "https://api.github.com"
    ruta = (
        "/repos/"
        + urllib.parse.quote(full_name, safe="/")
    )

    repo, _ = rest_json_public(base + ruta)

    if int(repo["id"]) != repo_id:
        raise RuntimeError(
            f"GitHub ID diferente: {full_name}"
        )

    lenguajes, _ = rest_json_public(
        base + ruta + "/languages"
    )

    releases, link_releases = rest_json_public(
        base + ruta + "/releases?per_page=1"
    )

    tags, link_tags = rest_json_public(
        base + ruta + "/tags?per_page=1"
    )

    numero_releases = total_paginado(
        releases, link_releases
    )

    numero_tags = total_paginado(
        tags, link_tags
    )

    conteos = {}

    consultas = [
        ("issues_abiertos", "issue", "open"),
        ("issues_cerrados", "issue", "closed"),
        ("prs_abiertos", "pr", "open"),
        ("prs_cerrados", "pr", "closed"),
    ]

    for campo, tipo, estado in consultas:
        consulta = (
            f"repo:{full_name} "
            f"is:{tipo} is:{estado}"
        )

        url = (
            base
            + "/search/issues?"
            + urllib.parse.urlencode({
                "q": consulta,
                "per_page": 1,
            })
        )

        respuesta, _ = rest_json_public(url)

        if (
            respuesta.get("incomplete_results")
            or not isinstance(
                respuesta.get("total_count"), int
            )
        ):
            raise RuntimeError(
                f"Conteo incompleto: {campo}"
            )

        conteos[campo] = respuesta["total_count"]
        time.sleep(1)

    idiomas = ", ".join(
        nombre
        for nombre, _ in sorted(
            lenguajes.items(),
            key=lambda item: -item[1],
        )[:5]
    )

    if not idiomas:
        raise RuntimeError(
            f"Lenguajes no verificables: {full_name}"
        )

    fecha_release = (
        releases[0].get("published_at")
        if releases else None
    )

    return {
        "repo_id": repo_id,
        "full_name": repo["full_name"],
        "consultado_utc": ahora,
        **conteos,
        "languages": idiomas,
        "archived": bool(repo["archived"]),
        "disabled": bool(repo["disabled"]),
        "tiene_release": numero_releases > 0,
        "tiene_tags": numero_tags > 0,
        "fecha_ultimo_release": fecha_release or "",
        "num_releases": numero_releases,
        "num_tags": numero_tags,
    }


def main():
    if not CATALOGO.exists():
        raise RuntimeError(
            f"No existe {CATALOGO}"
        )

    with CATALOGO.open(
        encoding="utf-8-sig",
        newline="",
    ) as archivo:
        filas = list(csv.DictReader(archivo))

    if len(filas) != 100:
        raise RuntimeError(
            f"Se esperaban 100 repositorios: {len(filas)}"
        )

    repositorios = []

    for fila in filas:
        full_name = (
            fila.get("nombre_completo") or ""
        ).strip()

        repo_id = int(fila["repo_id"])

        if "/" not in full_name:
            raise RuntimeError(
                f"Repositorio invalido: {full_name}"
            )

        repositorios.append((repo_id, full_name))

    ids = {r[0] for r in repositorios}
    nombres = {
        r[1].casefold() for r in repositorios
    }

    if len(ids) != 100 or len(nombres) != 100:
        raise RuntimeError(
            "El catalogo contiene duplicados"
        )

    secreto = token()

    registros = []
    errores = []

    ahora = datetime.now(
        timezone.utc
    ).isoformat()

    for inicio in range(0, 100, TAMANO):
        grupo = repositorios[
            inicio:inicio + TAMANO
        ]

        try:
            respuesta = request_graphql(
                secreto,
                query_for(grupo),
            )

            datos = respuesta["data"]
            errores_por_alias = {}

            for error in respuesta.get(
                "errors", []
            ):
                ruta = error.get("path") or []

                if (
                    not ruta
                    or not re.fullmatch(
                        r"r\d+", str(ruta[0])
                    )
                ):
                    raise RuntimeError(
                        "Error GraphQL general: "
                        + str(error)[:300]
                    )

                errores_por_alias[
                    str(ruta[0])
                ] = error

            for indice, (
                repo_id,
                full_name,
            ) in enumerate(grupo):

                alias = f"r{indice}"
                repo = datos.get(alias)

                if (
                    alias in errores_por_alias
                    or not repo
                ):
                    try:
                        if (
                            full_name.casefold()
                            != "aquasecurity/trivy"
                        ):
                            raise RuntimeError(
                                str(
                                    errores_por_alias.get(
                                        alias,
                                        "Repositorio inaccesible",
                                    )
                                )[:300]
                            )

                        print(
                            "FALLBACK REST PUBLICO:",
                            full_name,
                            flush=True,
                        )

                        registros.append(
                            rest_fallback_public(
                                repo_id,
                                full_name,
                                ahora,
                            )
                        )

                    except (
                        urllib.error.URLError,
                        TimeoutError,
                        RuntimeError,
                        ValueError,
                        KeyError,
                    ) as error:

                        errores.append({
                            "full_name": full_name,
                            "error": str(error)[:300],
                        })

                    continue

                if repo.get(
                    "databaseId"
                ) != repo_id:

                    errores.append({
                        "full_name": full_name,
                        "error": "GitHub ID diferente",
                    })
                    continue

                try:
                    nombres = [
                        item["name"]
                        for item in repo[
                            "languages"
                        ]["nodes"]
                        if item and item.get("name")
                    ]

                    releases = repo["releases"]
                    total_releases = int(
                        releases["totalCount"]
                    )

                    tags = repo["refs"]

                    total_tags = (
                        int(tags["totalCount"])
                        if tags else 0
                    )

                    fecha_release = None

                    if releases.get("nodes"):
                        fecha_release = (
                            releases["nodes"][0]
                            .get("publishedAt")
                        )

                    registro = {
                        "repo_id": repo_id,
                        "full_name": repo[
                            "nameWithOwner"
                        ],
                        "consultado_utc": ahora,
                        "issues_abiertos": int(
                            repo["issuesOpen"][
                                "totalCount"
                            ]
                        ),
                        "issues_cerrados": int(
                            repo["issuesClosed"][
                                "totalCount"
                            ]
                        ),
                        "prs_abiertos": int(
                            repo["prsOpen"][
                                "totalCount"
                            ]
                        ),
                        "prs_cerrados": int(
                            repo["prsClosed"][
                                "totalCount"
                            ]
                        ),
                        "languages": (
                            ", ".join(nombres)
                            if nombres else ""
                        ),
                        "archived": repo["isArchived"],
                        "disabled": repo["isDisabled"],
                        "tiene_release": (
                            total_releases > 0
                        ),
                        "tiene_tags": total_tags > 0,
                        "fecha_ultimo_release": (
                            fecha_release or ""
                        ),
                        "num_releases": total_releases,
                        "num_tags": total_tags,
                    }

                    registros.append(registro)

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ) as error:

                    errores.append({
                        "full_name": full_name,
                        "error": (
                            f"Campos incompletos: {error}"
                        ),
                    })

        except (
            urllib.error.URLError,
            TimeoutError,
            RuntimeError,
        ) as error:

            for _, full_name in grupo:
                errores.append({
                    "full_name": full_name,
                    "error": str(error)[:300],
                })

        print(
            f"Procesados {min(inicio + TAMANO, 100)}/100 "
            f"| completos {len(registros)} "
            f"| errores {len(errores)}",
            flush=True,
        )

        time.sleep(1)

    SALIDA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SALIDA.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:

        escritor = csv.DictWriter(
            archivo,
            fieldnames=CAMPOS,
        )

        escritor.writeheader()
        escritor.writerows(registros)

    with ERRORES.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:

        escritor = csv.DictWriter(
            archivo,
            fieldnames=["full_name", "error"],
        )

        escritor.writeheader()
        escritor.writerows(errores)

    print(
        f"RESULTADO: {len(registros)}/100 "
        "datos extraidos. Sin modificar Supabase."
    )

    print(
        f"CSV: {SALIDA} | Errores: {ERRORES}"
    )

    if len(registros) != 100:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "ERROR:", str(error),
            file=sys.stderr,
        )
        sys.exit(1)
