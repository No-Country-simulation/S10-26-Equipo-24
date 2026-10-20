import os
import requests
import pandas as pd
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def obtener_metadatos_github(repo_url):
    """
    Extrae owner/repo de la URL y consulta la API REST/GraphQL de GitHub.
    """
    if not isinstance(repo_url, str) or "github.com/" not in repo_url:
        return {"valido": False, "error": "URL inválida"}
    
    # Extraer usuario/organizacion y nombre del repositorio
    partes = repo_url.rstrip("/").split("github.com/")[-1].split("/")
    if len(partes) < 2:
        return {"valido": False, "error": "Formato de URL incorrecto"}
    
    owner, repo = partes[0], partes[1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "valido": True,
                "stars": data.get("stargazers_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "last_update": data.get("updated_at"),
                "license": data.get("license", {}).get("spdx_id") if data.get("license") else "N/A",
                "language": data.get("language", "Unkown"),
                "description_github": data.get("description", "")
            }
        elif response.status_code == 404:
            return {"valido": False, "error": "Repositorio no encontrado (404)"}
        else:
            return {"valido": False, "error": f"API Error HTTP {response.status_code}"}
    except Exception as e:
        return {"valido": False, "error": str(e)}

def procesar_csv_catalogo(input_filepath, output_filepath):
    print(f" Cargando archivo desde: {input_filepath}")
    df = pd.read_csv(input_filepath)
    
    # Identificar la columna que contiene la URL de GitHub
    col_url = [c for c in df.columns if "url" in c.lower() or "repo" in c.lower() or "github" in c.lower()]
    if not col_url:
        print(" Error: No se encontró una columna con URLs de GitHub en el CSV.")
        return
    
    target_col = col_url[0]
    print(f" Analizando la columna de URLs: '{target_col}'...")

    # Listas para acumular resultados
    resultados = []
    
    for idx, row in df.iterrows():
        url = row[target_col]
        print(f"[{idx+1}/{len(df)}] Validando {url}...")
        meta = obtener_metadatos_github(url)
        resultados.append(meta)
    
    # Convertir resultados a DataFrame y concatenar
    df_meta = pd.DataFrame(resultados)
    df_final = pd.concat([df, df_meta], axis=1)
    
    # Guardar CSV procesado
    df_final.to_csv(output_filepath, index=False)
    print(f"\n Procesamiento completado. Archivo guardado en: {output_filepath}")

if __name__ == "__main__":
    # Ruta del archivo base enviado por Yani (actualizar según corresponda)
    input_csv = "data/catalogo_base.csv"
    output_csv = "data/catalogo_actualizado.csv"
    
    if os.path.exists(input_csv):
        procesar_csv_catalogo(input_csv, output_csv)
    else:
        print(f" Archivo no encontrado: {input_csv}. Verificá el nombre dentro de 'data/'.")
        