import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("ERROR: DATABASE_URL no está configurada en el archivo .env")

# 2. Priorizar el dataset activo y unificado del pipeline (catalogo_actualizado.csv)
BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "..", "..", "data", "catalogo_actualizado.csv")

if not os.path.exists(CSV_PATH):
    CSV_PATH = os.path.join(BASE_DIR, "..", "..", "data", "catalogo_enriquecido_100.csv")

print(f"📂 Leyendo archivo CSV desde: {CSV_PATH}")
df = pd.read_csv(CSV_PATH)

# Función de extracción flexible (soporta nombres de columnas en español e inglés)
def get_val(row, *keys, default=None):
    for key in keys:
        if key in row and pd.notna(row[key]):
            val = str(row[key]).strip()
            if val and val.lower() not in ['nan', 'none', 'null']:
                return row[key]
    return default

# Función para calcular el Health Score de 4 dimensiones (0 a 100)
def calcular_health_score(row):
    stars = float(get_val(row, 'stars', 'estrellas', default=0) or 0)
    forks = float(get_val(row, 'forks_actual', 'forks', default=0) or 0)
    commits = float(get_val(row, 'commits_90d', default=0) or 0)
    contribs = float(get_val(row, 'contribuidores', 'contributors', default=0) or 0)
    licencia = str(get_val(row, 'license', 'licencia', default='')).lower()

    # Dimensión 1: Popularidad (0 a 30 pts) -> Basado en estrellas y forks
    pop_score = min(30.0, (stars / 1000.0) * 15.0 + (forks / 200.0) * 15.0)

    # Dimensión 2: Actividad reciente (0 a 30 pts) -> Commits en últimos 90 días
    act_score = min(30.0, (commits / 50.0) * 30.0)

    # Dimensión 3: Comunidad (0 a 25 pts) -> Cantidad de contribuidores
    com_score = min(25.0, (contribs / 20.0) * 25.0)

    # Dimensión 4: Mantenimiento & Licencia (0 a 15 pts)
    lic_score = 15.0 if licencia and licencia not in ['unspecified', 'nan', 'none', 'n/a', ''] else 0.0

    total = round(pop_score + act_score + com_score + lic_score, 2)
    return min(100.0, total)

# Calcular Health Score
df['health_score_calc'] = df.apply(calcular_health_score, axis=1)

# 3. Conectar a Supabase PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

updated_count = 0
skipped_count = 0
print("🚀 Sincronizando métricas y Health Score en Supabase de forma segura...")

try:
    for idx, row in df.iterrows():
        # Extracción flexible y segura de datos
        github_id = get_val(row, 'github_id', 'id')
        full_name = get_val(row, 'full_name', 'nombre_completo', 'name')
        
        stars = int(get_val(row, 'stars', 'estrellas', default=0) or 0)
        forks = int(get_val(row, 'forks_actual', 'forks', default=0) or 0)
        commits = int(get_val(row, 'commits_90d', default=0) or 0)
        contribs = int(get_val(row, 'contribuidores', 'contributors', default=0) or 0)
        license_type = str(get_val(row, 'license', 'licencia', default='Unspecified')).strip()
        health_score = float(row.get('health_score_calc', 0.0))

        if license_type.lower() in ['nan', 'none', 'n/a', '']:
            license_type = 'Unspecified'

        # CONDICIÓN DE BÚSQUEDA SEGURA Y ESTRICTA:
        # Prioriza github_id (que es único e inmutable), luego full_name exacto.
        if github_id:
            update_query = """
                UPDATE repositories
                SET stars = %s,
                    forks = %s,
                    commits_90d = %s,
                    contribuidores = %s,
                    license = %s,
                    health_score = %s
                WHERE github_id = %s;
            """
            cur.execute(update_query, (stars, forks, commits, contribs, license_type, health_score, int(github_id)))
        elif full_name:
            update_query = """
                UPDATE repositories
                SET stars = %s,
                    forks = %s,
                    commits_90d = %s,
                    contribuidores = %s,
                    license = %s,
                    health_score = %s
                WHERE full_name = %s;
            """
            cur.execute(update_query, (stars, forks, commits, contribs, license_type, health_score, full_name))
        else:
            skipped_count += 1
            continue

        if cur.rowcount > 0:
            updated_count += 1

    conn.commit()
    print(f"✅ ¡Éxito! Se actualizaron con éxito {updated_count} repositorios en Supabase de forma individual.")
    if skipped_count > 0:
        print(f"⚠️ Se omitieron {skipped_count} filas por no tener ni github_id ni full_name.")

except Exception as e:
    conn.rollback()
    print(f"❌ Error al actualizar métricas: {str(e)}")

finally:
    cur.close()
    conn.close()