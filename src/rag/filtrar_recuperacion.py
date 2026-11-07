
#!/usr/bin/env python3
"""Filtrado preliminar de resultados semanticos para OpenBridge."""

import argparse
import json
import re
import unicodedata
from pathlib import Path


def normalizar(valor):
    texto = unicodedata.normalize(
        "NFKD", str(valor).lower()
    )
    return "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )


def capacidades(consulta):
    texto = normalizar(consulta)

    patrones = {
        "pagos": r"\b(pagos?|cobros?|payments?|checkout|tarjetas?|transacciones?)\b",
        "facturacion": r"\b(factur\w*|billing|invoic\w*|suscrip\w*|subscription\w*)\b",
        "autenticacion": r"\b(autentic\w*|usuarios?|login|oauth|identidad|identity|sso)\b",
        "comercio": r"\b(tiendas?|ecommerce|e-commerce|comercio|storefront|shopping)\b",
    }

    return [
        nombre
        for nombre, patron in patrones.items()
        if re.search(patron, texto)
    ]


def puntuar(registro, capacidad):
    temas = " ".join(
        normalizar(t)
        for t in (registro.get("topics") or [])
    )

    categoria = normalizar(
        registro.get("original_category") or ""
    )

    if capacidad == "pagos":
        especificos = (
            "payment-gateway",
            "payment-processing",
            "orchestration",
            "payment-integration",
        )
        if any(x in temas for x in especificos):
            return 3
        return 1 if (
            "payment" in temas or "pago" in categoria
        ) else 0

    if capacidad == "facturacion":
        if any(
            x in temas
            for x in ("invoic", "billing")
        ):
            return 3
        return 1 if any(
            x in temas
            for x in ("accounting", "bills", "subscriptions")
        ) else 0

    if capacidad == "autenticacion":
        if any(
            x in temas
            for x in ("auth", "oauth", "oidc", "identity", "sso")
        ):
            return 3
        return 1 if "autentic" in categoria else 0

    if capacidad == "comercio":
        if any(
            x in temas
            for x in (
                "ecommerce",
                "e-commerce",
                "storefront",
                "headless-commerce",
                "shopping",
            )
        ):
            return 3
        return 1 if "comercio" in categoria else 0

    return 0


def seleccionar(registros, consulta, limite):
    necesidades = capacidades(consulta)

    pide_cripto = bool(
        re.search(
            r"\b(bitcoin|cripto\w*|crypto\w*|blockchain|lightning)\b",
            normalizar(consulta),
        )
    )

    candidatos = []

    for registro in registros:
        temas = " ".join(
            normalizar(t)
            for t in (registro.get("topics") or [])
        )

        if not pide_cripto and any(
            t in temas
            for t in (
                "bitcoin",
                "cryptocurrency",
                "lightning-network",
            )
        ):
            continue

        puntos = {
            c: puntuar(registro, c)
            for c in necesidades
        }

        if necesidades and not any(puntos.values()):
            continue

        candidatos.append((registro, puntos))

    def similitud(fila):
        try:
            return float(
                fila[0].get("similarity") or 0
            )
        except (TypeError, ValueError):
            return 0.0

    seleccion = []
    vistos = set()

    # Cubrir las capacidades solicitadas.
    for necesidad in necesidades:
        ordenados = sorted(
            candidatos,
            key=lambda x: (
                x[1].get(necesidad, 0),
                similitud(x),
            ),
            reverse=True,
        )

        for registro, puntos in ordenados:
            clave = str(
                registro.get("github_id")
                or registro.get("full_name")
            )

            if (
                puntos.get(necesidad, 0)
                and clave not in vistos
            ):
                seleccion.append(registro)
                vistos.add(clave)
                break

        if len(seleccion) == limite:
            break

    # Completar con otros candidatos relevantes.
    restantes = sorted(
        candidatos,
        key=lambda x: (
            sum(v > 0 for v in x[1].values()),
            similitud(x),
        ),
        reverse=True,
    )

    for registro, puntos in restantes:
        clave = str(
            registro.get("github_id")
            or registro.get("full_name")
        )

        if clave not in vistos:
            seleccion.append(registro)
            vistos.add(clave)

        if len(seleccion) >= limite:
            break

    return seleccion[:limite], necesidades


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--entrada", type=Path, required=True
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path(
            "tests/rag/recuperacion_filtrada.json"
        ),
    )
    parser.add_argument(
        "--consulta", required=True
    )
    parser.add_argument(
        "--limite", type=int, default=3
    )

    args = parser.parse_args()

    if args.limite < 1:
        parser.error(
            "--limite debe ser mayor que cero"
        )

    datos = json.loads(
        args.entrada.read_text(encoding="utf-8-sig")
    )

    registros = (
        datos
        if isinstance(datos, list)
        else datos.get("resultados", [])
    )

    if not isinstance(registros, list):
        parser.error(
            "La entrada debe contener una lista"
        )

    elegidos, necesidades = seleccionar(
        registros,
        args.consulta,
        args.limite,
    )

    if not elegidos:
        parser.error(
            "No hay repositorios coincidentes"
        )

    args.salida.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.salida.write_text(
        json.dumps(
            elegidos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "Capacidades:",
        ", ".join(necesidades) or "sin detectar",
    )
    print(
        "Seleccionados:",
        len(elegidos),
        "de",
        len(registros),
    )

    for repo in elegidos:
        print("-", repo.get("full_name"))

    print("Archivo:", args.salida)


if __name__ == "__main__":
    main()
