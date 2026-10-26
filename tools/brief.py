"""Build a subagent prompt: rules Part A + task + inventory rows + writable paths + browser/queue access.

  .venv/bin/python tools/brief.py --task .scratch/briefs/matlib.md --writes 3d/materials/ tools/matlib/ \
      --inventory lantern rock_cluster --browser "none: use the screenshot queue" > .scratch/briefs/matlib.prompt
"""
import argparse, csv, hashlib, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def part_a():
    s = open(os.path.join(ROOT, '3d', 'AGENT_RULES.md')).read()
    a = s.index('## Part A'); b = s.index('## Part B')
    return s[a:b].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True, help='markdown file with the task')
    ap.add_argument('--writes', nargs='+', required=True, help='paths the subagent may write')
    ap.add_argument('--inventory', nargs='*', default=[], help='inventory ids to include')
    ap.add_argument('--browser', default='none. Do not start a browser.')
    a = ap.parse_args()
    rules_sha = hashlib.sha256(open(os.path.join(ROOT, '3d', 'AGENT_RULES.md'), 'rb').read()).hexdigest()
    out = [f'# Kazan-yu subagent brief\n\nProject root: `{ROOT}` (you are a subagent of the lead; report back to the lead, not the owner).',
           f'Rules file SHA-256 (echo this first): `{rules_sha}`', part_a(), '## Your task', open(a.task).read().strip(),
           '## Paths you may write (nothing else)', '\n'.join(f'- `{p}`' for p in a.writes),
           '## Browser / screenshot access', a.browser]
    if a.inventory:
        rows = list(csv.DictReader(open(os.path.join(ROOT, '3d', 'inventory.csv'))))
        sel = [r for r in rows if r['id'] in a.inventory]
        out += ['## Inventory rows', '```csv', ','.join(rows[0].keys()) if rows else '',
                *[','.join(r.values()) for r in sel], '```']
    out += ['## Report format', 'Start: the rules SHA-256. Then: what you built, file paths, check results, open problems, '
            'proposed changes to shared files (as diffs or exact values, do not write them). End: every process you '
            'started and confirmation each one has stopped.']
    print('\n\n'.join(out))


if __name__ == '__main__':
    main()
