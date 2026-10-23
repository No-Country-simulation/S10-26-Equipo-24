
#!/usr/bin/env python3
"""
OpenBridge - Validación y comparación de métricas con Supabase.

Fuente:
    data/catalogo_actualizado.csv

Destino:
    public.repositories

Modos:
    Sin argumentos: valida el CSV localmente.
    --check-db: compara CSV con Supabase y genera un reporte.

SEGURIDAD:
    - No realiza INSERT, UPDATE ni DELETE.
    - No modifica categorías, descripciones ni Health Score.
    - --apply está deshabilitado hasta autorización del equipo.

Dependencia:
    pip install "psycopg[binary]>=3.1,<4"
"""

import argparse
import csv
import os

from collections import Counter
from pathlib import Path
from datetime import datetime, timezone


DEFAULT_CSV = Path("data/catalogo_actualizado.csv")
DEFAULT_REPORT = Path("comparacion_supabase.csv")

REQUIRED = {
    "repo_id",
    "stars_actual",
    "forks_actual",
    "actualizado_en",
}

# Columna en Supabase -> columna del CSV
# No incluye categorías, issues, descripciones ni Health Score.
FIELD_MAP = {
    "stars": ("stars_actual", "number"),
    "forks": ("forks_actual", "number"),
    "license": ("licencia_actual", "text"),
    "archived": ("archivado_actual", "bool"),
}

MISSING = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "sin licencia",
    "unknown",
}


def positive_int(raw, label, allow_zero=False):
    value = str(raw if raw is not None else "").strip()

    if not value.isdigit():
        raise ValueError(
            f"{label}: entero no válido ({value!r})"
        )

    number = int(value)

    if number == 0 and not allow_zero:
        raise ValueError(
            f"{label}: se esperaba un ID mayor que cero"
        )

    return number


def parse_bool(raw):
    value = str(
        raw if raw is not None else ""
    ).strip().lower()

    if value in {"1", "true", "t", "yes", "si", "sí"}:
        return True

    if value in {"0", "false", "f", "no"}:
        return False

    return None


def parse_value(raw, kind, label):
    value = str(
        raw if raw is not None else ""
    ).strip()

    if kind == "number":
        if value == "":
            return None
        return positive_int(
            value,
            label,
            allow_zero=True,
        )

    if kind == "bool":
        return parse_bool(value)

    if value.lower() in MISSING:
        return None

    return value


def load_csv(path, expected_count=100):
    if not path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fh:

        reader = csv.DictReader(fh)
        header = set(reader.fieldnames or [])

        missing_columns = REQUIRED - header

        if missing_columns:
            raise ValueError(
                "Faltan columnas: "
                + ", ".join(sorted(missing_columns))
            )

        rows = list(reader)

    if len(rows) != expected_count:
        raise ValueError(
            f"Se esperaban {expected_count} repositorios "
            f"y se encontraron {len(rows)}."
        )

    ids = [
        positive_int(row["repo_id"], "repo_id")
        for row in rows
    ]

    if len(set(ids)) != len(ids):
        raise ValueError(
            "Se detectaron IDs duplicados en el CSV."
        )

    data = []

    for repo_id, row in zip(ids, rows):

        updated = str(
            row.get("actualizado_en") or ""
        ).strip()

        if not updated:
            raise ValueError(
                f"ID {repo_id}: falta actualizado_en."
            )

        try:
            timestamp = datetime.fromisoformat(
                updated.replace("Z", "+00:00")
            )
        except ValueError:
            raise ValueError(
                f"ID {repo_id}: fecha no válida: {updated}"
            )

        if timestamp.tzinfo is None:
            raise ValueError(
                f"ID {repo_id}: fecha sin zona horaria."
            )

        if timestamp > datetime.now(timezone.utc):
            raise ValueError(
                f"ID {repo_id}: fecha futura."
            )

        values = {}

        for target, (source, kind) in FIELD_MAP.items():

            if source not in header:
                continue

            value = parse_value(
                row.get(source),
                kind,
                f"{source} del ID {repo_id}",
            )

            # No convertimos datos ausentes en ceros.
            if value is not None:
                values[target] = value

        data.append((repo_id, values))

    validate_metrics(data, expected_count)

    return data


def validate_metrics(data, expected_count):
    """
    Detecta errores generalizados en las métricas.
    """

    for field in ("stars", "forks"):

        values = [
            row[field]
            for _, row in data
            if field in row
        ]

        if len(values) != expected_count:
            raise ValueError(
                f"{field}: solo hay {len(values)} "
                f"de {expected_count} valores."
            )

        if all(value == 0 for value in values):
            raise ValueError(
                f"{field}: todos los valores son cero. "
                "Posible error de ingesta."
            )

        # Detecta casos como las 102752 estrellas
        # repetidas en los 100 repositorios de Supabase.
        if len(set(values)) == 1:
            raise ValueError(
                f"{field}: todos los repositorios tienen "
                f"el mismo valor ({values[0]}). "
                "Revisar el origen de los datos."
            )

    print("VALIDACIÓN LOCAL COMPLETADA")
    print(f"Repositorios: {len(data)}")
    print(f"IDs únicos: {len(set(i for i, _ in data))}")

    for field in ("stars", "forks"):
        values = [
            row[field]
            for _, row in data
            if field in row
        ]

        print(
            f"{field}: "
            f"{len(set(values))} valores diferentes; "
            f"{values.count(0)} ceros"
        )


def preview(data):
    """
    Muestra un resumen sin modificar información.
    """

    totals = Counter(
        key
        for _, values in data
        for key in values
    )

    print("\nCAMPOS DISPONIBLES")

    for field, count in sorted(totals.items()):
        print(f"  {field}: {count} registros")

    print("\nPRIMEROS 3 REPOSITORIOS")

    for repo_id, values in data[:3]:
        print(f"  ID {repo_id}: {values}")

    print("\nNo se ha modificado Supabase.")


def normalize_db_value(value, kind):
    if value is None:
        return None

    if kind == "number":
        return int(value)

    if kind == "bool":
        if isinstance(value, bool):
            return value
        return parse_bool(value)

    return str(value).strip()


def compare_db(data, db_url, report_path):
    """
    Compara los registros con Supabase.

    La transacción se configura como SOLO LECTURA.
    No se ejecuta ninguna sentencia de modificación.
    """

    import psycopg
    from psycopg import sql

    differences = []
    compared = 0

    with psycopg.connect(
        db_url,
        connect_timeout=15,
    ) as con:

        with con.cursor() as cur:

            # Toda la transacción es de solo lectura.
            cur.execute("SET TRANSACTION READ ONLY")

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                """,
                ("public", "repositories"),
            )

            columns = {
                row[0]
                for row in cur.fetchall()
            }

            if "github_id" not in columns:
                raise ValueError(
                    "Supabase no tiene la columna github_id."
                )

            available_fields = [
                field
                for field in FIELD_MAP
                if field in columns
            ]

            if not available_fields:
                raise ValueError(
                    "No existen columnas compatibles "
                    "para comparar métricas."
                )

            select_fields = ["github_id"]

            if "full_name" in columns:
                select_fields.append("full_name")

            select_fields.extend(available_fields)

            query = sql.SQL(
                "SELECT {} FROM public.repositories"
            ).format(
                sql.SQL(", ").join(
                    sql.Identifier(field)
                    for field in select_fields
                )
            )

            cur.execute(query)

            records = cur.fetchall()

            db_data = {}

            for record in records:
                item = dict(zip(select_fields, record))

                github_id = item["github_id"]

                if github_id is None:
                    raise ValueError(
                        "Supabase contiene un github_id nulo."
                    )

                github_id = int(github_id)

                if github_id in db_data:
                    raise ValueError(
                        f"ID duplicado en Supabase: {github_id}"
                    )

                db_data[github_id] = item

            csv_ids = {
                repo_id
                for repo_id, _ in data
            }

            db_ids = set(db_data)

            missing = csv_ids - db_ids
            extra = db_ids - csv_ids

            if missing or extra:
                raise ValueError(
                    "Los IDs del CSV y Supabase no coinciden. "
                    f"Faltantes: {len(missing)}. "
                    f"Extras: {len(extra)}. "
                    f"Ejemplos faltantes: {sorted(missing)[:5]}. "
                    f"Ejemplos extras: {sorted(extra)[:5]}."
                )

            print("\nCONEXIÓN DE SOLO LECTURA EXITOSA")
            print(f"Repositorios coincidentes: {len(csv_ids)}")

            # Se compara cada métrica con su propio
            # repositorio, identificado por github_id.
            for repo_id, values in data:

                existing = db_data[repo_id]

                for field in available_fields:

                    if field not in values:
                        continue

                    source, kind = FIELD_MAP[field]

                    new_value = values[field]

                    old_value = normalize_db_value(
                        existing[field],
                        kind,
                    )

                    compared += 1

                    if old_value != new_value:
                        differences.append({
                            "github_id": repo_id,
                            "full_name": existing.get(
                                "full_name", ""
                            ),
                            "campo": field,
                            "columna_origen": source,
                            "valor_supabase": old_value,
                            "valor_csv": new_value,
                        })

            # Se termina la transacción de lectura.
            con.rollback()

    # Se genera un informe local.
    # No se escribe nada en Supabase.
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fh:

        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "github_id",
                "full_name",
                "campo",
                "columna_origen",
                "valor_supabase",
                "valor_csv",
            ],
        )

        writer.writeheader()
        writer.writerows(differences)

    print("\nRESULTADO DE LA COMPARACIÓN")
    print(f"Valores comparados: {compared}")
    print(f"Diferencias detectadas: {len(differences)}")

    counts = Counter(
        row["campo"]
        for row in differences
    )

    for field, count in sorted(counts.items()):
        print(f"  {field}: {count} diferencias")

    print(f"\nReporte generado: {report_path}")
    print("Cambios realizados en Supabase: 0")


def main():
    parser = argparse.ArgumentParser(
        description="Validación y comparación OpenBridge"
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
    )

    parser.add_argument(
        "--expected-count",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Comparar con Supabase sin escribir",
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Deshabilitado: requiere autorización",
    )

    args = parser.parse_args()

    if args.apply:
        parser.error(
            "La escritura en Supabase está deshabilitada "
            "en esta versión."
        )

    if args.expected_count < 1:
        parser.error(
            "--expected-count debe ser mayor que cero."
        )

    try:
        data = load_csv(
            args.csv,
            args.expected_count,
        )

        preview(data)

        if args.check_db:

            db_url = os.environ.get("DATABASE_URL")

            if not db_url:
                raise ValueError(
                    "Falta DATABASE_URL. "
                    "Debe configurarse como secreto "
                    "de GitHub Actions, nunca en el código."
                )

            compare_db(
                data,
                db_url,
                args.report,
            )

        else:
            print(
                "\nMODO LOCAL: no se ha establecido "
                "ninguna conexión con Supabase."
            )

    except Exception as exc:
        parser.exit(
            1,
            f"\nERROR: {exc}\n",
        )


if __name__ == "__main__":
    main()
