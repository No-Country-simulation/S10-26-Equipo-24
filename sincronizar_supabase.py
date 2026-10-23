#!/usr/bin/env python3
"""Sincroniza SOLO métricas comprobadas desde data/catalogo_actualizado.csv a public.repositories.
Modo predeterminado: validación local SIN escritura. Para aplicar: --apply + DATABASE_URL.
Requiere: pip install 'psycopg[binary]>=3.1,<4'
"""
import argparse
import csv
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_CSV = Path('data/catalogo_actualizado.csv')
REQUIRED = {'repo_id', 'stars_actual', 'forks_actual', 'actualizado_en'}
# Destino -> (fuente, tipo). Campos NO permitidos: categorías, score, issues, descripciones.
FIELD_MAP = {
    'stars': ('stars_actual', 'number'),
    'forks': ('forks_actual', 'number'),
    'license': ('licencia_actual', 'text'),
    'archived': ('archivado_actual', 'bool'),
}
MISSING = {'', 'nan', 'none', 'null', 'n/a', 'sin licencia', 'unknown'}


def positive_int(raw, label):
    s = str(raw or '').strip()
    if not s.isdigit():
        raise ValueError(f'{label}: entero no válido ({s!r})')
    return int(s)


def parse_bool(raw):
    value = str(raw or '').strip().lower()
    if value in {'1', 'true', 't', 'yes', 'si', 'sí'}:
        return True
    if value in {'0', 'false', 'f', 'no'}:
        return False
    return None


def load_csv(path, expected_count):
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        header = set(reader.fieldnames or [])
        if REQUIRED - header:
            raise ValueError(f'Faltan columnas: {sorted(REQUIRED - header)}')
        rows = list(reader)
    if len(rows) != expected_count:
        raise ValueError(f'Se esperaban {expected_count} filas, hay {len(rows)}. Se detiene por seguridad.')
    ids = [positive_int(r['repo_id'], 'repo_id') for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('IDs duplicados en CSV; se detiene.')
    if any(not str(r.get('actualizado_en') or '').strip() for r in rows):
        raise ValueError('Hay filas sin actualizado_en; se detiene.')
    # actualizado_en indica cuándo se actualizó la fila del snapshot; NO es la fecha de commits.
    data = []
    for repo_id, row in zip(ids, rows):
        values = {}
        for target, (source, kind) in FIELD_MAP.items():
            if source not in header:
                continue
            raw = str(row.get(source) or '').strip()
            if kind == 'number':
                if not raw:
                    continue  # Nunca convertir ausencias a 0
                values[target] = positive_int(raw, f'{source} de ID {repo_id}')
            elif kind == 'bool':
                val = parse_bool(raw)
                if val is not None:
                    values[target] = val
            elif raw.lower() not in MISSING:
                values[target] = raw
        data.append((repo_id, values))
    # Un conjunto con 100 ceros casi siempre refleja error de ingesta, no una disminución real.
    for target in ('stars', 'forks'):
        observed = [values[target] for _, values in data if target in values]
        if len(observed) < expected_count:
            raise ValueError(f'{target}: solo {len(observed)}/{expected_count} valores presentes; detener sincronización.')
        if all(v == 0 for v in observed):
            raise ValueError(f'{target}: todas las métricas son cero; detener para revisar origen.')
    return data


def preview(data):
    totals = Counter(key for _, values in data for key in values)
    print(f'CSV validado: {len(data)} IDs únicos.')
    print('Campos a sincronizar: ' + ', '.join(f'{k}={v}' for k, v in sorted(totals.items())))
    print('Primeros 3 IDs y métricas:', data[:3])


def sync(data, db_url, apply):
    import psycopg
    from psycopg import sql
    with psycopg.connect(db_url, connect_timeout=15) as con:
        with con.cursor() as cur:
            cur.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s', ('public','repositories'))
            cols = {r[0] for r in cur.fetchall()}
            if 'github_id' not in cols:
                raise ValueError('La tabla public.repositories no tiene github_id')
            cur.execute('SELECT github_id FROM public.repositories')
            db_ids = {int(row[0]) for row in cur.fetchall() if row[0] is not None}
            csv_ids = {repo_id for repo_id, _ in data}
            missing = csv_ids - db_ids
            extra = db_ids - csv_ids
            if extra:
                raise ValueError(f'{len(extra)} IDs en Supabase no figuran en el CSV; se detiene. Ejemplos: {sorted(extra)[:5]}')
            if missing:
                raise ValueError(f'{len(missing)} IDs del CSV no existen en Supabase; no se escribe. Ejemplos: {sorted(missing)[:5]}')
            updates = 0
            for repo_id, values in data:
                permitted = {k: v for k, v in values.items() if k in cols}
                if not permitted:
                    continue
                assignments = sql.SQL(', ').join(sql.SQL('{} = %s').format(sql.Identifier(key)) for key in permitted)
                query = sql.SQL('UPDATE public.repositories SET {} WHERE github_id = %s').format(assignments)
                if apply:
                    cur.execute(query, [*permitted.values(), repo_id])
                    if cur.rowcount != 1:
                        raise RuntimeError(f'ID {repo_id} afectó {cur.rowcount} filas: rollback')
                updates += 1
            if apply:
                con.commit()
                print(f'COMMIT: {updates} repositorios actualizados.')
            else:
                con.rollback()
                print(f'PREVISUALIZACIÓN CON BD: {updates} filas coinciden; 0 cambios realizados.')
            skipped = sorted(set(FIELD_MAP) - cols)
            if skipped:
                print('Columnas ausentes en la BD y omitidas:', ', '.join(skipped))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv', type=Path, default=DEFAULT_CSV)
    ap.add_argument('--expected-count', type=int, default=100)
    ap.add_argument('--apply', action='store_true', help='Modifica Supabase: requiere DATABASE_URL')
    ap.add_argument('--check-db', action='store_true', help='Verifica IDs en Supabase sin escribir')
    args = ap.parse_args()
    if args.expected_count < 1:
        ap.error('--expected-count debe ser >=1')
    try:
        data = load_csv(args.csv, args.expected_count)
        preview(data)
        if args.apply or args.check_db:
            url = os.environ.get('DATABASE_URL')
            if not url:
                raise ValueError('Falta DATABASE_URL; configúralo como GitHub Actions Secret, nunca en código.')
            sync(data, url, args.apply)
        else:
            print('MODO PRUEBA LOCAL: no se ha conectado a Supabase ni escrito ningún dato.')
    except Exception as exc:
        ap.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
