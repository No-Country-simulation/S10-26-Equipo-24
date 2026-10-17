"""Pipeline incremental de metadatos GitHub — No Country.

Ejecución: python pipeline.py --mode daily|weekly --dry-run
No reextrae candidatos; parte de data/catalogo_base.csv (100 IDs).
Guarda snapshots/ETags en SQLite y CSV de salida. No modifica el CSV base.
"""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import requests

BASE = Path('data/catalogo_base.csv')
DB = Path('data/historico.sqlite')
OUTPUT = Path('data/catalogo_actualizado.csv')
LOG = Path('data/errores.csv')
API = 'https://api.github.com'
UTC = dt.timezone.utc

def now():
    return dt.datetime.now(UTC).isoformat()

def setup_db(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS state (
      repo_id INTEGER PRIMARY KEY, etag TEXT, last_checked TEXT,
      last_changed TEXT, last_commit_checked TEXT
    );
    CREATE TABLE IF NOT EXISTS snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT, repo_id INTEGER NOT NULL,
      measured_at TEXT NOT NULL, stars INTEGER, forks INTEGER,
      open_issues_and_pr INTEGER, pushed_at TEXT, license TEXT,
      archived INTEGER, commits_observed INTEGER,
      commits_complete INTEGER, commits_since TEXT,
      source TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS errors (
      id INTEGER PRIMARY KEY AUTOINCREMENT, repo_id INTEGER,
      at TEXT, phase TEXT, http_status INTEGER, message TEXT
    );
    ''')
    conn.commit()

def load_catalog():
    with BASE.open(encoding='utf-8-sig', newline='') as f:
        records = list(csv.DictReader(f))
    if len(records) != 100:
        raise ValueError(f'Se esperaban 100 repositorios y hay {len(records)}')
    ids = [int(r['repo_id']) for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Hay repo_id duplicados')
    return records

def github_get(session, url, params=None, etag=None):
    headers = {'If-None-Match': etag} if etag else {}
    for attempt in range(3):
        response = session.get(url, params=params, headers=headers, timeout=30)
        if response.status_code in (200, 304):
            return response
        if response.status_code in (403, 429):
            print(
                f"GitHub API HTTP {response.status_code} | "
                f"Mensaje: {response.text[:500]} | "
                f"Remaining: {response.headers.get('X-RateLimit-Remaining')} | "
                f"Retry-After: {response.headers.get('Retry-After')} | "
                f"Reset: {response.headers.get('X-RateLimit-Reset')}"
            )
            remaining = response.headers.get('X-RateLimit-Remaining')
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                wait = max(1, float(retry_after))
            elif remaining == '0':
                wait = max(1, int(response.headers.get('X-RateLimit-Reset', '0')) - time.time() + 5)
            else:
                wait = min(60 * (2 ** attempt), 240)
            if attempt < 2:
                print(f'Limitación API HTTP {response.status_code}; espera {wait:.0f}s')
                time.sleep(wait)
                continue
        response.raise_for_status()
    raise RuntimeError('Se agotaron los reintentos de GitHub')

def log_error(conn, rid, phase, exc):
    http = getattr(getattr(exc, 'response', None), 'status_code', None)
    conn.execute('INSERT INTO errors(repo_id,at,phase,http_status,message) VALUES (?,?,?,?,?)',
                 (rid, now(), phase, http, str(exc)[:350]))
    conn.commit()
    print(f'ERROR {rid} {phase}: {exc}', file=sys.stderr)

def update_repo(conn, session, repo, weekly=False):
    rid = int(repo['repo_id'])
    full = repo['nombre_completo']
    state = conn.execute('SELECT etag FROM state WHERE repo_id=?', (rid,)).fetchone()
    etag = state[0] if state else None
    resp = github_get(session, f'{API}/repos/{full}', etag=etag)
    checked = now()
    if resp.status_code == 304:
        conn.execute('INSERT INTO state(repo_id,etag,last_checked) VALUES(?,?,?) '
                     'ON CONFLICT(repo_id) DO UPDATE SET last_checked=excluded.last_checked', (rid, etag, checked))
        # Snapshot solo para cambios, evita duplicaciones artificiales
        conn.commit()
        print(f'{full}: sin cambios (304)')
    else:
        data = resp.json()
        if int(data.get('id', -1)) != rid:
            raise ValueError(f'ID no coincide para {full}: {data.get("id")} vs {rid}')
        lic = (data.get('license') or {}).get('spdx_id')
        conn.execute('''INSERT INTO snapshots
          (repo_id,measured_at,stars,forks,open_issues_and_pr,pushed_at,license,archived,source)
          VALUES (?,?,?,?,?,?,?,?,?)''',
          (rid, checked, data.get('stargazers_count'), data.get('forks_count'),
           data.get('open_issues_count'), data.get('pushed_at'), lic,
           int(bool(data.get('archived'))), 'github_api'))
        conn.execute('''INSERT INTO state(repo_id,etag,last_checked,last_changed)
           VALUES(?,?,?,?) ON CONFLICT(repo_id) DO UPDATE SET
           etag=excluded.etag,last_checked=excluded.last_checked,last_changed=excluded.last_changed''',
           (rid, resp.headers.get('ETag'), checked, checked))
        conn.commit()
        print(f'{full}: metadatos actualizados')
    if weekly:
        since = (dt.datetime.now(UTC) - dt.timedelta(days=90)).isoformat()
        commits_resp = github_get(session, f'{API}/repos/{full}/commits',
                                  params={'since': since, 'per_page': 100, 'page': 1})
        commits = commits_resp.json()
        if not isinstance(commits, list):
            raise ValueError('La API no devolvió una lista de commits')
        # 100 registros implican un mínimo; exactitud desconocida
        observed = len(commits)
        complete = int(observed < 100)
        # La consulta de commits se registra en un snapshot propio incluso si hubo 304 metadata
        conn.execute('''INSERT INTO snapshots
          (repo_id, measured_at, commits_observed, commits_complete, commits_since, source)
          VALUES (?,?,?,?,?,?)''', (rid, now(), observed, complete, since, 'github_commits'))
        conn.execute('INSERT INTO state(repo_id,last_commit_checked) VALUES(?,?) '
                     'ON CONFLICT(repo_id) DO UPDATE SET last_commit_checked=excluded.last_commit_checked', (rid, now()))
        conn.commit()
        print(f'  commits 90d: {observed}{"+" if not complete else ""}')

def export_files(conn, rows):
    # latest metadata and latest commits are separate snapshots; merge by repo_id
    meta = {}
    for row in conn.execute('''SELECT repo_id,measured_at,stars,forks,open_issues_and_pr,pushed_at,license,archived
      FROM snapshots WHERE source='github_api' ORDER BY id'''):
        meta[row[0]] = row[1:]
    commits = {}
    for row in conn.execute('''SELECT repo_id,measured_at,commits_observed,commits_complete,commits_since
      FROM snapshots WHERE source='github_commits' ORDER BY id'''):
        commits[row[0]] = row[1:]
    out_cols = ['actualizado_en','stars_actual','forks_actual','issues_y_pr_abiertos_actual',
                'ultima_actividad_actual','licencia_actual','archivado_actual',
                'commits_consultado_en','commits_90d_observados_actual','commits_conteo_completo_actual',
                'commits_ventana_inicio_actual']
    cols = list(rows[0]) + [c for c in out_cols if c not in rows[0]]
    with OUTPUT.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader()
        for r in rows:
            r = r.copy(); rid = int(r['repo_id'])
            if rid in meta:
                vals = meta[rid]
                r.update(dict(zip(out_cols[:7], vals)))
            if rid in commits:
                r.update(dict(zip(out_cols[7:], commits[rid])))
            w.writerow(r)
    with LOG.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['repo_id','fecha','fase','http_status','mensaje'])
        w.writerows(conn.execute('SELECT repo_id,at,phase,http_status,message FROM errors'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['daily','weekly'], default='daily')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    rows = load_catalog(); DB.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        print(f'DEMO OK: {len(rows)} repositorios únicos. Modo {args.mode}. Sin consultar GitHub.')
        return
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise RuntimeError('Necesitas GITHUB_TOKEN (GitHub Actions lo proporciona automáticamente)')
    session = requests.Session()
    session.headers.update({'Accept': 'application/vnd.github+json',
                            'X-GitHub-Api-Version': '2022-11-28',
                            'Authorization': f'Bearer {token}',
                            'User-Agent': 'nocountry-oss-catalog'})
    failures = 0
    with sqlite3.connect(DB) as conn:
        setup_db(conn)
        for repo in rows[:args.limit]:
            try:
                update_repo(conn, session, repo, weekly=(args.mode == 'weekly'))
                time.sleep(1)
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                failures += 1; log_error(conn, int(repo['repo_id']), args.mode, exc)
                if getattr(getattr(exc, 'response', None), 'status_code', None) in (403, 429):
                    print('Detención preventiva ante límite de GitHub'); break
        export_files(conn, rows)
        print(f'Repositorios catálogo: {len(rows)}; errores en esta ejecución: {failures}')
    if failures:
        sys.exit(1)  # workflow señalizará incidencia, pero conservará datos generados

if __name__ == '__main__':
    main()
