// src/components/ui/Logo.tsx

import { Network } from "lucide-react";

export default function Logo() {
  return (
    <div className="flex items-center gap-2">
      <Network className="h-5 w-5 text-sky-400" />

      <div className="flex items-center gap-2">
        <span className="font-semibold text-white">
          OpenBridge
        </span>

        <span className="text-xs text-gray-300">
          | Catálogo Inteligente de Developer Tools B2B
        </span>
      </div>
    </div>
  );
}