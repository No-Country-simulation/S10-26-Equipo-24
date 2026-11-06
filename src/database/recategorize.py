import os
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("ERROR: DATABASE_URL no está configurada en el archivo .env")

# 10 Categorías Funcionales Oficiales
CATEGORIES = [
    ("Inteligencia Artificial & ML", "LLMs, modelos, visión por computadora, NLP, IA y agentes."),
    ("Bases de Datos & Almacenamiento", "Bases de datos SQL/NoSQL, ORMs, cachés, motores vectoriales y storage."),
    ("APIs, Backend & Microservicios", "Frameworks backend, servidores web, GraphQL, REST y microservicios."),
    ("Frontend & Frameworks UI", "Librerías de interfaz gráfica, componentes web, CSS y frameworks JS."),
    ("Seguridad & Autenticación", "Gestión de identidad, OAuth, encriptación, auth y análisis de seguridad."),
    ("DevOps, CI/CD & Cloud", "Contenedores, Docker, Kubernetes, automatización de despliegues e infraestructura."),
    ("Monitoreo & Observabilidad", "Métricas, trazas, generación de logs, observabilidad y tableros."),
    ("Analítica & Big Data", "Pipelines de datos, procesamiento masivo, ETL, Data Science y visualización."),
    ("Desarrollo Mobile", "Frameworks y herramientas para desarrollo iOS, Android y multiplataforma."),
    ("Herramientas & Utilidades", "Linter, CLI, testing, automatización, bibliotecas base y utilidades generales.")
]

def match_word(pattern: str, text: str) -> bool:
    """Evita falsos positivos con palabras cortas y machea frases compuestas."""
    if len(pattern) <= 3:
        return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text, re.IGNORECASE))
    return pattern.lower() in text.lower()

def determinar_categoria(full_name: str, description: str, languages: str) -> str:
    text = f"{full_name} {description} {languages}".lower()

    # 1. Inteligencia Artificial & ML
    if any(match_word(k, text) for k in ['ai', 'llm', 'gpt', 'neural', 'machine-learning', 'machine learning', 'deep learning', 'model', 'embeddings', 'pytorch', 'tensorflow', 'rag', 'langchain', 'agent']):
        return "Inteligencia Artificial & ML"

    # 2. Bases de Datos & Almacenamiento
    if any(match_word(k, text) for k in ['database', 'db', 'sql', 'postgres', 'postgresql', 'redis', 'mongo', 'mongodb', 'vector', 'orm', 'storage', 'query', 'prisma', 'supabase', 'mysql', 'sqlite']):
        return "Bases de Datos & Almacenamiento"

    # 3. Frontend & Frameworks UI (Especial atención a UI/JS)
    if any(match_word(k, text) for k in ['ui', 'frontend', 'react', 'vue', 'next', 'nextjs', 'tailwind', 'css', 'dom', 'web-ui', 'component', 'components', 'interface', 'angular', 'svelte', 'html']):
        return "Frontend & Frameworks UI"

    # 4. APIs, Backend & Microservicios
    if any(match_word(k, text) for k in ['api', 'apis', 'backend', 'fastapi', 'express', 'rest', 'graphql', 'grpc', 'server', 'microservice', 'microservices', 'http', 'framework', 'django', 'flask', 'nest']):
        return "APIs, Backend & Microservicios"

    # 5. DevOps, CI/CD & Cloud
    if any(match_word(k, text) for k in ['devops', 'docker', 'kubernetes', 'k8s', 'ci/cd', 'cicd', 'action', 'actions', 'deploy', 'deployment', 'terraform', 'cloud', 'container', 'containers', 'aws']):
        return "DevOps, CI/CD & Cloud"

    # 6. Seguridad & Autenticación
    if any(match_word(k, text) for k in ['security', 'auth', 'authentication', 'oauth', 'jwt', 'crypto', 'encryption', 'vulnerability', 'scan', 'password', 'cipher']):
        return "Seguridad & Autenticación"

    # 7. Monitoreo & Observabilidad
    if any(match_word(k, text) for k in ['monitor', 'monitoring', 'metric', 'metrics', 'observability', 'log', 'logging', 'logs', 'trace', 'tracing', 'grafana', 'prometheus', 'telemetry']):
        return "Monitoreo & Observabilidad"

    # 8. Analítica & Big Data
    if any(match_word(k, text) for k in ['data', 'analytics', 'bigdata', 'spark', 'etl', 'pandas', 'pipeline', 'pipelines', 'warehouse', 'analysis', 'chart', 'dashboard']):
        return "Analítica & Big Data"

    # 9. Desarrollo Mobile
    if any(match_word(k, text) for k in ['mobile', 'flutter', 'react-native', 'ios', 'android', 'swift', 'kotlin']):
        return "Desarrollo Mobile"

    # Fallback por defecto
    return "Herramientas & Utilidades"

# Ejecución
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    print("🚀 Sincronizando las 10 categorías oficiales en Supabase...")
    
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

    print("🔍 Recategorizando repositorios...")
    cur.execute("SELECT id, full_name, description, languages FROM repositories;")
    repos = cur.fetchall()

    reassigned = 0
    for repo_id, full_name, description, languages in repos:
        cat_name = determinar_categoria(full_name, description or "", languages or "")
        cat_id = category_map[cat_name]

        cur.execute("UPDATE repositories SET category_id = %s WHERE id = %s;", (cat_id, repo_id))
        reassigned += 1

    conn.commit()
    print(f"✅ ¡Completado! Se recategorizaron {reassigned} repositorios.")

    # Conteo oficial
    cur.execute("""
        SELECT c.name, COUNT(r.id) as total
        FROM categories c
        INNER JOIN repositories r ON r.category_id = c.id
        GROUP BY c.name
        ORDER BY total DESC;
    """)
    stats = cur.fetchall()
    print("\n📊 Distribución resultante por categoría:")
    for cat, count in stats:
        print(f" - {cat}: {count} repositorios")

except Exception as e:
    conn.rollback()
    print(f"❌ Error durante el rebalanceo: {str(e)}")

finally:
    cur.close()
    conn.close()