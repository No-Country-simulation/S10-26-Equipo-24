
const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Category {
  id: string;
  name: string;
  description: string;
}

export interface Repository {
  id: string;
  full_name: string;
  category: string | null;
  stars: number;
  forks: number;
  languages: string | null;
  commits_90d: number;
  contribuidores: number;
  license: string | null;
  html_url: string;
  health_score: number | null;
}

// Filtros disponibles para consultar repositorios
export interface RepositoryFilters {
  search?: string;
  categoryId?: string;
  license?: string;
  minStars?: string;
  minHealthScore?: number;
  maxHealthScore?: number;
}

export interface RepositoryFilterOptions {
  licenses: string[];
}

// Obtener categorías
export async function getCategories(): Promise<{
  total: number;
  data: Category[];
}> {
  const res = await fetch(`${API_URL}/api/categories`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Error al cargar las categorías");
  }

  return res.json();
}

// Obtener repositorios con filtros y paginación
export async function getRepositories(
  limit = 20,
  filters: RepositoryFilters = {},
  offset = 0
): Promise<{
  total: number;
  data: Repository[];
}> {
  const params = new URLSearchParams();

  // Paginación
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  // Búsqueda
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }

  // Categoría
  if (filters.categoryId) {
    params.set("category_id", filters.categoryId);
  }

  // Licencia
  if (filters.license) {
    params.set("license", filters.license);
  }

  // Estrellas mínimas
  if (filters.minStars) {
    params.set("min_stars", filters.minStars);
  }

  // Health Score mínimo
  if (filters.minHealthScore !== undefined) {
    params.set(
      "min_health_score",
      String(filters.minHealthScore)
    );
  }

  // Health Score máximo
  if (filters.maxHealthScore !== undefined) {
    params.set(
      "max_health_score",
      String(filters.maxHealthScore)
    );
  }

  const res = await fetch(
    `${API_URL}/api/repositories?${params.toString()}`,
    { cache: "no-store" }
  );

  if (!res.ok) {
    throw new Error("Error al cargar los repositorios");
  }

  return res.json();
}

// Obtener opciones de filtros desde el backend
export async function getRepositoryFilters():
Promise<RepositoryFilterOptions> {
  const res = await fetch(
    `${API_URL}/api/repository-filters`,
    { cache: "no-store" }
  );

  if (!res.ok) {
    throw new Error("Error al cargar los filtros");
  }

  return res.json();
}
