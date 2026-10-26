import os
import time
import datetime
import requests
import numpy as np
import pandas as pd

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# La Search API tiene un límite mucho más bajo: 30 req/min con token, 10 sin él.
PAUSA_SEARCH = 2.5 if GITHUB_TOKEN else 6.5

# Tope de páginas al paginar (100 elementos por página).
MAX_PAGINAS = 10

if not GITHUB_TOKEN:
    print("⚠️  GITHUB_TOKEN no definido: el límite de la API será muy bajo (60 req/h).")


# ---------------------------------------------------------------------------
# Utilidades de red
# ---------------------------------------------------------------------------
def get_con_reintento(url, params=None, silenciar_404=False):
    """
    GET con aviso en consola si falla y un reintento si se agota el rate limit.
    Devuelve el objeto Response, o None si hubo un error de red.
    """
    for intento in range(2):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        except requests.RequestException as e:
            print(f"    ⚠️ Error de red en {url}: {e}")
            return None

        if r.status_code == 200:
            return r

        # Rate limit agotado: esperar al reset (máx. 2 min) y reintentar una vez
        restante = r.headers.get("X-RateLimit-Remaining")
        if r.status_code in (403, 429) and intento == 0:
            reset = r.headers.get("X-RateLimit-Reset")
            espera = r.headers.get("Retry-After")
            if espera:
                espera = int(espera)
            elif restante == "0" and reset:
                espera = max(int(reset) - int(time.time()), 1)
            else:
                espera = None

            if espera is not None:
                espera = min(espera + 1, 120)
                print(f"    ⏳ Rate limit alcanzado. Esperando {espera}s...")
                time.sleep(espera)
                continue

        if not (r.status_code == 404 and silenciar_404):
            print(f"    ⚠️ HTTP {r.status_code} en {url}")
        return r

    return None


def paginar(url, params=None, max_paginas=MAX_PAGINAS):
    """Recorre las páginas de un endpoint que devuelve listas. Devuelve (items, truncado)."""
    params = dict(params or {})
    params["per_page"] = 100
    items = []

    for pagina in range(1, max_paginas + 1):
        params["page"] = pagina
        r = get_con_reintento(url, params=params)
        if r is None or r.status_code != 200:
            return items, False

        datos = r.json()
        if not isinstance(datos, list):
            return items, False

        items.extend(datos)
        if len(datos) < 100:
            return items, False  # última página: conteo completo

    return items, True  # se alcanzó el tope de páginas


def contar_busqueda(query):
    """
    Cuenta resultados con la Search API (total_count) sin paginar.
    Devuelve None si la petición falla, para no confundir un fallo con un 0 real.
    """
    time.sleep(PAUSA_SEARCH)
    r = get_con_reintento(
        "https://api.github.com/search/issues",
        params={"q": query, "per_page": 1},
    )
    if r is not None and r.status_code == 200:
        return r.json().get("total_count", 0)
    return None


def parsear_fecha(texto):
    return datetime.datetime.fromisoformat(texto.replace("Z", "+00:00"))


def mediana_dias(items, campo_fin):
    """Mediana de días entre created_at y campo_fin. Ignora los elementos sin fecha de fin."""
    dias = []
    for it in items:
        ini, fin = it.get("created_at"), it.get(campo_fin)
        if ini and fin:
            delta = parsear_fecha(fin) - parsear_fecha(ini)
            dias.append(delta.total_seconds() / 86400)
    return round(float(np.median(dias)), 2) if dias else None


# ---------------------------------------------------------------------------
# Obtención de datos por repositorio
# ---------------------------------------------------------------------------
def obtener_detalles_github(nombre_completo):
    base_url = f"https://api.github.com/repos/{nombre_completo}"
    ahora = datetime.datetime.now(datetime.timezone.utc)

    res_data = {
        "full_name": nombre_completo,
        "description": "",
        "language": "Multi-lenguaje",
        "stars": 0,
        "forks": 0,
        "open_issues": 0,
        "license": "N/A",
        "html_url": f"https://github.com/{nombre_completo}",
        "archived": False,
        "disabled": False,
        "fecha_descarga": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "commits_90d": 0,
        "fecha_ultimo_commit": None,
        "issues_abiertos": None,
        "issues_cerrados": None,
        "prs_abiertos": None,
        "prs_cerrados": None,
        "mediana_dias_cierre_issues": None,
        "mediana_dias_merge_prs": None,
        "contribuidores": 0,
        "tiene_release": False,
        "tiene_tags": False,
        "fecha_ultimo_release": None,
    }

    try:
        # 0. Datos básicos del repo
        r = get_con_reintento(base_url)
        if r is not None and r.status_code == 200:
            d = r.json()
            res_data["description"] = d.get("description") or ""
            res_data["language"] = d.get("language") or "No especificado"
            res_data["stars"] = d.get("stargazers_count", 0)
            res_data["forks"] = d.get("forks_count", 0)
            res_data["open_issues"] = d.get("open_issues_count", 0)
            res_data["archived"] = d.get("archived", False)
            res_data["disabled"] = d.get("disabled", False)
            res_data["html_url"] = d.get("html_url", res_data["html_url"])

            lic = d.get("license")
            if isinstance(lic, dict):
                res_data["license"] = lic.get("spdx_id") or "N/A"
        else:
            print(f"    ⚠️ No se pudo leer el repo {nombre_completo}; se omiten el resto de métricas.")
            return res_data

        # 1. Commits de los últimos 90 días (paginado) y fecha del último commit
        hace_90d = (ahora - datetime.timedelta(days=90)).isoformat()
        commits, truncado = paginar(f"{base_url}/commits", {"since": hace_90d})
        res_data["commits_90d"] = len(commits)
        if truncado:
            print(f"    ℹ️ commits_90d truncado a {len(commits)} (tope de {MAX_PAGINAS} páginas)")
        if commits:
            res_data["fecha_ultimo_commit"] = (
                commits[0].get("commit", {}).get("committer", {}).get("date")
            )

        # 2. Contribuidores (paginado, descartando bots)
        contribs, truncado = paginar(f"{base_url}/contributors")
        humanos = [c for c in contribs if isinstance(c, dict) and c.get("type") != "Bot"]
        res_data["contribuidores"] = len(humanos)
        if truncado:
            print(f"    ℹ️ contribuidores truncado a {len(humanos)} (tope de {MAX_PAGINAS} páginas)")

        # 3. Releases y tags (un 404 en releases/latest es normal: no hay releases)
        r_rel = get_con_reintento(f"{base_url}/releases/latest", silenciar_404=True)
        if r_rel is not None and r_rel.status_code == 200:
            res_data["tiene_release"] = True
            res_data["fecha_ultimo_release"] = r_rel.json().get("published_at")

        r_tags = get_con_reintento(f"{base_url}/tags", params={"per_page": 1})
        if r_tags is not None and r_tags.status_code == 200 and len(r_tags.json()) > 0:
            res_data["tiene_tags"] = True

        # 4. Conteo de issues y PRs (Search API)
        res_data["issues_abiertos"] = contar_busqueda(f"repo:{nombre_completo} type:issue state:open")
        res_data["issues_cerrados"] = contar_busqueda(f"repo:{nombre_completo} type:issue state:closed")
        res_data["prs_abiertos"] = contar_busqueda(f"repo:{nombre_completo} type:pr state:open")
        res_data["prs_cerrados"] = contar_busqueda(f"repo:{nombre_completo} type:pr state:closed")

        # 5. Medianas (sobre una muestra de hasta 100 elementos cerrados)
        r_i = get_con_reintento(
            f"{base_url}/issues",
            params={"state": "closed", "per_page": 100, "sort": "updated", "direction": "desc"},
        )
        if r_i is not None and r_i.status_code == 200:
            # /issues también devuelve PRs: se filtran
            issues = [i for i in r_i.json() if "pull_request" not in i]
            res_data["mediana_dias_cierre_issues"] = mediana_dias(issues, "closed_at")

        r_p = get_con_reintento(
            f"{base_url}/pulls",
            params={"state": "closed", "per_page": 100, "sort": "updated", "direction": "desc"},
        )
        if r_p is not None and r_p.status_code == 200:
            # Los PRs cerrados sin merge tienen merged_at = None y se ignoran
            res_data["mediana_dias_merge_prs"] = mediana_dias(r_p.json(), "merged_at")

    except Exception as e:
        print(f"    ⚠️ Error inesperado para {nombre_completo}: {e}")

    return res_data


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------
def enriquecer_catalogo():
    input_path = "data/catalogo_base.csv"
    output_csv = "data/catalogo_enriquecido_100.csv"

    if not os.path.exists(input_path):
        print(f"❌ No se encontró el archivo: {input_path}")
        return

    df = pd.read_csv(input_path)
    total = len(df)
    print(f"🔄 Enriqueciendo {total} repositorios con métricas de salud avanzadas...")

    registros = []

    for idx, row in df.iterrows():
    
        nombre = row["nombre_completo"]
        print(f"  --> [{idx + 1}/{total}] Procesando métricas: {nombre}")
        info = obtener_detalles_github(nombre)

        cat = str(row.get("categoria_propuesta", "General"))
        tipo = str(row.get("tipo_recurso_propuesto", "Herramienta"))
        desc = info.get("description", "")

        row_dict = row.to_dict()
        row_dict["categoria_validada"] = cat
        row_dict["tipo_recurso_validado"] = tipo
        row_dict["descripcion"] = desc
        row_dict["problema_que_resuelve"] = f"Solución de {cat.lower()}: {desc}"
        row_dict["casos_de_uso"] = f"Integración B2B y arquitectura de software para {cat.lower()}."
        row_dict["lenguaje"] = info.get("language", "No especificado")
        row_dict["estrellas"] = info.get("stars", 0)
        row_dict["forks"] = info.get("forks", 0)
        row_dict["open_issues"] = info.get("open_issues", 0)
        row_dict["licencia"] = info.get("license", "N/A")
        row_dict["url_github"] = info.get("html_url")
        row_dict["archived"] = info.get("archived")
        row_dict["disabled"] = info.get("disabled")
        row_dict["fecha_descarga"] = info.get("fecha_descarga")
        row_dict["commits_90d"] = info.get("commits_90d")
        row_dict["fecha_ultimo_commit"] = info.get("fecha_ultimo_commit")
        row_dict["issues_abiertos"] = info.get("issues_abiertos")
        row_dict["issues_cerrados"] = info.get("issues_cerrados")
        row_dict["prs_abiertos"] = info.get("prs_abiertos")
        row_dict["prs_cerrados"] = info.get("prs_cerrados")
        row_dict["mediana_dias_cierre_issues"] = info.get("mediana_dias_cierre_issues")
        row_dict["mediana_dias_merge_prs"] = info.get("mediana_dias_merge_prs")
        row_dict["contribuidores"] = info.get("contribuidores")
        row_dict["tiene_release"] = info.get("tiene_release")
        row_dict["tiene_tags"] = info.get("tiene_tags")
        row_dict["fecha_ultimo_release"] = info.get("fecha_ultimo_release")
        row_dict["consideraciones_integracion"] = "Despliegue vía Docker o consumo mediante API REST / SDK."

        registros.append(row_dict)

    df_result = pd.DataFrame(registros)
    df_result.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ Catálogo enriquecido con métricas de salud guardado en: {output_csv}")


if __name__ == "__main__":
    enriquecer_catalogo()




# import os
# import datetime
# import requests
# import numpy as np
# import pandas as pd

# GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# def obtener_detalles_github(nombre_completo):
#     headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
#     base_url = f"https://api.github.com/repos/{nombre_completo}"
    
#     res_data = {
#         "full_name": nombre_completo,
#         "description": "",
#         "language": "Multi-lenguaje",
#         "stars": 0,
#         "forks": 0,
#         "open_issues": 0,
#         "license": "N/A",
#         "html_url": f"https://github.com/{nombre_completo}",
#         "archived": False,
#         "disabled": False,
#         "fecha_descarga": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
#         "commits_90d": 0,
#         "fecha_ultimo_commit": None,
#         "issues_abiertos": 0,
#         "issues_cerrados": 0,
#         "prs_abiertos": 0,
#         "prs_cerrados": 0,
#         "mediana_dias_cierre_issues": None,
#         "mediana_dias_merge_prs": None,
#         "contribuidores": 0,
#         "tiene_release": False,
#         "tiene_tags": False,
#         "fecha_ultimo_release": None
#     }

#     try:
#         r = requests.get(base_url, headers=headers, timeout=10)
#         if r.status_code == 200:
#             d = r.json()
#             res_data["description"] = d.get("description") or ""
#             res_data["language"] = d.get("language") or "No especificado"
#             res_data["stars"] = d.get("stargazers_count", 0)
#             res_data["forks"] = d.get("forks_count", 0)
#             res_data["open_issues"] = d.get("open_issues_count", 0)
#             res_data["archived"] = d.get("archived", False)
#             res_data["disabled"] = d.get("disabled", False)
#             res_data["html_url"] = d.get("html_url", f"https://github.com/{nombre_completo}")
            
#             lic = d.get("license")
#             if isinstance(lic, dict):
#                 res_data["license"] = lic.get("spdx_id") or "N/A"

#         # 1. Commits últimos 90 días y fecha último commit
#         hace_90d = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)).isoformat()
#         r_commits = requests.get(f"{base_url}/commits?since={hace_90d}&per_page=100", headers=headers, timeout=10)
#         if r_commits.status_code == 200:
#             commits = r_commits.json()
#             if isinstance(commits, list):
#                 res_data["commits_90d"] = len(commits)
#                 if len(commits) > 0:
#                     res_data["fecha_ultimo_commit"] = commits[0].get("commit", {}).get("committer", {}).get("date")

#         # 2. Contribuidores (descartando Bots)
#         r_contrib = requests.get(f"{base_url}/contributors?per_page=100", headers=headers, timeout=10)
#         if r_contrib.status_code == 200:
#             contribs = r_contrib.json()
#             if isinstance(contribs, list):
#                 humanos = [c for c in contribs if isinstance(c, dict) and c.get("type") != "Bot"]
#                 res_data["contribuidores"] = len(humanos)

#         # 3. Releases y Tags
#         r_rel = requests.get(f"{base_url}/releases/latest", headers=headers, timeout=10)
#         if r_rel.status_code == 200:
#             res_data["tiene_release"] = True
#             res_data["fecha_ultimo_release"] = r_rel.json().get("published_at")

#         r_tags = requests.get(f"{base_url}/tags?per_page=1", headers=headers, timeout=10)
#         if r_tags.status_code == 200 and len(r_tags.json()) > 0:
#             res_data["tiene_tags"] = True

#     except Exception as e:
#         print(f"    ⚠️ Error en API para {nombre_completo}: {e}")

#     return res_data

# def enriquecer_catalogo():
#     input_path = "data/catalogo_base.csv"
#     output_csv = "data/catalogo_enriquecido_100.csv"
    
#     if not os.path.exists(input_path):
#         print(f"❌ No se encontró el archivo: {input_path}")
#         return

#     df = pd.read_csv(input_path)
#     print(f"🔄 Enriqueciendo {len(df)} repositorios con métricas de salud avanzadas...")

#     columnas_nuevas = [
#         "categoria_validada", "tipo_recurso_validado", "descripcion", "problema_que_resuelve",
#         "casos_de_uso", "lenguaje", "estrellas", "forks", "open_issues", "licencia", "url_github",
#         "archived", "disabled", "fecha_descarga", "commits_90d", "fecha_ultimo_commit",
#         "issues_abiertos", "issues_cerrados", "prs_abiertos", "prs_cerrados",
#         "mediana_dias_cierre_issues", "mediana_dias_merge_prs", "contribuidores",
#         "tiene_release", "tiene_tags", "fecha_ultimo_release", "consideraciones_integracion"
#     ]

#     registros = []

#     for idx, row in df.iterrows():
#         nombre = row['nombre_completo']
#         print(f"  --> [{idx+1}/100] Procesando métricas: {nombre}")
#         info = obtener_detalles_github(nombre)
        
#         cat = str(row.get('categoria_propuesta', 'General'))
#         tipo = str(row.get('tipo_recurso_propuesto', 'Herramienta'))
#         desc = info.get('description', '')

#         row_dict = row.to_dict()
#         row_dict['categoria_validada'] = cat
#         row_dict['tipo_recurso_validado'] = tipo
#         row_dict['descripcion'] = desc
#         row_dict['problema_que_resuelve'] = f"Solución de {cat.lower()}: {desc}"
#         row_dict['casos_de_uso'] = f"Integración B2B y arquitectura de software para {cat.lower()}."
#         row_dict['lenguaje'] = info.get('language', 'No especificado')
#         row_dict['estrellas'] = info.get('stars', 0)
#         row_dict['forks'] = info.get('forks', 0)
#         row_dict['open_issues'] = info.get('open_issues', 0)
#         row_dict['licencia'] = info.get('license', 'N/A')
#         row_dict['url_github'] = info.get('html_url')
#         row_dict['archived'] = info.get('archived')
#         row_dict['disabled'] = info.get('disabled')
#         row_dict['fecha_descarga'] = info.get('fecha_descarga')
#         row_dict['commits_90d'] = info.get('commits_90d')
#         row_dict['fecha_ultimo_commit'] = info.get('fecha_ultimo_commit')
#         row_dict['issues_abiertos'] = info.get('issues_abiertos')
#         row_dict['issues_cerrados'] = info.get('issues_cerrados')
#         row_dict['prs_abiertos'] = info.get('prs_abiertos')
#         row_dict['prs_cerrados'] = info.get('prs_cerrados')
#         row_dict['mediana_dias_cierre_issues'] = info.get('mediana_dias_cierre_issues')
#         row_dict['mediana_dias_merge_prs'] = info.get('mediana_dias_merge_prs')
#         row_dict['contribuidores'] = info.get('contribuidores')
#         row_dict['tiene_release'] = info.get('tiene_release')
#         row_dict['tiene_tags'] = info.get('tiene_tags')
#         row_dict['fecha_ultimo_release'] = info.get('fecha_ultimo_release')
#         row_dict['consideraciones_integracion'] = "Despliegue vía Docker o consumo mediante API REST / SDK."

#         registros.append(row_dict)

#     df_result = pd.DataFrame(registros)
#     df_result.to_csv(output_csv, index=False, encoding='utf-8-sig')
#     print(f"\n✅ Catálogo enriquecido con métricas de salud guardado en: {output_csv}")

# if __name__ == "__main__":
#     enriquecer_catalogo()