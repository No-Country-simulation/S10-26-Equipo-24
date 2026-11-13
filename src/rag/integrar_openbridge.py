
#!/usr/bin/env python3
"""OpenBridge: busqueda semantica -> filtro -> RAG generativo."""

import argparse
import json
import os
import subprocess
import sys
import tempfile

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BUSCADOR = ROOT / "src/database/02_buscar_db.py"
FILTRO = ROOT / "src/rag/filtrar_recuperacion.py"
RAG = ROOT / "src/rag/rag_openbridge.py"


def ejecutar(etapa, comando, tiempo):
    entorno = os.environ.copy()
    entorno["PYTHONIOENCODING"] = "utf-8"

    try:
        proceso = subprocess.run(
            comando,
            cwd=ROOT,
            env=entorno,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=tiempo,
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{etapa}: se supero el tiempo limite"
        ) from exc

    if proceso.returncode != 0:
        detalle = (
            proceso.stderr or proceso.stdout
        ).strip()

        raise RuntimeError(
            f"{etapa} fallo:\n{detalle}"
        )

    return proceso.stdout


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--consulta",
        required=True
    )

    parser.add_argument(
        "--modelo",
        default="qwen2.5:3b"
    )

    parser.add_argument(
        "--k",
        type=int,
        default=8
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=3
    )

    args = parser.parse_args()

    if args.k < 1 or not 1 <= args.limite <= 12:
        parser.error(
            "--k debe ser >= 1 y --limite entre 1 y 12"
        )

    try:
        with tempfile.TemporaryDirectory(
            prefix="openbridge_"
        ) as carpeta:

            entrada = (
                Path(carpeta) / "recuperados.json"
            )

            filtrados = (
                Path(carpeta) / "filtrados.json"
            )

            # ETAPA 1: BUSQUEDA EN SUPABASE

            print(
                "1/3 Buscando en Supabase...",
                flush=True
            )

            salida = ejecutar(
                "Busqueda semantica",
                [
                    sys.executable,
                    str(BUSCADOR),
                    "--probar",
                    args.consulta,
                    "-k",
                    str(args.k),
                    "--json",
                ],
                300
            )

            try:
                resultados = json.loads(salida)

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "El buscador no devolvio JSON valido"
                ) from exc

            if (
                not isinstance(resultados, list)
                or not resultados
            ):
                raise RuntimeError(
                    "La busqueda no devolvio repositorios"
                )

            entrada.write_text(
                json.dumps(
                    resultados,
                    ensure_ascii=False,
                    default=str
                ),
                encoding="utf-8"
            )

            print(
                f"Recuperados: {len(resultados)}",
                flush=True
            )

            # ETAPA 2: FILTRO DE RELEVANCIA

            print(
                "2/3 Filtrando resultados...",
                flush=True
            )

            salida = ejecutar(
                "Filtro de relevancia",
                [
                    sys.executable,
                    str(FILTRO),
                    "--entrada",
                    str(entrada),
                    "--salida",
                    str(filtrados),
                    "--consulta",
                    args.consulta,
                    "--limite",
                    str(args.limite),
                ],
                60
            )

            print(
                salida.strip(),
                flush=True
            )

            # ETAPA 3: RAG GENERATIVO

            print(
                "3/3 Generando recomendacion...",
                flush=True
            )

            salida = ejecutar(
                "RAG generativo",
                [
                    sys.executable,
                    str(RAG),
                    "--consulta",
                    args.consulta,
                    "--recuperacion",
                    str(filtrados),
                    "--modelo",
                    args.modelo,
                    "--max-fuentes",
                    str(args.limite),
                ],
                900
            )

            print(salida)

    except (RuntimeError, OSError) as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
