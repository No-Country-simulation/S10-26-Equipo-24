-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Tabla de Categorías Principales
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Repositorios (Metadatos + Métricas de Salud + Embeddings)
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_id BIGINT UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    original_category VARCHAR(100),
    resource_type VARCHAR(100),
    description TEXT,
    problem_solved TEXT,
    use_cases TEXT,
    languages VARCHAR(255),
    stars INT DEFAULT 0,
    forks INT DEFAULT 0,
    open_issues INT DEFAULT 0,
    health_score FLOAT DEFAULT 0.0,
    license VARCHAR(50),
    html_url VARCHAR(255),
    
    -- Métricas de Salud Avanzadas (Propuestas por Adrián)
    archived BOOLEAN DEFAULT FALSE,
    disabled BOOLEAN DEFAULT FALSE,
    fecha_descarga TIMESTAMP WITH TIME ZONE,
    commits_90d INT DEFAULT 0,
    fecha_ultimo_commit TIMESTAMP WITH TIME ZONE,
    issues_abiertos INT DEFAULT 0,
    issues_cerrados INT DEFAULT 0,
    prs_abiertos INT DEFAULT 0,
    prs_cerrados INT DEFAULT 0,
    mediana_dias_cierre_issues FLOAT,
    mediana_dias_merge_prs FLOAT,
    contribuidores INT DEFAULT 0,
    tiene_release BOOLEAN DEFAULT FALSE,
    tiene_tags BOOLEAN DEFAULT FALSE,
    fecha_ultimo_release TIMESTAMP WITH TIME ZONE,
    
    consideraciones_integracion TEXT,
    embedding VECTOR(1536), -- Vector OpenAI text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Patrones e Ideas de Integración Estructuradas
CREATE TABLE IF NOT EXISTS integration_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    integration_type VARCHAR(100), -- REST_API, DOCKER, SDK, WEBHOOK
    triggers_webhooks TEXT,
    code_snippet TEXT,
    stack_compatibility TEXT[],
    difficulty_level VARCHAR(50) DEFAULT 'Medium',
    considerations TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices de rendimiento
CREATE INDEX IF NOT EXISTS idx_repositories_category ON repositories(category_id);
CREATE INDEX IF NOT EXISTS idx_repositories_health_score ON repositories(health_score DESC);
CREATE INDEX IF NOT EXISTS idx_repositories_embedding ON repositories USING hnsw (embedding vector_cosine_ops);