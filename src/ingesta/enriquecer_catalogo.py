import os
import datetime
import requests
import numpy as np
import pandas as pd

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def obtener_detalles_github(nombre_completo):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    base_url = f"https://api.github.com/repos/{nombre_completo}"
    
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
        "fecha_descarga": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "commits_90d": 0,
        "fecha_ultimo_commit": None,
        "issues_abiertos": 0,
        "issues_cerrados": 0,
        "prs_abiertos": 0,
        "prs_cerrados": 0,
        "mediana_dias_cierre_issues": None,
        "mediana_dias_merge_prs": None,
        "contribuidores": 0,
        "tiene_release": False,
        "tiene_tags": False,
        "fecha_ultimo_release": None
    }

    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        if r.status_code == 200:
            d = r.json()
            res_data["description"] = d.get("description") or ""
            res_data["language"] = d.get("language") or "No especificado"
            res_data["stars"] = d.get("stargazers_count", 0)
            res_data["forks"] = d.get("forks_count", 0)
            res_data["open_issues"] = d.get("open_issues_count", 0)
            res_data["archived"] = d.get("archived", False)
            res_data["disabled"] = d.get("disabled", False)
            res_data["html_url"] = d.get("html_url", f"https://github.com/{nombre_completo}")
            
            lic = d.get("license")
            if isinstance(lic, dict):
                res_data["license"] = lic.get("spdx_id") or "N/A"

        # 1. Commits últimos 90 días y fecha último commit
        hace_90d = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)).isoformat()
        r_commits = requests.get(f"{base_url}/commits?since={hace_90d}&per_page=100", headers=headers, timeout=10)
        if r_commits.status_code == 200:
            commits = r_commits.json()
            if isinstance(commits, list):
                res_data["commits_90d"] = len(commits)
                if len(commits) > 0:
                    res_data["fecha_ultimo_commit"] = commits[0].get("commit", {}).get("committer", {}).get("date")

        # 2. Contribuidores (descartando Bots)
        r_contrib = requests.get(f"{base_url}/contributors?per_page=100", headers=headers, timeout=10)
        if r_contrib.status_code == 200:
            contribs = r_contrib.json()
            if isinstance(contribs, list):
                humanos = [c for c in contribs if isinstance(c, dict) and c.get("type") != "Bot"]
                res_data["contribuidores"] = len(humanos)

        # 3. Releases y Tags
        r_rel = requests.get(f"{base_url}/releases/latest", headers=headers, timeout=10)
        if r_rel.status_code == 200:
            res_data["tiene_release"] = True
            res_data["fecha_ultimo_release"] = r_rel.json().get("published_at")

        r_tags = requests.get(f"{base_url}/tags?per_page=1", headers=headers, timeout=10)
        if r_tags.status_code == 200 and len(r_tags.json()) > 0:
            res_data["tiene_tags"] = True

    except Exception as e:
        print(f"    ⚠️ Error en API para {nombre_completo}: {e}")

    return res_data

def enriquecer_catalogo():
    input_path = "data/catalogo_base.csv"
    output_csv = "data/catalogo_enriquecido_100.csv"
    
    if not os.path.exists(input_path):
        print(f"❌ No se encontró el archivo: {input_path}")
        return

    df = pd.read_csv(input_path)
    print(f"🔄 Enriqueciendo {len(df)} repositorios con métricas de salud avanzadas...")

    columnas_nuevas = [
        "categoria_validada", "tipo_recurso_validado", "descripcion", "problema_que_resuelve",
        "casos_de_uso", "lenguaje", "estrellas", "forks", "open_issues", "licencia", "url_github",
        "archived", "disabled", "fecha_descarga", "commits_90d", "fecha_ultimo_commit",
        "issues_abiertos", "issues_cerrados", "prs_abiertos", "prs_cerrados",
        "mediana_dias_cierre_issues", "mediana_dias_merge_prs", "contribuidores",
        "tiene_release", "tiene_tags", "fecha_ultimo_release", "consideraciones_integracion"
    ]

    registros = []

    for idx, row in df.iterrows():
        nombre = row['nombre_completo']
        print(f"  --> [{idx+1}/100] Procesando métricas: {nombre}")
        info = obtener_detalles_github(nombre)
        
        cat = str(row.get('categoria_propuesta', 'General'))
        tipo = str(row.get('tipo_recurso_propuesto', 'Herramienta'))
        desc = info.get('description', '')

        row_dict = row.to_dict()
        row_dict['categoria_validada'] = cat
        row_dict['tipo_recurso_validado'] = tipo
        row_dict['descripcion'] = desc
        row_dict['problema_que_resuelve'] = f"Solución de {cat.lower()}: {desc}"
        row_dict['casos_de_uso'] = f"Integración B2B y arquitectura de software para {cat.lower()}."
        row_dict['lenguaje'] = info.get('language', 'No especificado')
        row_dict['estrellas'] = info.get('stars', 0)
        row_dict['forks'] = info.get('forks', 0)
        row_dict['open_issues'] = info.get('open_issues', 0)
        row_dict['licencia'] = info.get('license', 'N/A')
        row_dict['url_github'] = info.get('html_url')
        row_dict['archived'] = info.get('archived')
        row_dict['disabled'] = info.get('disabled')
        row_dict['fecha_descarga'] = info.get('fecha_descarga')
        row_dict['commits_90d'] = info.get('commits_90d')
        row_dict['fecha_ultimo_commit'] = info.get('fecha_ultimo_commit')
        row_dict['issues_abiertos'] = info.get('issues_abiertos')
        row_dict['issues_cerrados'] = info.get('issues_cerrados')
        row_dict['prs_abiertos'] = info.get('prs_abiertos')
        row_dict['prs_cerrados'] = info.get('prs_cerrados')
        row_dict['mediana_dias_cierre_issues'] = info.get('mediana_dias_cierre_issues')
        row_dict['mediana_dias_merge_prs'] = info.get('mediana_dias_merge_prs')
        row_dict['contribuidores'] = info.get('contribuidores')
        row_dict['tiene_release'] = info.get('tiene_release')
        row_dict['tiene_tags'] = info.get('tiene_tags')
        row_dict['fecha_ultimo_release'] = info.get('fecha_ultimo_release')
        row_dict['consideraciones_integracion'] = "Despliegue vía Docker o consumo mediante API REST / SDK."

        registros.append(row_dict)

    df_result = pd.DataFrame(registros)
    df_result.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n✅ Catálogo enriquecido con métricas de salud guardado en: {output_csv}")

if __name__ == "__main__":
    enriquecer_catalogo()