import os
import psycopg2
from dotenv import load_dotenv
load_dotenv(override=True)

from urllib.parse import urlparse
u = urlparse(os.getenv("DATABASE_URL"))
print("user:", u.username, "| host:", u.hostname, "| port:", u.port)


print("🔌 Conectando a Supabase PostgreSQL...")

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
print("🔌 Conectado a Supabase.")

cur.execute("SELECT version();")
print(cur.fetchone())

input("Presiona Enter para continuar...")
cur.close()
conn.close()

print("🔌 Conexión cerrada.")