import os
import requests
import pandas as pd

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def obtener_detalles_github(nombre_completo):
    url = f"https://api.github.com/repos/{nombre_completo}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return {
                "valido": True,
                "description": data.get("description") or "",
                "language": data.get("language") or "Multi-lenguaje",
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "license": data.get("license", {}).get("spdx_id") if isinstance(data.get("license"), dict) else "N/A",
                "html_url": data.get("html_url", f"https://github.com/{nombre_completo}")
            }
        return {"valido": False, "html_url": f"https://github.com/{nombre_completo}"}
    except Exception:
        return {"valido": False, "html_url": f"https://github.com/{nombre_completo}"}

def enriquecer_catalogo():
    input_path = "data/catalogo_base.csv"
    output_csv = "data/catalogo_enriquecido_100.csv"
    
    if not os.path.exists(input_path):
        print(f"❌ No se encontró el archivo: {input_path}")
        return

    df = pd.read_csv(input_path)
    print(f"🔄 Enriqueciendo {len(df)} repositorios desde data/catalogo_base.csv...")

    # Crear listas para almacenar los datos procesados sin conflictos de dtype
    categorias_validadas = []
    tipos_validados = []
    descripcion_list = []
    problema_list = []
    casos_list = []
    lenguaje_list = []
    estrellas_list = []
    forks_list = []
    issues_list = []
    licencia_list = []
    url_list = []
    integracion_list = []

    for idx, row in df.iterrows():
        nombre = row['nombre_completo']
        print(f"  --> [{idx+1}/100] Procesando: {nombre}")
        info = obtener_detalles_github(nombre)
        
        cat = str(row.get('categoria_propuesta', 'General'))
        tipo = str(row.get('tipo_recurso_propuesto', 'Herramienta'))
        desc = info.get('description', '')
        
        categorias_validadas.append(cat)
        tipos_validados.append(tipo)
        descripcion_list.append(desc)
        problema_list.append(f"Solución de {cat.lower()}: {desc}")
        casos_list.append(f"Integración B2B y arquitectura de software para {cat.lower()}.")
        lenguaje_list.append(info.get('language', 'No especificado'))
        estrellas_list.append(info.get('stars', 0))
        forks_list.append(info.get('forks', 0))
        issues_list.append(info.get('open_issues', 0))
        licencia_list.append(info.get('license', 'N/A'))
        url_list.append(info.get('html_url'))
        integracion_list.append("Despliegue vía Docker o consumo mediante API REST / SDK.")

    # Asignar todas las listas completas al DataFrame
    df['categoria_validada'] = categorias_validadas
    df['tipo_recurso_validado'] = tipos_validados
    df['descripcion'] = descripcion_list
    df['problema_que_resuelve'] = problema_list
    df['casos_de_uso'] = casos_list
    df['lenguaje'] = lenguaje_list
    df['estrellas'] = estrellas_list
    df['forks'] = forks_list
    df['open_issues'] = issues_list
    df['licencia'] = licencia_list
    df['url_github'] = url_list
    df['consideraciones_integracion'] = integracion_list

    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n✅ Catálogo enriquecido guardado exitosamente en: {output_csv}")

if __name__ == "__main__":
    enriquecer_catalogo()