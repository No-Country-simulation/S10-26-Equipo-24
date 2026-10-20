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

-- Tabla de Repositorios (Metadatos + Health Score + Embeddings)
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_id BIGINT UNIQUE NOT NULL,
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
