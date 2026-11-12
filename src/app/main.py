import os
import sys
import json
import subprocess
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ROOT_DIR = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="OpenBridge API 🌉",
    description="API B2B para el catálogo inteligente de herramientas Open-Source",
    version="1.0.0"
)

# 🔓 Configuración de CORS para el Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

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

@app.post("/api/chat", tags=["Chat RAG"])
def chat_rag(request: ChatRequest):
    consulta = request.message.strip()
    if not consulta:
        raise HTTPException(status_code=400, detail="El campo 'message' no puede estar vacío.")

    script_rag = ROOT_DIR / "src/rag/integrar_openbridge.py"
    salida_json = ROOT_DIR / "reportes/rag_openbridge_respuesta.json"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proceso = subprocess.run(
        [sys.executable, str(script_rag), "--consulta", consulta],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300
    )

    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout).strip()
        raise HTTPException(status_code=500, detail=f"Error en pipeline RAG: {detalle}")

    # Leer el JSON estructurado generado por rag_openbridge.py
    if salida_json.is_file():
        datos = json.loads(salida_json.read_text(encoding="utf-8"))
        return {
            "response": datos.get("respuesta_generada", ""),
            "fuentes": datos.get("fuentes", []),
            "modo": datos.get("modo", ""),
            "status": "success"
        }

    return {"response": proceso.stdout.strip(), "status": "success"}
