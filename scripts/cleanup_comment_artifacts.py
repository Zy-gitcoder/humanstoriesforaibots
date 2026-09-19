"""Retire Pages build archives after deployment so removed text is not retained.

Only artifacts named github-pages from this repository's pages.yml are touched.
The deployed website and separate current Release assets are unaffected.
"""
import os
from sync_comments import API, request


def main():
    workflow = request(API + '/actions/workflows/pages.yml', authenticated=True)['id']
    page, candidates = 1, []
    while True:
        result = request(API + f'/actions/artifacts?name=github-pages&per_page=100&page={page}', authenticated=True)
        rows = result['artifacts']
        candidates.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    runs, removed = {}, 0
    current_run = int(os.environ['GITHUB_RUN_ID'])
    for artifact in candidates:
        run_id = artifact.get('workflow_run', {}).get('id')
        if not run_id or artifact['name'] != 'github-pages':
            continue
        if run_id not in runs:
            runs[run_id] = request(API + f'/actions/runs/{run_id}', authenticated=True)
        run = runs[run_id]
        if run['workflow_id'] != workflow or (run_id != current_run and run['status'] != 'completed'):
            continue
        request(API + f'/actions/artifacts/{artifact["id"]}', 'DELETE', authenticated=True)
        removed += 1
    print(f'Retired {removed} Pages build artifacts after successful deployment.')


if __name__ == '__main__':
    main()
