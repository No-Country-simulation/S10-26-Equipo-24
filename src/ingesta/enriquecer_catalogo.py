import os
import re
import datetime
import requests
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def obtener_detalles_github(nombre_completo):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    base_url = f"https://api.github.com/repos/{nombre_completo}"
    
    res_data = {
        "full_name": nombre_completo,
        "description": "",
        "language": "No especificado",
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
        "contribuidores": 0,
        "tiene_release": False,
        "tiene_tags": False,
        "fecha_ultimo_release": None,
        "api_status": "ERROR"  # Indica si la API respondió correctamente
    }

    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        
        # Si el repositorio no existe o falla la autenticación, registramos el fallo
        if r.status_code != 200:
            print(f"    ⚠️ Error HTTP {r.status_code} al consultar API para {nombre_completo}")
            return res_data

        d = r.json()
        res_data["api_status"] = "OK"
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

        # 1. Commits en los últimos 90 días (PAGINADO)
        hace_90d = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)).isoformat()
        total_commits_90d = 0
        page = 1
        
        while True:
            r_commits = requests.get(
                f"{base_url}/commits?since={hace_90d}&per_page=100&page={page}", 
                headers=headers, 
                timeout=10
            )
            if r_commits.status_code == 200:
                commits = r_commits.json()
                if isinstance(commits, list) and len(commits) > 0:
                    if page == 1:
                        res_data["fecha_ultimo_commit"] = commits[0].get("commit", {}).get("committer", {}).get("date")
                    total_commits_90d += len(commits)
                    if len(commits) < 100 or page >= 5:  # Límite de seguridad de 500 commits para evitar rate limits
                        break
                    page += 1
                else:
                    break
            else:
                break
        res_data["commits_90d"] = total_commits_90d

        # 2. Contribuidores con paginación optimizada vía Header Link o lista
        r_contrib = requests.get(f"{base_url}/contributors?per_page=100", headers=headers, timeout=10)
        if r_contrib.status_code == 200:
            link_header = r_contrib.headers.get("Link", "")
            if 'rel="last"' in link_header:
                # Extrae el número total de páginas desde el header rel="last"
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    res_data["contribuidores"] = int(match.group(1)) * 100
                else:
                    contribs = r_contrib.json()
                    res_data["contribuidores"] = len([c for c in contribs if isinstance(c, dict) and c.get("type") != "Bot"])
            else:
                contribs = r_contrib.json()
                if isinstance(contribs, list):
                    res_data["contribuidores"] = len([c for c in contribs if isinstance(c, dict) and c.get("type") != "Bot"])

        # 3. Releases y Tags
        r_rel = requests.get(f"{base_url}/releases/latest", headers=headers, timeout=10)
        if r_rel.status_code == 200:
            res_data["tiene_release"] = True
            res_data["fecha_ultimo_release"] = r_rel.json().get("published_at")

        r_tags = requests.get(f"{base_url}/tags?per_page=1", headers=headers, timeout=10)
        if r_tags.status_code == 200 and isinstance(r_tags.json(), list) and len(r_tags.json()) > 0:
            res_data["tiene_tags"] = True

    except Exception as e:
        print(f"    ⚠️ Excepción al conectar con la API para {nombre_completo}: {e}")

    return res_data

def enriquecer_catalogo():
    BASE_DIR = os.path.dirname(__file__)
    input_path = os.path.join(BASE_DIR, "..", "..", "data", "catalogo_base.csv")
    output_csv = os.path.join(BASE_DIR, "..", "..", "data", "catalogo_enriquecido_100.csv")
    
    if not os.path.exists(input_path):
        input_path = "data/catalogo_base.csv"
        output_csv = "data/catalogo_enriquecido_100.csv"

    if not os.path.exists(input_path):
        print(f"❌ No se encontró el archivo de entrada en: {input_path}")
        return

    df = pd.read_csv(input_path)
    print(f"🔄 Enriqueciendo {len(df)} repositorios con métricas de salud avanzadas...")

    registros = []

    for idx, row in df.iterrows():
        nombre = row.get('nombre_completo') or row.get('full_name')
        print(f"  --> [{idx+1}/{len(df)}] Procesando métricas: {nombre}")
        info = obtener_detalles_github(nombre)
        
        cat = str(row.get('categoria_propuesta', row.get('categoria', 'General')))
        tipo = str(row.get('tipo_recurso_propuesto', row.get('tipo_recurso', 'Herramienta')))
        desc = info.get('description', '')

        row_dict = row.to_dict()
        row_dict['categoria_validada'] = cat
        row_dict['tipo_recurso_validado'] = tipo
        row_dict['descripcion'] = desc
        row_dict['problema_que_resuelve'] = f"Solución de {cat.lower()}: {desc}"
        row_dict['casos_de_uso'] = f"Integración B2B y arquitectura de software para {cat.lower()}."
        row_dict['lenguaje'] = info.get('language', 'No especificado')
        row_dict['estrellas'] = info.get('stars', 0)
        row_dict['stars'] = info.get('stars', 0)
        row_dict['forks'] = info.get('forks', 0)
        row_dict['open_issues'] = info.get('open_issues', 0)
        row_dict['licencia'] = info.get('license', 'N/A')
        row_dict['license'] = info.get('license', 'N/A')
        row_dict['url_github'] = info.get('html_url')
        row_dict['archived'] = info.get('archived')
        row_dict['disabled'] = info.get('disabled')
        row_dict['fecha_descarga'] = info.get('fecha_descarga')
        row_dict['commits_90d'] = info.get('commits_90d')
        row_dict['fecha_ultimo_commit'] = info.get('fecha_ultimo_commit')
        row_dict['contribuidores'] = info.get('contribuidores')
        row_dict['tiene_release'] = info.get('tiene_release')
        row_dict['tiene_tags'] = info.get('tiene_tags')
        row_dict['fecha_ultimo_release'] = info.get('fecha_ultimo_release')
        row_dict['api_status'] = info.get('api_status')

        registros.append(row_dict)

    df_result = pd.DataFrame(registros)
    df_result.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n✅ Catálogo enriquecido guardado con éxito en: {output_csv}")

if __name__ == "__main__":
    enriquecer_catalogo()