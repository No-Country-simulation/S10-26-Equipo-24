import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import time


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(
    title="OpenBridge API 🌉",
    description="API B2B para el catálogo inteligente de herramientas Open-Source",
    version="1.0.0"
)

# 🔓 Configuración de CORS para que el Frontend de Lau pueda consumir la API sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
) 

def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL no configurada en el archivo .env")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con Supabase PostgreSQL: {str(e)}")

@app.get("/", tags=["Health Check"])
def health_check():
    return {"status": "online", "message": "API de OpenBridge conectada exitosamente a Supabase PostgreSQL"}

@app.get("/api/categories", tags=["Categorías"])
def list_categories():
    start = time.perf_counter()

    conn = get_db_connection()
    connected = time.perf_counter()

    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description FROM categories ORDER BY name ASC;"
    )
    categories = cur.fetchall()
    queried = time.perf_counter()

    cur.close()
    conn.close()

    finished = time.perf_counter()

    print(f"Conexión: {connected - start:.3f}s")
    print(f"Consulta SQL: {queried - connected:.3f}s")
    print(f"Cierre: {finished - queried:.3f}s")
    print(f"Total: {finished - start:.3f}s")

    return {"total": len(categories), "data": categories}


@app.get("/api/repositories", tags=["Repositorios"])
def list_repositories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = None,
    category_id: str = None,
    license: str = None,
    min_stars: int = None,
    min_health_score: int = None,
    max_health_score: int = None
):
    start = time.perf_counter()

    conn = get_db_connection()
    connected = time.perf_counter()

    cur = conn.cursor()

    conditions = []
    params = []

    if search:
        conditions.append("r.full_name ILIKE %s")
        params.append(f"%{search}%")

    if category_id:
        conditions.append("r.category_id = %s")
        params.append(category_id)

    if license:
        conditions.append("r.license = %s")
        params.append(license)

    if min_stars is not None:
        conditions.append("r.stars >= %s")
        params.append(min_stars)

    if min_health_score is not None:
        conditions.append("r.health_score >= %s")
        params.append(min_health_score)

    if max_health_score is not None:
        conditions.append("r.health_score <= %s")
        params.append(max_health_score)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Contar todos los resultados filtrados
    count_query = f"""
        SELECT COUNT(*) AS total
        FROM repositories r
        {where_clause};
    """

    cur.execute(count_query, tuple(params))
    total = cur.fetchone()["total"]

    # Obtener únicamente los resultados de la página actual
    query = f"""
        SELECT
            r.id,
            r.full_name,
            c.name AS category,
            r.stars,
            r.forks,
            r.languages,
            r.commits_90d,
            r.contribuidores,
            r.license,
            r.html_url,
            r.health_score
        FROM repositories r
        LEFT JOIN categories c ON r.category_id = c.id
        {where_clause}
        ORDER BY r.stars DESC, r.full_name ASC
        LIMIT %s OFFSET %s;
    """

    cur.execute(query, tuple(params + [limit, offset]))
    repos = cur.fetchall()

    queried = time.perf_counter()

    cur.close()
    conn.close()

    finished = time.perf_counter()

    print(f"Conexión: {connected - start:.3f}s")
    print(f"Consulta SQL: {queried - connected:.3f}s")
    print(f"Cierre: {finished - queried:.3f}s")
    print(f"Total: {finished - start:.3f}s")

    return {
        "total": total,
        "data": repos
    }



@app.get("/api/repositories/{repo_id}", tags=["Repositorios"])
def get_repository_detail(repo_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT r.*, c.name as category_name 
        FROM repositories r
        LEFT JOIN categories c ON r.category_id = c.id
        WHERE r.id = %s OR r.github_id::text = %s;
    """
    cur.execute(query, (repo_id, repo_id))
    repo = cur.fetchone()
    cur.close()
    conn.close()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repositorio no encontrado")
        
    return {"data": repo}


