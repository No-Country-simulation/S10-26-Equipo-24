
import { Suspense } from "react";
import { getCategories, getRepositories } from "@/services/api";
import RepositoryCard from "@/components/RepositoryCard";

export const instant = false;

async function DashboardContent() {
  // Consultamos ambas fuentes en paralelo.
  const [categoriesData, reposData] = await Promise.all([
    getCategories(),
    getRepositories(100),
  ]);

  return (
    <>
      {/* Categorías */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-gray-700">
          Categorías ({categoriesData.total})
        </h2>

        <div className="flex flex-wrap gap-3">
          {categoriesData.data.map((cat) => (
            <div
              key={cat.id}
              className="bg-white p-4 rounded-lg shadow border border-gray-200"
            >
              <h3 className="font-bold text-blue-600">
                {cat.name}
              </h3>
              <p className="text-sm text-gray-600">
                {cat.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Repositorios */}
      <section>
        <h2 className="text-xl font-semibold mb-4 text-gray-700">
          Repositorios destacados
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reposData.data.map((repo) => (
            <RepositoryCard key={repo.id} repo={repo} />
          ))}
        </div>
      </section>
    </>
  );
}

export default function DashboardPage() {
  return (
    <main className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Dashboard
      </h1>

      <Suspense
        fallback={
          <div className="text-gray-500 p-6">
            Cargando tecnologías y repositorios...
          </div>
        }
      >
        <DashboardContent />
      </Suspense>
    </main>
  );
}
