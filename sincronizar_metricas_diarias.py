#!/usr/bin/env python3
"""Sincronizacion segura de metricas GitHub -> Supabase.

Solo modifica stars, forks, license y archived en public.repositories.
No inserta ni elimina repositorios; tampoco modifica ideas, categorias o embeddings.

Uso:
  python sincronizar_metricas_diarias.py --check
  python sincronizar_metricas_diarias.py --apply

Requiere DATABASE_URL en el entorno, y psycopg>=3.1.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from collections import Counter
from pathlib import Path

import psycopg
from psycopg import sql

CSV_PATH = Path('data/catalogo_actualizado.csv')
COL_MAP = {
    'stars': 'stars_actual',
    'forks': 'forks_actual',
    'license': 'licencia_actual',
    'archived': 'archivado_actual',
}
MISSING_LICENSE = {'', 'nan', 'none', 'null', 'n/a', 'sin licencia', 'unknown'}


def require_integer(raw: str | None, label: str, *, positive: bool = False) -> int:
    value = (raw or '').strip()
    if not value.isdecimal():
        raise ValueError(f'{label}: entero no valido')
    result = int(value)
    if positive and result == 0:
        raise ValueError(f'{label}: debe ser mayor que 0')
    return result


def parse_bool(raw: str | None, label: str) -> bool:
    value = (raw or '').strip().lower()
    if value in {'1', 'true', 't', 'yes', 'si', 'sí'}:
        return True
    if value in {'0', 'false', 'f', 'no'}:
        return False
    raise ValueError(f'{label}: booleano no valido')


def load_csv(path: Path, max_age_hours: int) -> dict[int, dict]:
    if not path.is_file():
        raise FileNotFoundError(f'No existe el CSV: {path}')
    with path.open(newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        required = {'repo_id', 'actualizado_en', *COL_MAP.values()}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'Faltan columnas: {sorted(missing)}')
        rows = list(reader)

    if len(rows) != 100:
        raise ValueError(f'Esperados 100 repositorios; encontrados {len(rows)}')

    now = dt.datetime.now(dt.timezone.utc)
    most_recent = None
    data = {}
    for r in rows:
        rid = require_integer(r['repo_id'], 'repo_id', positive=True)
        if rid in data:
            raise ValueError(f'ID duplicado: {rid}')
        try:
            updated = dt.datetime.fromisoformat(r['actualizado_en'].strip().replace('Z', '+00:00'))
        except (ValueError, AttributeError) as exc:
            raise ValueError(f'Fecha invalida para ID {rid}') from exc
        if updated.tzinfo is None or updated > now + dt.timedelta(minutes=5):
            raise ValueError(f'Fecha invalida o futura para ID {rid}')
        most_recent = max(most_recent, updated) if most_recent else updated

        stars = require_integer(r['stars_actual'], f'stars_actual, ID {rid}')
        forks = require_integer(r['forks_actual'], f'forks_actual, ID {rid}')
        archived = parse_bool(r['archivado_actual'], f'archivado_actual, ID {rid}')
        license_value = (r['licencia_actual'] or '').strip()
        item = {'stars': stars, 'forks': forks, 'archived': archived}
        if license_value.lower() not in MISSING_LICENSE:
            item['license'] = license_value
        data[rid] = item

    if (now - most_recent).total_seconds() > max_age_hours * 3600:
        raise ValueError(
            f'CSV sin cambios recientes: ultima actualizacion {most_recent.isoformat()}; '
            f'maximo {max_age_hours} horas. No se aplicaran datos posiblemente obsoletos.'
        )
    for name in ('stars', 'forks'):
        vals = [item[name] for item in data.values()]
        if len(set(vals)) == 1:
            raise ValueError(f'{name}: los 100 valores son identicos; posible ingesta erronea')
    return data


def sync(data: dict[int, dict], apply: bool) -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('Falta DATABASE_URL en el entorno (secreto de GitHub Actions)')

    with psycopg.connect(db_url, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT github_id, stars, forks, license, archived FROM public.repositories')
            records = cur.fetchall()
            db = {}
            for rid, stars, forks, license_value, archived in records:
                if rid is None or int(rid) in db:
                    raise ValueError('Hay github_id nulos o duplicados en Supabase')
                db[int(rid)] = {
                    'stars': stars, 'forks': forks,
                    'license': license_value, 'archived': archived,
                }
            if set(db) != set(data):
                raise ValueError(
                    f'IDs diferentes entre CSV y Supabase. '
                    f'Faltantes={len(set(data)-set(db))}, extras={len(set(db)-set(data))}'
                )
            if len(db) != 100:
                raise ValueError(f'Supabase tiene {len(db)} repositorios; se esperaban 100')

            changes = []
            counts = Counter()
            for rid, updated in data.items():
                difference = {k: v for k, v in updated.items() if db[rid][k] != v}
                if difference:
                    changes.append((rid, difference))
                    counts.update(difference.keys())
            print(f'Repositorios verificados: {len(data)}/100')
            print(f'Repositorios con cambios: {len(changes)}')
            print(f'Campos cambiados: {dict(sorted(counts.items()))}')

            if not apply:
                print('MODO COMPROBACION: Supabase sin cambios. Use --apply solo tras autorizacion.')
                conn.rollback()
                return

            for rid, difference in changes:
                set_clause = sql.SQL(', ').join(
                    sql.SQL('{} = %s').format(sql.Identifier(column))
                    for column in difference
                )
                statement = sql.SQL('UPDATE public.repositories SET {} WHERE github_id = %s').format(set_clause)
                cur.execute(statement, [*difference.values(), rid])
                if cur.rowcount != 1:
                    raise RuntimeError(f'Actualizacion inesperada en github_id {rid}')
            # La conexion confirma la transaccion al salir sin excepciones.
    if apply:
        print(f'SINCRONIZACION CORRECTA: {len(changes)} repositorios actualizados.')
        print('Sin INSERT/DELETE. Categorias, ideas, embeddings y Health Score intactos.')


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true', help='Comparar sin escribir')
    modes.add_argument('--apply', action='store_true', help='Actualizar solamente las 4 columnas permitidas')
    parser.add_argument('--csv', type=Path, default=CSV_PATH)
    parser.add_argument('--max-age-hours', type=int, default=72)
    args = parser.parse_args()
    if args.max_age_hours < 1:
        parser.error('--max-age-hours debe ser positivo')
    data = load_csv(args.csv, args.max_age_hours)
    sync(data, apply=args.apply)


if __name__ == '__main__':
    main()
