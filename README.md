# OpenBridge 🌉

> **Catálogo B2B Inteligente de Herramientas Open-Source**  
> *Simulación Laboral No Country — Equipo 24 (S10-26)*

OpenBridge es una plataforma B2B diseñada para centralizar, analizar y recomendar herramientas y repositorios open-source mediante métricas de salud automatizadas e intenciones de integración directa.

---

## 🛠️ Stack Técnico

- **Lenguaje:** Python 3.12
- **Base de Datos:** PostgreSQL en Supabase con extensión `pgvector`
- **Librerías de Datos & API:** `pandas`, `requests`, `psycopg2-binary`, `python-dotenv`
- **Backend / API:** FastAPI *(en desarrollo)*
- **Interfaz Frontend:** Streamlit *(en desarrollo)*
- **Control de Versiones:** Git & GitHub Actions (CI/CD)

---

## 🏗️ Arquitectura del Proyecto

```text
S10-26-EQUIPO-24/
│
├── .github/workflows/       # Automatización e integración continua
├── data/
│   ├── catalogo_base.csv           # Dataset inicial (100 repositorios)
│   └── catalogo_enriquecido_100.csv # Dataset consolidado con métricas avanzadas
│
├── src/
│   ├── database/
│   │   ├── schema.sql              # Esquema SQL relacional y vectorial
│   │   └── seed.py                 # Script de carga masiva a Supabase
│   │
│   └── ingesta/
│       ├── enriquecer_catalogo.py  # Script de consumo API REST GitHub
│       └── validar_catalogo.py     # Reglas de validación de esquemas
│
├── .env.example                    # Plantilla de variables de entorno
├── pipeline.py                     # Ejecución completa del pipeline
├── README.md                       # Documentación principal
└── requirements.txt                # Dependencias del proyecto

📊 Métricas Avanzadas de Salud (Health Score)
El catálogo implementa un modelo de salud repositorio por repositorio categorizado en 4 dimensiones clave:

Actividad: Frecuencia de commits en los últimos 90 días (commits_90d) y fecha del último commit (fecha_ultimo_commit).

Mantenimiento: Conteo de issues/PRs abiertos y cerrados, evaluando el tiempo promedio de respuesta.

Adopción: Cantidad de estrellas (stars), forks y contribuidores únicos (contribuidores), filtrando cuentas automatizadas (bots).

Gobernanza: Verificación de tipos de licencia SPDX, presencia de lanzamientos (tiene_release) y etiquetas de versión (tiene_tags).

🗄️ Modelo de Datos (PostgreSQL / Supabase)
El esquema relacional incluye soporte para búsquedas semánticas con vectores de embeddings:

categories: Clasificación taxonómica de las herramientas.

repositories: Información detallada, métricas de salud de la API de GitHub y vector de embeddings (vector(1536)).

integration_patterns: Estrategias de integración (API REST, Docker, SDK, Webhooks).

🚀 Guía de Instalación y Ejecución Local
1. Clonar el repositorio e instalar dependencias

PowerShell
git clone [https://github.com/No-Country-simulation/S10-26-Equipo-24.git](https://github.com/No-Country-simulation/S10-26-Equipo-24.git)
cd S10-26-Equipo-24
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

2. Configurar Variables de Entorno
Crea un archivo .env en la raíz del proyecto basándote en el siguiente formato:

Fragmento de código
GITHUB_TOKEN=tu_github_personal_access_token
DATABASE_URL=postgresql://postgres:tu_password@db.tu_project_ref.supabase.co:5432/postgres
3. Enriquecer el Catálogo y Poblar la Base de Datos
PowerShell
# 1. Enriquecer datos desde la API de GitHub
python src/ingesta/enriquecer_catalogo.py

# 2. Ejecutar la carga masiva (seeding) hacia Supabase
python src/database/seed.py
👥 Equipo de Desarrollo (Equipo 24)
- **Ema Camila Conde** — Data Engineering & Backend Architecture
- **Adrián** — Data Strategy, Health Metrics Design & Software Development
- **Yani** — Sourcing, Curation & Repository Requirements Selection
- **Lau** - falta agregar descripcion.
---
