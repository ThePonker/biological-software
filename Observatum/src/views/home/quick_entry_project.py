"""Project choice for a Commercial record entered in Quick Entry (review OBS-16).

Quick Entry saved "Commercial" records with no project or client, which no Commercial
report or embargo could then find. A Commercial record now has to name one of the
existing projects (Data Entry creates new ones). The record takes the project's
embargo only when every record of that project has the same one; otherwise none is
set and the caller says so.
"""
from typing import Dict, List


def commercial_projects(db) -> List[Dict]:
    """Existing commercial projects, most records first.

    [{project, client, n, embargo_status, embargo_until}] -- the embargo fields are
    None unless the project's records all share one (status, until) pair.
    """
    rows = db.execute_main("""
        SELECT TRIM(project_name) AS project, COALESCE(TRIM(client), '') AS client,
               COUNT(*) AS n,
               COUNT(DISTINCT COALESCE(embargo_status, '') || '|' || COALESCE(embargo_until, ''))
                   AS embargo_variants,
               MAX(embargo_status) AS embargo_status, MAX(embargo_until) AS embargo_until
        FROM observations
        WHERE record_type = 'Commercial' AND TRIM(COALESCE(project_name, '')) != ''
        GROUP BY TRIM(project_name), COALESCE(TRIM(client), '')
        ORDER BY n DESC, project
    """) or []
    out = []
    for r in rows:
        one = r['embargo_variants'] == 1
        out.append({
            'project': r['project'], 'client': r['client'], 'n': r['n'],
            'embargo_status': (r['embargo_status'] or None) if one else None,
            'embargo_until': (r['embargo_until'] or None) if one else None,
        })
    return out


def project_label(p: Dict) -> str:
    return f"{p['project']} ({p['client']})" if p.get('client') else p['project']
