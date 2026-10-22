import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("ERROR: DATABASE_URL no está configurada en el archivo .env")

# Definición de las 10 categorías funcionales
CATEGORIES = [
    ("Inteligencia Artificial & ML", "LLMs, modelos, visión por computadora, NLP y herramientas de IA."),
    ("Bases de Datos & Almacenamiento", "Bases de datos SQL/NoSQL, ORMs, cachés y motores vectoriales."),
    ("APIs, Backend & Microservicios", "Frameworks backend, servidores web, GraphQL y arquitecturas de APIs."),
    ("Frontend & Frameworks UI", "Librerías de interfaz gráfica, componentes web, CSS y frameworks JS."),
    ("Seguridad & Autenticación", "Gestión de identidad, OAuth, encriptación y análisis de seguridad."),
    ("DevOps, CI/CD & Cloud", "Contenedores, orquestación, automatización de despliegues e infraestructura."),
    ("Monitoreo & Observabilidad", "Métricas, trazas, generación de logs y tableros de rendimiento."),
    ("Analítica & Big Data", "Pipelines de datos, procesamiento masivo, ETL y visualización."),
    ("Desarrollo Mobile", "Frameworks y herramientas para desarrollo iOS, Android y multiplataforma."),
    ("Herramientas & Utilidades", "Linter, herramientas CLI, pruebas unitarias y automatización general.")
]

# Reglas de mapeo por palabras clave (en descripción, lenguaje y nombre)
def determinar_categoria(full_name, description, languages):
    text = f"{full_name} {description} {languages}".lower()

    if any(k in text for k in ['ai', 'llm', 'gpt', 'neural', 'machine learning', 'deep learning', 'model', 'embeddings', 'pytorch', 'tensorflow', 'rag', 'langchain']):
        return "Inteligencia Artificial & ML"
    elif any(k in text for k in ['database', 'db', 'sql', 'postgres', 'redis', 'mongo', 'vector', 'orm', 'storage', 'query', 'prisma', 'supabase']):
        return "Bases de Datos & Almacenamiento"
    elif any(k in text for k in ['api', 'backend', 'fastapi', 'express', 'rest', 'graphql', 'grpc', 'server', 'microservice', 'http', 'framework']):
        return "APIs, Backend & Microservicios"
    elif any(k in text for k in ['ui', 'frontend', 'react', 'vue', 'next', 'tailwind', 'component', 'css', 'dom', 'web-ui', 'interface']):
        return "Frontend & Frameworks UI"
    elif any(k in text for k in ['security', 'auth', 'oauth', 'jwt', 'crypto', 'encryption', 'vulnerability', 'scan', 'password']):
        return "Seguridad & Autenticación"
    elif any(k in text for k in ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'action', 'deploy', 'terraform', 'cloud', 'container']):
        return "DevOps, CI/CD & Cloud"
    elif any(k in text for k in ['monitor', 'metric', 'observability', 'log', 'trace', 'grafana', 'prometheus', 'telemetry']):
        return "Monitoreo & Observabilidad"
    elif any(k in text for k in ['data', 'analytics', 'bigdata', 'spark', 'etl', 'pandas', 'pipeline', 'warehouse']):
        return "Analítica & Big Data"
    elif any(k in text for k in ['mobile', 'flutter', 'react-native', 'ios', 'android', 'swift', 'kotlin']):
        return "Desarrollo Mobile"
    else:
        return "Herramientas & Utilidades"

# Ejecución del rebalanceo
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    print("🚀 Asegurando las 10 categorías funcionales en Supabase...")
    category_map = {}
    for name, desc in CATEGORIES:
        cur.execute("""
            INSERT INTO categories (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id, name;
        """, (name, desc))
        cat_id, cat_name = cur.fetchone()
        category_map[cat_name] = cat_id

    conn.commit()

    print("🔍 Obteniendo repositorios para redefinir categorías...")
    cur.execute("SELECT id, full_name, description, languages FROM repositories;")
    repos = cur.fetchall()

    reassigned = 0
    for repo_id, full_name, description, languages in repos:
        cat_name = determinar_categoria(full_name, description or "", languages or "")
        cat_id = category_map[cat_name]

        cur.execute("UPDATE repositories SET category_id = %s WHERE id = %s;", (cat_id, repo_id))
        reassigned += 1

    conn.commit()
    print(f"✅ ¡Rebalanceo completado con éxito! Se redefinieron las categorías de {reassigned} repositorios.")

    # Conteo de verificación por categoría
    cur.execute("""
        SELECT c.name, COUNT(r.id) as total
        FROM categories c
        LEFT JOIN repositories r ON r.category_id = c.id
        GROUP BY c.name
        ORDER BY total DESC;
    """)
    stats = cur.fetchall()
    print("\n📊 Nueva distribución por categoría:")
    for cat, count in stats:
        print(f" - {cat}: {count} repositorios")

except Exception as e:
    conn.rollback()
    print(f"❌ Error durante el rebalanceo: {str(e)}")

finally:
    cur.close()
    conn.close()