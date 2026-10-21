import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("ERROR: DATABASE_URL no está configurada en el archivo .env")

# 2. Rutas del archivo de datos
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalogo_enriquecido_100.csv")
if not os.path.exists(CSV_PATH):
    CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalogo_actualizado.csv")

print(f"📂 Leyendo archivo CSV desde: {CSV_PATH}")
df = pd.read_csv(CSV_PATH)

# Sanitizar valores nulos/NaN para PostgreSQL
df = df.fillna({
    'stars': 0,
    'forks': 0,
    'commits_90d': 0,
    'contribuidores': 0,
    'health_score': 0.0,
    'license': 'Unspecified'
})

# 3. Conectar a Supabase PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

updated_count = 0

print("🚀 Sincronizando métricas en Supabase...")

try:
    for idx, row in df.iterrows():
        # Extracción segura de datos del CSV
        full_name = str(row.get('full_name') or row.get('name') or '').strip()
        stars = int(row.get('stars', 0))
        forks = int(row.get('forks', 0))
        commits = int(row.get('commits_90d', 0))
        contribs = int(row.get('contribuidores', 0))
        license_type = str(row.get('license', 'Unspecified')).strip()
        
        if license_type.lower() == 'nan' or not license_type:
            license_type = 'Unspecified'

        # Query de actualización por full_name o coincidencia de URL
        update_query = """
            UPDATE repositories
            SET stars = %s,
                forks = %s,
                commits_90d = %s,
                contribuidores = %s,
                license = %s
            WHERE full_name = %s OR html_url LIKE %s;
        """
        
        url_pattern = f"%{full_name}%" if full_name else "%"
        
        cur.execute(update_query, (stars, forks, commits, contribs, license_type, full_name, url_pattern))
        
        if cur.rowcount > 0:
            updated_count += 1

    conn.commit()
    print(f"✅ Se actualizaron con éxito las métricas de {updated_count} repositorios en Supabase.")

except Exception as e:
    conn.rollback()
    print(f"❌ Error al actualizar métricas: {str(e)}")

finally:
    cur.close()
    conn.close()