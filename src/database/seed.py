import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar_db():
    if not DATABASE_URL:
        raise ValueError(
            "Falta configurar DATABASE_URL en el archivo .env"
        )

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "15")),
        sslmode=os.getenv("DB_SSLMODE", "require")
    )


def inferir_categoria(row):
    """Asigna una categoría coherente según metadatos si no viene definida."""
    cat_orig = str(
        row.get('categoria_validada', '')
        or row.get('categoria_propuesta', '')
        or ''
    ).strip()

    if cat_orig and cat_orig.lower() not in ['general', 'nan', 'none', '']:
        return cat_orig.title()

    desc = str(row.get('descripcion', '') or '').lower()
    nombre = str(row.get('nombre_completo', '') or '').lower()
    lang = str(row.get('lenguaje', '') or '').lower()

    if any(k in desc or k in nombre for k in [
        'db', 'database', 'sql', 'postgres', 'mongo', 'redis', 'storage'
    ]):
        return "Bases de Datos & Almacenamiento"

    elif any(k in desc or k in nombre for k in [
        'ai', 'ml', 'llm', 'gpt', 'model', 'neural', 'learning', 'rag'
    ]):
        return "Inteligencia Artificial & ML"

    elif any(k in desc or k in nombre for k in [
        'sec', 'auth', 'cyber', 'shield', 'key', 'token', 'vault'
    ]):
        return "Seguridad & Autenticación"

    elif any(k in desc or k in nombre for k in [
        'docker', 'k8s', 'kubernetes', 'deploy', 'ci/cd', 'cloud', 'devops'
    ]):
        return "DevOps & Infraestructura"

    elif any(k in desc or k in nombre for k in [
        'api', 'rest', 'graphql', 'grpc', 'fastapi', 'express'
    ]):
        return "APIs & Integración"

    elif any(k in desc or k in nombre for k in [
        'ui', 'frontend', 'react', 'vue', 'css', 'dashboard', 'streamlit'
    ]):
        return "Frontend & UI Frameworks"

    elif 'python' in lang:
        return "Herramientas Python"

    elif any(l in lang for l in ['javascript', 'typescript']):
        return "Herramientas JS/TS"

    elif 'go' in lang:
        return "Herramientas Go"

    else:
        return "Herramientas & Utilidades General"


def seed_database():
    csv_path = "data/catalogo_enriquecido_100.csv"

    if not os.path.exists(csv_path):
        print(f"❌ No se encontró el archivo: {csv_path}")
        return

    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada en el archivo .env")
        return

    conn = None
    cur = None

    try:
        print("🔌 Conectando a Supabase PostgreSQL mediante Session Pooler...")

        # conn = psycopg2.connect(
        #     DATABASE_URL,
        #     connect_timeout=15,
        #     sslmode="require"
        # )
        conn = conectar_db()
        cur = conn.cursor()

        df = pd.read_csv(csv_path)
        print(f"📦 Procesando {len(df)} repositorios...")

        # Asignar categorías inferidas
        df['categoria_inferida'] = df.apply(inferir_categoria, axis=1)

        # 1. Insertar categorías únicas
        categorias_unicas = df['categoria_inferida'].unique()
        cat_map = {}

        for cat in categorias_unicas:
            cur.execute(
                """
                INSERT INTO categories (name, description)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id;
                """,
                (cat, f"Catálogo y herramientas especializadas en {cat}")
            )

            cat_id = cur.fetchone()[0]
            cat_map[cat] = cat_id

        conn.commit()
        print(f"✅ {len(cat_map)} categorías registradas e indexadas.")

        # 2. Insertar repositorios
        inserted_count = 0

        for idx, row in df.iterrows():
            cat_id = cat_map.get(row.get('categoria_inferida'))

            insert_query = """
            INSERT INTO repositories (
                github_id, full_name, category_id, original_category,
                resource_type, description, problem_solved, use_cases,
                languages, stars, forks, open_issues, license, html_url,
                archived, disabled, fecha_descarga, commits_90d,
                fecha_ultimo_commit, issues_abiertos, issues_cerrados,
                prs_abiertos, prs_cerrados, contribuidores, tiene_release,
                tiene_tags, fecha_ultimo_release, consideraciones_integracion
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (github_id) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                stars = EXCLUDED.stars,
                forks = EXCLUDED.forks,
                updated_at = CURRENT_TIMESTAMP;
            """

            github_id = (
                int(row.get('repo_id'))
                if pd.notna(row.get('repo_id'))
                else idx + 1000
            )

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
                int(row.get('estrellas', 0))
                if pd.notna(row.get('estrellas')) else 0,
                int(row.get('forks', 0))
                if pd.notna(row.get('forks')) else 0,
                int(row.get('open_issues', 0))
                if pd.notna(row.get('open_issues')) else 0,
                str(row.get('licencia', 'N/A')),
                str(row.get('url_github', '')),
                bool(row.get('archived', False)),
                bool(row.get('disabled', False)),
                row.get('fecha_descarga')
                if pd.notna(row.get('fecha_descarga')) else None,
                int(row.get('commits_90d', 0))
                if pd.notna(row.get('commits_90d')) else 0,
                row.get('fecha_ultimo_commit')
                if pd.notna(row.get('fecha_ultimo_commit')) else None,
                int(row.get('issues_abiertos', 0))
                if pd.notna(row.get('issues_abiertos')) else 0,
                int(row.get('issues_cerrados', 0))
                if pd.notna(row.get('issues_cerrados')) else 0,
                int(row.get('prs_abiertos', 0))
                if pd.notna(row.get('prs_abiertos')) else 0,
                int(row.get('prs_cerrados', 0))
                if pd.notna(row.get('prs_cerrados')) else 0,
                int(row.get('contribuidores', 0))
                if pd.notna(row.get('contribuidores')) else 0,
                bool(row.get('tiene_release', False)),
                bool(row.get('tiene_tags', False)),
                row.get('fecha_ultimo_release')
                if pd.notna(row.get('fecha_ultimo_release')) else None,
                str(row.get('consideraciones_integracion', ''))
            ))

            inserted_count += 1

        conn.commit()

        print(
            "🎉 Seeding completado exitosamente. "
            f"{inserted_count} repositorios procesados."
        )

    except Exception as e:
        if conn is not None:
            conn.rollback()

        print(f"❌ Error durante el seeding: {e}")
        raise

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


if __name__ == "__main__":
    seed_database()







# import os
# import pandas as pd
# import psycopg2
# from dotenv import load_dotenv

# load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL")

# def inferir_categoria(row):
#     """Asigna una categoría coherente según metadatos si no viene definida."""
#     cat_orig = str(row.get('categoria_validada', '') or row.get('categoria_propuesta', '') or '').strip()
#     if cat_orig and cat_orig.lower() not in ['general', 'nan', 'none', '']:
#         return cat_orig.title()

#     desc = str(row.get('descripcion', '') or '').lower()
#     nombre = str(row.get('nombre_completo', '') or '').lower()
#     lang = str(row.get('lenguaje', '') or '').lower()

#     if any(k in desc or k in nombre for k in ['db', 'database', 'sql', 'postgres', 'mongo', 'redis', 'storage']):
#         return "Bases de Datos & Almacenamiento"
#     elif any(k in desc or k in nombre for k in ['ai', 'ml', 'llm', 'gpt', 'model', 'neural', 'learning', 'rag']):
#         return "Inteligencia Artificial & ML"
#     elif any(k in desc or k in nombre for k in ['sec', 'auth', 'cyber', 'shield', 'key', 'token', 'vault']):
#         return "Seguridad & Autenticación"
#     elif any(k in desc or k in nombre for k in ['docker', 'k8s', 'kubernetes', 'deploy', 'ci/cd', 'cloud', 'devops']):
#         return "DevOps & Infraestructura"
#     elif any(k in desc or k in nombre for k in ['api', 'rest', 'graphql', 'grpc', 'fastapi', 'express']):
#         return "APIs & Integración"
#     elif any(k in desc or k in nombre for k in ['ui', 'frontend', 'react', 'vue', 'css', 'dashboard', 'streamlit']):
#         return "Frontend & UI Frameworks"
#     elif 'python' in lang:
#         return "Herramientas Python"
#     elif any(l in lang for l in ['javascript', 'typescript']):
#         return "Herramientas JS/TS"
#     elif 'go' in lang:
#         return "Herramientas Go"
#     else:
#         return "Herramientas & Utilidades General"

# def seed_database():
#     csv_path = "data/catalogo_enriquecido_100.csv"
#     if not os.path.exists(csv_path):
#         print(f"❌ No se encontró el archivo: {csv_path}")
#         return

#     if not DATABASE_URL:
#         print("❌ DATABASE_URL no está configurada en el archivo .env")
#         return

#     print("🔌 Conectando a Supabase PostgreSQL...")
#     conn = psycopg2.connect(DATABASE_URL)
#     cur = conn.cursor()

#     df = pd.read_csv(csv_path)
#     print(f"📦 Procesando {len(df)} repositorios...")

#     # Asignar categorías inferidas
#     df['categoria_inferida'] = df.apply(inferir_categoria, axis=1)

#     # 1. Insertar Categorías Únicas
#     categorias_unicas = df['categoria_inferida'].unique()
#     cat_map = {}
    
#     for cat in categorias_unicas:
#         cur.execute(
#             """
#             INSERT INTO categories (name, description) 
#             VALUES (%s, %s) 
#             ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name 
#             RETURNING id;
#             """,
#             (cat, f"Catálogo y herramientas especializadas en {cat}")
#         )
#         cat_id = cur.fetchone()[0]
#         cat_map[cat] = cat_id

#     conn.commit()
#     print(f"✅ {len(cat_map)} categorías registradas e indexadas.")

#     # 2. Insertar Repositorios
#     inserted_count = 0
#     for idx, row in df.iterrows():
#         cat_id = cat_map.get(row.get('categoria_inferida'))
        
#         insert_query = """
#         INSERT INTO repositories (
#             github_id, full_name, category_id, original_category, resource_type,
#             description, problem_solved, use_cases, languages, stars, forks, open_issues,
#             license, html_url, archived, disabled, fecha_descarga, commits_90d,
#             fecha_ultimo_commit, issues_abiertos, issues_cerrados, prs_abiertos, prs_cerrados,
#             contribuidores, tiene_release, tiene_tags, fecha_ultimo_release, consideraciones_integracion
#         ) VALUES (
#             %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
#         ) ON CONFLICT (github_id) DO UPDATE SET
#             category_id = EXCLUDED.category_id,
#             stars = EXCLUDED.stars,
#             forks = EXCLUDED.forks,
#             updated_at = CURRENT_TIMESTAMP;
#         """
    

#         github_id = int(row.get('repo_id')) if pd.notna(row.get('repo_id')) else idx + 1000
        
#         cur.execute(insert_query, (
#             github_id,
#             str(row.get('nombre_completo')),
#             cat_id,
#             str(row.get('categoria_original', '')),
#             str(row.get('tipo_recurso_validado', '')),
#             str(row.get('descripcion', '')),
#             str(row.get('problema_que_resuelve', '')),
#             str(row.get('casos_de_uso', '')),
#             str(row.get('lenguaje', '')),
#             int(row.get('estrellas', 0)) if pd.notna(row.get('estrellas')) else 0,
#             int(row.get('forks', 0)) if pd.notna(row.get('forks')) else 0,
#             int(row.get('open_issues', 0)) if pd.notna(row.get('open_issues')) else 0,
#             str(row.get('licencia', 'N/A')),
#             str(row.get('url_github', '')),
#             bool(row.get('archived', False)),
#             bool(row.get('disabled', False)),
#             row.get('fecha_descarga') if pd.notna(row.get('fecha_descarga')) else None,
#             int(row.get('commits_90d', 0)) if pd.notna(row.get('commits_90d')) else 0,
#             row.get('fecha_ultimo_commit') if pd.notna(row.get('fecha_ultimo_commit')) else None,
#             int(row.get('issues_abiertos', 0)) if pd.notna(row.get('issues_abiertos')) else 0,
#             int(row.get('issues_cerrados', 0)) if pd.notna(row.get('issues_cerrados')) else 0,
#             int(row.get('prs_abiertos', 0)) if pd.notna(row.get('prs_abiertos')) else 0,
#             int(row.get('prs_cerrados', 0)) if pd.notna(row.get('prs_cerrados')) else 0,
#             int(row.get('contribuidores', 0)) if pd.notna(row.get('contribuidores')) else 0,
#             bool(row.get('tiene_release', False)),
#             bool(row.get('tiene_tags', False)),
#             row.get('fecha_ultimo_release') if pd.notna(row.get('fecha_ultimo_release')) else None,
#             str(row.get('consideraciones_integracion', ''))
#         ))
#         inserted_count += 1

#     conn.commit()
#     cur.close()
#     conn.close()
#     print(f"🎉 Seeding completado exitosamente. {inserted_count} repositorios vinculados a sus categorías relacionales.")

# if __name__ == "__main__":
#     seed_database()