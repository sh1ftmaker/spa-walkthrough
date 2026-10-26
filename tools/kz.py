"""Lead-side helpers for the progress-site JSON files (atomic writes into 3d/)."""
import json, os, sys, time, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D3 = os.path.join(ROOT, '3d'); SCRATCH = os.path.join(ROOT, '.scratch')

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def write_json(rel, obj):
    os.makedirs(SCRATCH, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=SCRATCH, suffix='.json')
    with os.fdopen(fd, 'w') as f: json.dump(obj, f, indent=2)
    os.chmod(tmp, 0o664)
    os.replace(tmp, os.path.join(D3, rel))

def read_json(rel, default=None):
    try:
        with open(os.path.join(D3, rel)) as f: return json.load(f)
    except FileNotFoundError: return default

def status(**kw):
    s = read_json('status.json', {})
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(s.get(k), dict): s[k].update(v)
        else: s[k] = v
    s['updated'] = now(); write_json('status.json', s); return s

def gate(name, result='pass', notes=''):
    s = read_json('status.json', {})
    s.setdefault('gates', []).append({'name': name, 'result': result, 'time': now(), 'notes': notes})
    s['updated'] = now(); write_json('status.json', s)

def agent(id, **kw):
    a = read_json('agents.json', [])
    e = next((x for x in a if x['id'] == id), None)
    if e is None: e = {'id': id, 'outputs': []}; a.append(e)
    e.update(kw); e['updated'] = now(); write_json('agents.json', a)

def gallery(**kw):
    g = read_json('gallery.json', []); kw.setdefault('time', now()); g.append(kw); write_json('gallery.json', g)

def notify(title, body='', tag=None):
    cmd = ['tm-notify', title] + ([body] if body else []) + (['--tag', tag] if tag else [])
    subprocess.run(cmd, check=False)

if __name__ == '__main__':
    # CLI: python3 tools/kz.py status '{"phase":"Plan"}'  | gate NAME RESULT NOTES | notify T B
    cmd = sys.argv[1]
    if cmd == 'status': status(**json.loads(sys.argv[2]))
    elif cmd == 'gate': gate(*sys.argv[2:])
    elif cmd == 'agent': agent(sys.argv[2], **json.loads(sys.argv[3]))
    elif cmd == 'gallery': gallery(**json.loads(sys.argv[2]))
    elif cmd == 'notify': notify(*sys.argv[2:])
