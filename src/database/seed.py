import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def seed_database():
    csv_path = "data/catalogo_enriquecido_100.csv"
    if not os.path.exists(csv_path):
        print(f"❌ No se encontró el archivo: {csv_path}")
        return

    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada en el archivo .env")
        return

    print("🔌 Conectando a Supabase PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    df = pd.read_csv(csv_path)
    print(f"📦 Cargando {len(df)} repositorios a la base de datos...")

    # 1. Insertar Categorías Únicas
    categorias = df['categoria_validada'].dropna().unique()
    cat_map = {}
    
    for cat in categorias:
        cur.execute(
            "INSERT INTO categories (name, description) VALUES (%s, %s) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id;",
            (cat, f"Categoría de herramientas para {cat}")
        )
        cat_id = cur.fetchone()[0]
        cat_map[cat] = cat_id

    conn.commit()
    print("✅ Categorías registradas e indexadas.")

    # 2. Insertar Repositorios
    inserted_count = 0
    for idx, row in df.iterrows():
        cat_id = cat_map.get(row.get('categoria_validada'))
        
        insert_query = """
        INSERT INTO repositories (
            github_id, full_name, category_id, original_category, resource_type,
            description, problem_solved, use_cases, languages, stars, forks, open_issues,
            license, html_url, archived, disabled, fecha_descarga, commits_90d,
            fecha_ultimo_commit, issues_abiertos, issues_cerrados, prs_abiertos, prs_cerrados,
            contribuidores, tiene_release, tiene_tags, fecha_ultimo_release, consideraciones_integracion
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (github_id) DO UPDATE SET
            stars = EXCLUDED.stars,
            forks = EXCLUDED.forks,
            updated_at = CURRENT_TIMESTAMP;
        """

        github_id = int(row.get('repo_id')) if pd.notna(row.get('repo_id')) else idx + 1000
        
        cur.execute(insert_query, (
            github_id,
            str(row.get('nombre_completo')),
            cat_id,
            str(row.get('categoria_original', '')),
            str(row.get('tipo_recurso_validado', '')),
            str(row.get('descripcion', '')),
            str(row.get('problema_que_resuelve', '')),
            str(row.get('casos_de_uso', '')),
            str(row.get('lenguaje', '')),
            int(row.get('estrellas', 0)) if pd.notna(row.get('estrellas')) else 0,
            int(row.get('forks', 0)) if pd.notna(row.get('forks')) else 0,
            int(row.get('open_issues', 0)) if pd.notna(row.get('open_issues')) else 0,
            str(row.get('licencia', 'N/A')),
            str(row.get('url_github', '')),
            bool(row.get('archived', False)),
            bool(row.get('disabled', False)),
            row.get('fecha_descarga') if pd.notna(row.get('fecha_descarga')) else None,
            int(row.get('commits_90d', 0)) if pd.notna(row.get('commits_90d')) else 0,
            row.get('fecha_ultimo_commit') if pd.notna(row.get('fecha_ultimo_commit')) else None,
            int(row.get('issues_abiertos', 0)) if pd.notna(row.get('issues_abiertos')) else 0,
            int(row.get('issues_cerrados', 0)) if pd.notna(row.get('issues_cerrados')) else 0,
            int(row.get('prs_abiertos', 0)) if pd.notna(row.get('prs_abiertos')) else 0,
            int(row.get('prs_cerrados', 0)) if pd.notna(row.get('prs_cerrados')) else 0,
            int(row.get('contribuidores', 0)) if pd.notna(row.get('contribuidores')) else 0,
            bool(row.get('tiene_release', False)),
            bool(row.get('tiene_tags', False)),
            row.get('fecha_ultimo_release') if pd.notna(row.get('fecha_ultimo_release')) else None,
            str(row.get('consideraciones_integracion', ''))
        ))
        inserted_count += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"🎉 Seeding completado exitosamente. {inserted_count} repositorios insertados en Supabase.")

if __name__ == "__main__":
    seed_database()