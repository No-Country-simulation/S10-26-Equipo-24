import { Suspense } from "react";
import { getCategories, getRepositories } from "@/services/api";
import DashboardClient from "@/components/DashboardClient";

export const instant = false;

async function DashboardContent() {
  // Consultamos categorías y repositorios en paralelo.
  const [categoriesData, reposData] = await Promise.all([
    getCategories(),
    getRepositories(20),
  ]);

  return (
    <DashboardClient
      categories={categoriesData.data}
      initialRepositories={reposData.data}
      initialTotal={reposData.total}
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
