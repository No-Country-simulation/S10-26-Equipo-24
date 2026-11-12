import { Suspense } from "react";
import {
  getCategories,
  getRepositories,
  getRepositoryFilters,
} from "@/services/api";

import DashboardClient from "@/components/DashboardClient";

export const instant = false;

async function DashboardContent() {
  // Consultamos categorías, repositorios y filtros en paralelo.
  const [categoriesData, reposData, filtersData] = await Promise.all([
    getCategories(),
    getRepositories(20),
    getRepositoryFilters(),
  ]);

  return (
    <DashboardClient
      categories={categoriesData.data}
      initialRepositories={reposData.data}
      initialTotal={reposData.total}
      filterOptions={filtersData}
    />
  );
}

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <Suspense
        fallback={
          <div className="p-8 text-gray-500">
            Cargando tecnologías y repositorios...
          </div>
        }
      >
        <DashboardContent />
      </Suspense>
    </main>
  );
}