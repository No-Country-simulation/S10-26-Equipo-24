"""
OpenBridge · configuración central.

Todo lo que podría cambiar (modelo, dimensión, credenciales) está acá, en un solo lugar.

Variables de entorno necesarias (archivo .env, que NO debe subirse al repo):
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY=...        # la service_role key: solo para scripts de backend, nunca en el frontend

Dependencias:
    pip install python-dotenv supabase pandas sentence-transformers
"""
import os
import sys
import psycopg2

from dotenv import load_dotenv

load_dotenv(override=True)  # busca el .env desde esta carpeta hacia arriba

# Forzar UTF-8 global en la sesión si no está activo
if sys.getdefaultencoding() != 'utf-8':
    # Nota: sys.setdefaultencoding es interno en Python pero podemos forzar el entorno con variables 
    pass

# ------------------------------------------------------------------------------------------
# Base de datos
# ------------------------------------------------------------------------------------------
TABLA_REPOS = "repositories"

# ------------------------------------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------------------------------------
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384          # DEBE coincidir con vector(384) en 02_esquema_vectores.sql
EMBEDDING_MAX_SEQ = 256      # por defecto el modelo corta en 128 tokens y perdería parte de los topics

# Si True, el texto a embeber incluye la línea "Categoría: ...".
# Dejarlo configurable permite medir después si esa línea ayuda o mete ruido.
INCLUIR_CATEGORIA_EN_TEXTO = True

# Topics de GitHub que no aportan significado al embedding.
TOPICS_RUIDO = {
    "hacktoberfest", "hacktoberfest2021", "hacktoberfest2022", "hacktoberfest2023",
    "hacktoberfest2024", "hacktoberfest2025", "awesome", "good-first-issue",
    "help-wanted", "open-source", "opensource",
}


# ------------------------------------------------------------------------------------------
# Utilidades de Conexión Directa (PostgreSQL / psycopg2)
# ------------------------------------------------------------------------------------------
def get_conexion_db():
    """Conexión directa a Supabase PostgreSQL usando DATABASE_URL (salta RLS y problemas de API REST)."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Falta configurar DATABASE_URL en el archivo .env. "
            "Definila para permitir conexiones directas por psycopg2."
        )
    return psycopg2.connect(
        database_url,
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "15")),
        sslmode=os.getenv("DB_SSLMODE", "require")
    )

def get_supabase():
    """
    Función adaptadora de compatibilidad: 
    Devuelve un objeto envoltorio que imita la sintaxis del cliente de Supabase 
    pero ejecutando consultas SQL directas por debajo mediante psycopg2.
    """
    class SupabasePSQLWrapper:
        class TableWrapper:
            def __init__(self, table_name):
                self.table_name = table_name
                self._update_data = None
                self._eq_col = None
                self._eq_val = None
                self._select_cols = "*"
                self._count_mode = None

            def select(self, columns="*", count=None):
                self._select_cols = columns
                self._count_mode = count
                return self

            def eq(self, column, value):
                self._eq_col = column
                self._eq_val = value
                return self

            def update(self, data: dict):
                self._update_data = data
                return self

            def execute(self):
                conn = get_conexion_db()
                cur = conn.cursor()
                try:
                    # Caso 1: UPDATE con filtro .eq()
                    if self._update_data is not None:
                        sets = []
                        vals = []
                        for k, v in self._update_data.items():
                            sets.append(f"{k} = %s")
                            vals.append(v)
                        # Agregar updated_at por prolijidad si la tabla lo tiene
                        sets_str = ", ".join(sets)
                        
                        query = f"UPDATE {self.table_name} SET {sets_str} WHERE {self._eq_col} = %s RETURNING id;"
                        vals.append(self._eq_val)
                        cur.execute(query, tuple(vals))
                        conn.commit()
                        
                        class Res:
                            data = [{"status": "updated"}]
                        return Res()

                    # Caso 2: SELECT con conteo exacto (ej. count="exact")
                    if self._count_mode == "exact":
                        where_clause = ""
                        vals = []
                        if self._eq_col:
                            where_clause = f"WHERE {self._eq_col} = %s"
                            vals.append(self._eq_val)
                        
                        cur.execute(f"SELECT COUNT(*) FROM {self.table_name} {where_clause};", tuple(vals))
                        total = cur.fetchone()[0]
                        class Res:
                            data = []
                            count = total
                        return Res()

                    # Caso 3: SELECT estándar
                    cur.execute(f"SELECT {self._select_cols} FROM {self.table_name};")
                    columns_desc = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    data_list = [dict(zip(columns_desc, row)) for row in rows]
                    
                    class Res:
                        data = data_list
                        count = len(data_list)
                    return Res()

                finally:
                    cur.close()
                    conn.close()

        def table(self, name):
            return self.TableWrapper(name)

    return SupabasePSQLWrapper()


def leer_todo(sb, tabla: str, columnas: str, paso: int = 1000) -> list[dict]:
    """Lee todas las filas de la tabla directamente usando la conexión de Postgres."""
    conn = get_conexion_db()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT {columnas} FROM {tabla};")
        columns_desc = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns_desc, row)) for row in rows]
    finally:
        cur.close()
        conn.close()


def parsear_topics(valor) -> list[str]:
    """'api, webhook, queue' -> ['api', 'webhook', 'queue']. Vacío o NaN -> []."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return []
    return [t.strip() for t in str(valor).split(",") if t.strip()]
