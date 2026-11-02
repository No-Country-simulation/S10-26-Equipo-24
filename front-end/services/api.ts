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
}

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

export async function getRepositories(
  limit = 20,
  categoryId?: string
): Promise<{
  total: number;
  data: Repository[];
}> {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  if (categoryId) {
    params.set("category_id", categoryId);
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