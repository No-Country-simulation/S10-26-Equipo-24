
"use client";

import { useEffect, useState } from "react";
import {
  getRepositoryDetail,
  type RepositoryDetail,
} from "@/services/api";

interface RepositoryDetailsProps {
  repoId: string;
  onClose: () => void;
}

export default function RepositoryDetails({
  repoId,
  onClose,
}: RepositoryDetailsProps) {
  const [repository, setRepository] = useState<RepositoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadDetails() {
      try {
        setLoading(true);
        setError("");

        const data = await getRepositoryDetail(
          repoId,
          controller.signal
        );

        if (!controller.signal.aborted) {
          setRepository(data);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError("No fue posible cargar la información del repositorio.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadDetails();

    return () => controller.abort();
  }, [repoId]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  const formatNumber = (value: number | null) => {
    if (value === null || value === undefined) return "No disponible";

    return new Intl.NumberFormat("es-CO", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  };

  const formatDate = (date: string | null) => {
    if (!date) return "No disponible";

    const parsedDate = new Date(date);

    if (Number.isNaN(parsedDate.getTime())) {
      return "No disponible";
    }

    return new Intl.DateTimeFormat("es-CO", {
      dateStyle: "long",
    }).format(parsedDate);
  };

  const score = Math.min(
    100,
    Math.max(0, repository?.health_score ?? 0)
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 backdrop-blur-sm"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="technical-sheet-title"
        className="relative grid max-h-[90vh] w-full max-w-4xl grid-cols-1 overflow-hidden rounded-xl bg-white shadow-2xl md:grid-cols-[210px_minmax(0,1fr)]"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Panel azul izquierdo */}
        <aside className="flex flex-col gap-5 bg-slate-800 p-5 text-white">
          <h2
            id="technical-sheet-title"
            className="border-b border-white/20 pb-3 text-lg font-bold"
          >
            Ficha Técnica
          </h2>

          {loading ? (
            <p className="text-sm text-slate-300">
              Cargando métricas...
            </p>
          ) : repository ? (
            <>
              {/* Health Score */}
              <div>
                <span className="mb-2 block text-xs text-slate-300">
                  Health Score
                </span>

                <div className="relative mx-auto w-32">
                  <svg viewBox="0 0 100 60" className="w-full" fill="none">
                    <path
                      d="M 10 50 A 40 40 0 0 1 90 50"
                      stroke="#475569"
                      strokeWidth="9"
                      strokeLinecap="round"
                    />
                    <path
                      d="M 10 50 A 40 40 0 0 1 90 50"
                      stroke="#34D399"
                      strokeWidth="9"
                      strokeLinecap="round"
                      strokeDasharray={Math.PI * 40}
                      strokeDashoffset={
                        Math.PI * 40 - (score / 100) * Math.PI * 40
                      }
                    />
                  </svg>

                  <span className="absolute inset-x-0 bottom-0 text-center text-lg font-bold text-emerald-300">
                    {score}%
                  </span>
                </div>
              </div>

              {/* Stars */}
              <div>
                <span className="mb-1 block text-xs text-slate-300">
                  Stars
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xl text-amber-400">★</span>
                  <span className="text-xl font-bold">
                    {formatNumber(repository.stars)}
                  </span>
                </div>
              </div>

              {/* Licencia */}
              <div className="border-t border-white/15 pt-3">
                <span className="mb-1 block text-xs text-slate-300">
                  Licencia
                </span>
                <span className="wrap-break-word text-lg font-semibold">
                  {repository.license ?? "No especificada"}
                </span>
              </div>

              {/* Lenguaje */}
              <div className="border-t border-white/15 pt-3">
                <span className="mb-1 block text-xs text-slate-300">
                  Lenguaje
                </span>
                <span className="wrap-break-word text-lg font-semibold">
                  {repository.languages ?? "No especificado"}
                </span>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-300">
              No hay métricas disponibles.
            </p>
          )}
        </aside>

        {/* Panel derecho */}
        <div className="relative min-h-0 overflow-y-auto p-5 sm:p-6">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Cerrar ficha técnica"
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
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>

          <div className="mb-5 pr-8">
            <h3 className="text-lg font-bold text-gray-900">
              Ideas de Integración
            </h3>
            {repository && (
              <p className="mt-1 text-sm text-gray-500">
                {repository.full_name}
              </p>
            )}
          </div>

          {loading ? (
            <div className="flex min-h-48 items-center justify-center">
              <p className="text-sm text-gray-500">
                Cargando información del repositorio...
              </p>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          ) : repository ? (
            <>
              {/* Descripción */}
              <div className="mb-4 rounded-lg border border-gray-200 p-4">
                <h4 className="mb-2 text-sm font-bold text-gray-800">
                  Descripción
                </h4>
                <p className="whitespace-pre-line text-sm leading-relaxed text-gray-600">
                  {repository.description || "No hay una descripción disponible."}
                </p>
              </div>

              {/* Consideraciones de integración */}
              <div className="mb-4 rounded-lg border border-gray-200 p-4">
                <h4 className="mb-2 text-sm font-bold text-gray-800">
                  Consideraciones de Integración
                </h4>
                <p className="whitespace-pre-line text-sm leading-relaxed text-gray-600">
                  {repository.consideraciones_integracion ||
                    "No hay consideraciones de integración registradas."}
                </p>
              </div>

              {/* Último commit */}
              <div className="mb-4 rounded-lg border border-gray-200 p-4">
                <h4 className="mb-1 text-sm font-bold text-gray-800">
                  Último commit
                </h4>
                <p className="text-sm text-gray-600">
                  {formatDate(repository.fecha_ultimo_commit)}
                </p>
              </div>

              {/* Issues y Pull Requests */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {/* Issues abiertos */}
                <div className="rounded-lg border border-gray-200 p-3">
                  <span className="mb-1 block text-xs text-gray-500">
                    Issues abiertos
                  </span>
                  <span className="text-2xl font-bold text-gray-800">
                    {formatNumber(repository.open_issues)}
                  </span>
                </div>

                {/* Issues cerrados */}
                <div className="rounded-lg border border-gray-200 p-3">
                  <span className="mb-1 block text-xs text-gray-500">
                    Issues cerrados
                  </span>
                  <span className="text-2xl font-bold text-gray-800">
                    {formatNumber(repository.issues_cerrados)}
                  </span>
                </div>

                {/* PRs abiertos */}
                <div className="rounded-lg border border-gray-200 p-3">
                  <span className="mb-1 block text-xs text-gray-500">
                    PRs abiertos
                  </span>
                  <span className="text-2xl font-bold text-gray-800">
                    {formatNumber(repository.prs_abiertos)}
                  </span>
                </div>

                {/* PRs cerrados */}
                <div className="rounded-lg border border-gray-200 p-3">
                  <span className="mb-1 block text-xs text-gray-500">
                    PRs cerrados
                  </span>
                  <span className="text-2xl font-bold text-gray-800">
                    {formatNumber(repository.prs_cerrados)}
                  </span>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </section>
    </div>
  );
}
