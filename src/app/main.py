import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM categories ORDER BY name ASC;")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return {"total": len(categories), "data": categories}

@app.get("/api/repositories", tags=["Repositorios"])
def list_repositories(limit: int = 20, category_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    if category_id:
        query = """
            SELECT r.id, r.full_name, c.name as category, r.stars, r.forks, r.languages, 
                   r.commits_90d, r.contribuidores, r.license, r.html_url
            FROM repositories r
            LEFT JOIN categories c ON r.category_id = c.id
            WHERE r.category_id = %s
            ORDER BY r.stars DESC
            LIMIT %s;
        """
        cur.execute(query, (category_id, limit))
    else:
        query = """
            SELECT r.id, r.full_name, c.name as category, r.stars, r.forks, r.languages, 
                   r.commits_90d, r.contribuidores, r.license, r.html_url
            FROM repositories r
            LEFT JOIN categories c ON r.category_id = c.id
            ORDER BY r.stars DESC
            LIMIT %s;
        """
        cur.execute(query, (limit,))
        
    repos = cur.fetchall()
    cur.close()
    conn.close()
    return {"total": len(repos), "data": repos}

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