
import { useId, useState } from "react";
import type { Repository } from "@/services/api";
import RepositoryDetails from "@/components/RepositoryDetails";

interface RepositoryCardProps {
  repo: Repository;
}

export default function RepositoryCard({ repo }: RepositoryCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  // Obtener el porcentaje desde la API
  const score = Math.min(
    100,
    Math.max(0, repo.health_score ?? 0)
  );

  const gradientId = useId();

  // Configuración del indicador semicircular
  const radius = 40;
  const circumference = Math.PI * radius;
  const strokeDashoffset =
    circumference - (score / 100) * circumference;

  // Formatear cantidades grandes
  const formatNumber = (value: number) =>
    new Intl.NumberFormat("es-CO", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);

  return (
    <article className="relative w-full min-w-0 max-w-90 rounded-2xl border border-gray-200 bg-white p-4 font-sans text-gray-800 shadow-sm transition-shadow hover:shadow-md">

      {/* Header */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-emerald-100 bg-emerald-50">
            <svg
              className="h-5 w-5 fill-current text-emerald-500"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M11.5 2L2 13.5h8L8.5 22 22 8.5h-8.5L13.5 2z" />
            </svg>
          </div>

          <h3 className="truncate text-base font-bold tracking-tight text-gray-900 sm:text-lg">
            {repo.full_name}
          </h3>
        </div>

        <a
          href={repo.html_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Ver ${repo.full_name} en GitHub`}
          className="shrink-0 rounded-md p-1 text-gray-400 transition-colors hover:text-gray-600"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M14 3h7v7m-1-6L10 14M19 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6"
            />
          </svg>
        </a>
      </div>

      {/* Categoría */}
      <div className="mb-4">
        <span className="inline-block max-w-full truncate rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
          {repo.category ?? "Sin categoría"}
        </span>
      </div>

      <hr className="mb-3 border-gray-100" />

      {/* Métricas principales */}
      <h4 className="mb-3 text-xs font-bold text-gray-900">
        MÉTRICAS CLAVE
      </h4>

      <div className="mb-5 grid grid-cols-2 items-start gap-x-3">

        {/* Stars */}
        <div className="min-w-0 flex-1">
          <span className="mb-1 block text-xs font-bold text-gray-900">
            Stars
          </span>

          <div className="flex items-center gap-1.5">
            <svg
              className="h-5 w-5 shrink-0 fill-amber-400 text-amber-400"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>

            <span className="text-xl font-extrabold text-gray-900 sm:text-2xl">
              {formatNumber(repo.stars)}
            </span>
          </div>
        </div>

        {/* Health Score */}
        <div
          className="relative flex w-full max-w-35 min-w-0 flex-col items-center"
          role="img"
          aria-label={`Salud del repositorio: ${score}%`}
        >
          <svg
            className="block h-auto w-full"
            viewBox="0 0 100 60"
            fill="none"
            aria-hidden="true"
          >
            {/* Fondo del indicador */}
            <path
              d="M 10 50 A 40 40 0 0 1 90 50"
              stroke="#E5E7EB"
              strokeWidth="9"
              strokeLinecap="round"
            />

            {/* Progreso */}
            <path
              d="M 10 50 A 40 40 0 0 1 90 50"
              stroke={`url(#${gradientId})`}
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              className="transition-all duration-500 ease-out"
            />

            {/* Gradiente */}
            <defs>
              <linearGradient
                id={gradientId}
                x1="0%"
                y1="0%"
                x2="100%"
                y2="0%"
              >
                <stop offset="0%" stopColor="#EA580C" />
                <stop offset="60%" stopColor="#10B981" />
                <stop offset="100%" stopColor="#10B981" />
              </linearGradient>
            </defs>
          </svg>

          {/* Porcentaje */}
          <span className="absolute inset-x-0 bottom-0 text-center text-xs font-bold text-emerald-600">
            {score}%
          </span>
        </div>
      </div>

      {/* Metadatos: se conserva la distribución original */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-3 text-xs">

        {/* Forks */}
        <div className="min-w-0">
          <span className="mb-1 block font-bold text-gray-900">
            Forks
          </span>
          <span className="wrap-break-word text-gray-600">
            {formatNumber(repo.forks)}
          </span>
        </div>

        {/* Contribuidores */}
        <div className="min-w-0">
          <span className="mb-1 block font-bold text-gray-900">
            Contribuidores
          </span>
          <span className="wrap-break-word text-gray-600">
            {formatNumber(repo.contribuidores)}
          </span>
        </div>

        {/* Commits */}
        <div className="min-w-0">
          <span className="mb-1 block font-bold text-gray-900">
            Commits (90 días)
          </span>
          <span className="wrap-break-word text-gray-600">
            {formatNumber(repo.commits_90d)}
          </span>
        </div>

        {/* Licencia */}
        <div className="min-w-0">
          <span className="mb-1 block font-bold text-gray-900">
            Licencia
          </span>
          <span className="wrap-break-word text-gray-600">
            {repo.license ?? "No especificada"}
          </span>
        </div>

      {/* Lenguajes y botón */}
      <div className="col-span-2 flex items-end justify-between gap-3">

        {/* Lenguajes */}
        <div className="min-w-0 flex-1">
          <p className="mb-1 font-bold text-gray-900">
            Lenguajes
          </p>
          <p className="wrap-break-word text-gray-600">
            {repo.languages || "No disponible"}
          </p>
        </div>

        {/* Botón */}
        <button
          type="button"
          onClick={() => setShowDetails(true)}
          className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-slate-700"
          aria-label={`Ver ficha técnica de ${repo.full_name}`}
        >
          Ver ficha técnica
        </button>

      </div>
    </div>

      {/* Modal de información adicional */}
      {showDetails && (
        <RepositoryDetails
          repoId={repo.id}
          onClose={() => setShowDetails(false)}
        />
      )}

    </article>
  );
}
