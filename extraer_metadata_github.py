#!/usr/bin/env python3
"""Extrae métricas de 100 repositorios GitHub mediante GraphQL.
SOLO LECTURA: no utiliza DATABASE_URL ni escribe en Supabase.
Requiere GITHUB_TOKEN (en Actions) o GH_TOKEN; opcional gh auth token local.
"""
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

CATALOGO = Path('data/catalogo_actualizado.csv')
SALIDA = Path('reportes/metadata_github_verificada.csv')
ERRORES = Path('reportes/metadata_github_errores.csv')
TAMANO = 10

CAMPOS = [
    'repo_id', 'full_name', 'consultado_utc', 'issues_abiertos', 'issues_cerrados',
    'prs_abiertos', 'prs_cerrados', 'languages', 'archived', 'disabled',
    'tiene_release', 'tiene_tags', 'fecha_ultimo_release', 'num_releases', 'num_tags'
]

def token():
    v = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if v:
        return v
    if os.environ.get('GITHUB_ACTIONS'):
        raise RuntimeError('GITHUB_TOKEN ausente en GitHub Actions')
    try:
        r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise RuntimeError('Falta autenticacion. Ejecuta en GitHub Actions o inicia sesion con gh auth login. No pegues tokens en el chat.')

def query_for(group):
    pieces = []
    for idx, (_repo_id, full) in enumerate(group):
        owner, name = full.split('/', 1)
        pieces.append(f'''r{idx}: repository(owner:{json.dumps(owner)},name:{json.dumps(name)}) {{
            databaseId nameWithOwner isArchived isDisabled
            issuesOpen: issues(states:OPEN) {{totalCount}}
            issuesClosed: issues(states:CLOSED) {{totalCount}}
            prsOpen: pullRequests(states:OPEN) {{totalCount}}
            prsClosed: pullRequests(states:[CLOSED,MERGED]) {{totalCount}}
            languages(first:5, orderBy:{{field:SIZE,direction:DESC}}) {{nodes {{name}}}}
            releases(first:1, orderBy:{{field:CREATED_AT,direction:DESC}}) {{
                totalCount nodes {{publishedAt}}
            }}
            refs(refPrefix:"refs/tags/",first:1) {{totalCount}}
        }}''')
    return 'query OpenBridgeMetadata {\n' + '\n'.join(pieces) + '\n}'

def request_graphql(secret, query):
    payload = json.dumps({'query': query}).encode('utf-8')
    req = urllib.request.Request(
        'https://api.github.com/graphql', data=payload,
        headers={'Authorization': f'Bearer {secret}', 'Accept':'application/vnd.github+json',
                 'Content-Type':'application/json', 'User-Agent':'OpenBridge-Metadata-Audit'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errors'):
        raise RuntimeError('GitHub GraphQL reporto error: ' + str(data['errors'])[:650])
    if not isinstance(data.get('data'), dict):
        raise RuntimeError('Respuesta GraphQL sin campo data')
    return data['data']

def main():
    if not CATALOGO.exists():
        raise RuntimeError(f'No se encontro {CATALOGO}')
    with CATALOGO.open(encoding='utf-8-sig', newline='') as f:
        items = list(csv.DictReader(f))
    if len(items) != 100:
        raise RuntimeError(f'Esperados 100 repositorios, encontrados {len(items)}')
    repos = []
    for r in items:
        full = (r.get('nombre_completo') or '').strip()
        rid = int(r['repo_id'])
        if '/' not in full:
            raise RuntimeError(f'Nombre de repositorio invalido: {full}')
        repos.append((rid, full))
    if len({x[0] for x in repos}) != 100 or len({x[1].casefold() for x in repos}) != 100:
        raise RuntimeError('El catalogo contiene duplicados')

    secret = token()
    # No imprimir el token ni el cuerpo de las solicitudes.
    registros, errores = [], []
    ahora = datetime.now(timezone.utc).isoformat()
    for inicio in range(0, 100, TAMANO):
        group = repos[inicio:inicio+TAMANO]
        try:
            datos = request_graphql(secret, query_for(group))
            for idx, (rid, full) in enumerate(group):
                repo = datos.get(f'r{idx}')
                if not repo:
                    errores.append({'full_name':full,'error':'Repositorio no encontrado o sin acceso'})
                    continue
                if repo.get('databaseId') != rid:
                    errores.append({'full_name':full,'error':'GitHub ID distinto al catalogo'})
                    continue
                try:
                    nombres = [x['name'] for x in repo['languages']['nodes'] if x and x.get('name')]
                    releases = repo['releases']
                    total_releases = int(releases['totalCount'])
                    tags = repo['refs']
                    total_tags = int(tags['totalCount']) if tags else 0
                    fecha_release = None
                    if releases.get('nodes'):
                        fecha_release = releases['nodes'][0].get('publishedAt')
                    item = {
                        'repo_id':rid,
                        'full_name':repo['nameWithOwner'],
                        'consultado_utc':ahora,
                        'issues_abiertos':int(repo['issuesOpen']['totalCount']),
                        'issues_cerrados':int(repo['issuesClosed']['totalCount']),
                        'prs_abiertos':int(repo['prsOpen']['totalCount']),
                        'prs_cerrados':int(repo['prsClosed']['totalCount']),
                        'languages':', '.join(nombres) if nombres else '',
                        'archived':repo['isArchived'],
                        'disabled':repo['isDisabled'],
                        'tiene_release':total_releases>0,
                        'tiene_tags':total_tags>0,
                        'fecha_ultimo_release':fecha_release or '',
                        'num_releases':total_releases,
                        'num_tags':total_tags,
                    }
                    registros.append(item)
                except (KeyError, TypeError, ValueError) as e:
                    errores.append({'full_name':full,'error':f'Campos incompletos: {e}'})
        except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
            for _, full in group:
                errores.append({'full_name':full,'error':str(e)[:300]})
        print(f'Procesados {min(inicio+TAMANO,100)}/100 | completos {len(registros)} | errores {len(errores)}', flush=True)
        time.sleep(1)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=CAMPOS); w.writeheader(); w.writerows(registros)
    with ERRORES.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=['full_name','error']); w.writeheader(); w.writerows(errores)
    print(f'RESULTADO: {len(registros)}/100 datos extraidos. Sin modificar Supabase.')
    print(f'CSV: {SALIDA} | Errores: {ERRORES}')
    if len(registros) != 100:
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', str(exc), file=sys.stderr)
        sys.exit(1)
