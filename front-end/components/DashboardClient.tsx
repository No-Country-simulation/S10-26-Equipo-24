
"use client";

import { useEffect, useState } from "react";
import type { Category, Repository } from "@/services/api";
import { getRepositories } from "@/services/api";
import RepositoryCard from "@/components/RepositoryCard";

interface DashboardClientProps {
  categories: Category[];
  initialRepositories: Repository[];
  initialTotal: number;
}

const PAGE_SIZE = 20;

const maintenanceRanges: Record<
  string,
  { min: number; max: number }
> = {
  Bajo: { min: 0, max: 39 },
  Medio: { min: 40, max: 69 },
  Alto: { min: 70, max: 89 },
  Excelente: { min: 90, max: 100 },
};

export default function DashboardClient({
  categories,
  initialRepositories,
  initialTotal,
}: DashboardClientProps) {
  const [repositories, setRepositories] =
    useState<Repository[]>(initialRepositories);

  const [total, setTotal] = useState(initialTotal);

  // Estados de filtros
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [license, setLicense] = useState("");
  const [maintenance, setMaintenance] = useState("");
  const [minStars, setMinStars] = useState("");

  // Estado de paginación
  const [currentPage, setCurrentPage] = useState(1);

  // Estado de carga
  const [loading, setLoading] = useState(false);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  useEffect(() => {
    const controller = new AbortController();

    const timer = setTimeout(async () => {
      setLoading(true);

      try {
        const selectedRange = maintenance
          ? maintenanceRanges[maintenance]
          : undefined;

        const result = await getRepositories(
          PAGE_SIZE,
          {
            search,
            categoryId,
            license,
            minStars,
            minHealthScore: selectedRange?.min,
            maxHealthScore: selectedRange?.max,
          },
          (currentPage - 1) * PAGE_SIZE
        );

        if (!controller.signal.aborted) {
          setRepositories(result.data);
          setTotal(result.total);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error(
            "Error al filtrar repositorios:",
            error
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 350);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    search,
    categoryId,
    license,
    maintenance,
    minStars,
    currentPage,
  ]);

 const updateFilter = (setter: (value: string) => void, value: string) => {
  setter(value);
  setCurrentPage(1);
};

  const clearFilters = () => {
    setSearch("");
    setCategoryId("");
    setLicense("");
    setMaintenance("");
    setMinStars("");
    setCurrentPage(1);
  };

  return (
    <div className="flex min-h-screen bg-gray-50">

      {/* PANEL LATERAL */}
      <aside className="hidden w-64 shrink-0 border-r border-gray-200 bg-white p-5 md:block">

        <h2 className="mb-5 text-lg font-bold text-gray-900">
          Filtros
        </h2>

        {/* CATEGORÍAS */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-bold text-gray-800">
            Categorías
          </h3>

          <div className="max-h-64 space-y-2 overflow-y-auto">

            <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-600">
              <input
                type="radio"
                name="category"
                checked={categoryId === ""}
                onChange={() => updateFilter(setCategoryId, "")}
                className="accent-blue-600"
              />
              Todas las categorías
            </label>

            {categories.map((category) => (
              <label
                key={category.id}
                className="flex cursor-pointer items-start gap-2 text-sm text-gray-600"
              >
                <input
                  type="radio"
                  name="category"
                  checked={categoryId === category.id}
                  onChange={() => updateFilter(setCategoryId, category.id)}
                  className="mt-1 accent-blue-600"
                />

                <span>{category.name}</span>
              </label>
            ))}

          </div>
        </div>

        <hr className="mb-5 border-gray-100" />

        {/* LICENCIAS */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-bold text-gray-800">
            Licencia
          </h3>

          <select
            value={license}
            onChange={(e) => updateFilter(setLicense, e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white p-2 text-sm"
          >
            <option value="">Todas las licencias</option>
            <option value="MIT">MIT</option>
            <option value="Apache-2.0">Apache-2.0</option>
            <option value="GPL-3.0">GPL-3.0</option>
            <option value="AGPL-3.0">AGPL-3.0</option>
          </select>
        </div>

        <hr className="mb-5 border-gray-100" />

        {/* MANTENIMIENTO */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-bold text-gray-800">
            Nivel de mantenimiento
          </h3>

          <select
            value={maintenance}
            onChange={(e) => updateFilter(setMaintenance, e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white p-2 text-sm"
          >
            <option value="">Todos los niveles</option>
            <option value="Bajo">Bajo (0–39)</option>
            <option value="Medio">Medio (40–69)</option>
            <option value="Alto">Alto (70–89)</option>
            <option value="Excelente">Excelente (90–100)</option>
          </select>
        </div>

        <hr className="mb-5 border-gray-100" />

        {/* ESTRELLAS */}
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-bold text-gray-800">
            Estrellas mínimas
          </h3>

          <select
            value={minStars}
            onChange={(e) => updateFilter(setMinStars, e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white p-2 text-sm"
          >
            <option value="">Todas las cantidades</option>
            <option value="100">100 o más</option>
            <option value="1000">1.000 o más</option>
            <option value="5000">5.000 o más</option>
            <option value="10000">10.000 o más</option>
            <option value="50000">50.000 o más</option>
          </select>
        </div>

        {/* LIMPIAR FILTROS */}
        <button
          onClick={clearFilters}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Limpiar filtros
        </button>

      </aside>

      {/* CONTENIDO PRINCIPAL */}
      <section className="min-w-0 flex-1 p-5 md:p-7">

        {/* BUSCADOR */}
        <div className="mb-6">
          <div className="relative">

            <svg
              className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              aria-hidden="true"
            >
              <circle
                cx="11"
                cy="11"
                r="7"
                strokeWidth="2"
              />
              <path
                d="m16 16 4 4"
                strokeWidth="2"
              />
            </svg>

            <input
              type="search"
              value={search}
              onChange={(e) => updateFilter(setSearch, e.target.value)}
              placeholder="Buscar repositorio por nombre..."
              className="w-full rounded-xl border border-gray-300 bg-white py-3 pl-12 pr-4 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />

          </div>
        </div>

        {/* ENCABEZADO DE RESULTADOS */}
        <div className="mb-5 flex items-center justify-between">

          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Repositorios
            </h1>

            <p className="mt-1 text-sm text-gray-500">
              {total} resultados encontrados
            </p>
          </div>

          {loading && (
            <span className="text-sm text-blue-600">
              Actualizando...
            </span>
          )}

        </div>

        {/* TARJETAS */}
        {repositories.length > 0 ? (

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-3">

            {repositories.map((repo) => (
              <RepositoryCard
                key={repo.id}
                repo={repo}
              />
            ))}

          </div>

        ) : (

          !loading && (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center">
              <p className="font-medium text-gray-700">
                No se encontraron repositorios.
              </p>

              <p className="mt-1 text-sm text-gray-500">
                Prueba cambiando los filtros de búsqueda.
              </p>
            </div>
          )

        )}

        {/* PAGINACIÓN */}
        {totalPages > 1 && (
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">

            <button
              onClick={() =>
                setCurrentPage((page) => Math.max(1, page - 1))
              }
              disabled={currentPage === 1 || loading}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Anterior
            </button>

            {Array.from(
              { length: totalPages },
              (_, index) => index + 1
            ).map((page) => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                disabled={loading}
                className={`rounded-lg px-4 py-2 text-sm font-medium ${
                  currentPage === page
                    ? "bg-blue-600 text-white"
                    : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {page}
              </button>
            ))}

            <button
              onClick={() =>
                setCurrentPage((page) =>
                  Math.min(totalPages, page + 1)
                )
              }
              disabled={currentPage === totalPages || loading}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Siguiente
            </button>

          </div>
        )}

        {/* INFORMACIÓN DE PÁGINA */}
        {total > 0 && (
          <p className="mt-3 text-center text-xs text-gray-500">
            Página {currentPage} de {totalPages}
            {" · "}
            Mostrando {repositories.length} de {total} repositorios
          </p>
        )}

      </section>
    </div>
  );
}
