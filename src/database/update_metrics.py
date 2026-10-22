import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("ERROR: DATABASE_URL no está configurada en el archivo .env")

# 2. Ruta del CSV
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalogo_enriquecido_100.csv")
if not os.path.exists(CSV_PATH):
    CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalogo_actualizado.csv")

print(f"📂 Leyendo archivo CSV desde: {CSV_PATH}")
df = pd.read_csv(CSV_PATH)

# Función para calcular el Health Score de 4 dimensiones (0 a 100)
def calcular_health_score(row):
    stars = float(row.get('stars', 0) or 0)
    forks = float(row.get('forks_actual', row.get('forks', 0)) or 0)
    commits = float(row.get('commits_90d', 0) or 0)
    contribs = float(row.get('contribuidores', 0) or 0)
    licencia = str(row.get('license', '')).lower()

    # Dimensión 1: Popularidad (0 a 30 pts) -> Basado en estrellas y forks
    pop_score = min(30.0, (stars / 1000.0) * 15.0 + (forks / 200.0) * 15.0)

    # Dimensión 2: Actividad reciente (0 a 30 pts) -> Commits en últimos 90 días
    act_score = min(30.0, (commits / 50.0) * 30.0)

    # Dimensión 3: Comunidad (0 a 25 pts) -> Cantidad de contribuidores
    com_score = min(25.0, (contribs / 20.0) * 25.0)

    # Dimensión 4: Mantenimiento & Licencia (0 a 15 pts)
    lic_score = 15.0 if licencia and licencia not in ['unspecified', 'nan', 'none'] else 0.0

    total = round(pop_score + act_score + com_score + lic_score, 2)
    return min(100.0, total)

# Sanitizar y calcular Health Score
df['health_score_calc'] = df.apply(calcular_health_score, axis=1)

# 3. Conectar a Supabase PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

updated_count = 0
print("🚀 Sincronizando forks_actual y Health Score en Supabase...")

try:
    for idx, row in df.iterrows():
        full_name = str(row.get('full_name') or row.get('name') or '').strip()
        stars = int(row.get('stars', 0) or 0)
        
        # Mapeo prioritario de forks_actual
        forks = int(row.get('forks_actual', row.get('forks', 0)) or 0)
        commits = int(row.get('commits_90d', 0) or 0)
        contribs = int(row.get('contribuidores', 0) or 0)
        license_type = str(row.get('license', 'Unspecified')).strip()
        health_score = float(row.get('health_score_calc', 0.0))

        if license_type.lower() in ['nan', '']:
            license_type = 'Unspecified'

        update_query = """
            UPDATE repositories
            SET stars = %s,
                forks = %s,
                commits_90d = %s,
                contribuidores = %s,
                license = %s,
                health_score = %s
            WHERE full_name = %s OR html_url LIKE %s;
        """
        
        url_pattern = f"%{full_name}%" if full_name else "%"
        cur.execute(update_query, (stars, forks, commits, contribs, license_type, health_score, full_name, url_pattern))
        
        if cur.rowcount > 0:
            updated_count += 1

    conn.commit()
    print(f"✅ ¡Éxito! Se actualizaron con éxito las métricas y Health Score de {updated_count} repositorios en Supabase.")

except Exception as e:
    conn.rollback()
    print(f"❌ Error al actualizar métricas: {str(e)}")

finally:
    cur.close()
    conn.close()