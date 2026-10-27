"""Build an independent graybox reviewer prompt for one group and round.
  .venv/bin/python tools/review/make_review_prompt.py <group> <round>  -> .scratch/briefs/review_<group>_r<round>.prompt"""
import glob, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
g, rnd = sys.argv[1], int(sys.argv[2])
G = json.load(open(os.path.join(ROOT, 'tools', 'review', 'review_groups.json')))[g]
sys.path.insert(0, os.path.join(ROOT, 'tools', 'assembly'))
from spaces_io import load_spaces
S = load_spaces(ROOT)
lines = []
for sid in G['spaces']:
    sp = S[sid]
    sheet = f'3d/renders/contact/{sid}/contact-r{rnd}.jpg'
    c = (sp.get('cameras') or {}).get('concept', {}).get('image', '')
    lines.append(f"- **{sid}** ({sp.get('name', '')}): sheet `{sheet}`; full-size views in `3d/renders/graybox/{sid}/` "
                 f"(entry/reveal/concept at 16x9 and 9x16, strip-0..7); concept image `{c}`. Purpose (from the brief author): {sp.get('purpose', '')}")
refs = sorted(os.path.relpath(f, ROOT) for pat in ('ref-*.png', 'sheet-ref-*.png', 'sheet-mod-*.png') for f in glob.glob(os.path.join(ROOT, 'refs', 'gen', pat)))
rub = open(os.path.join(ROOT, '.scratch', 'briefs', 'review_rubric.md')).read().replace('<ROUND>', str(rnd))
task = f"""{rub}

## Your spaces (round {rnd}, group `{g}`) — give EACH of them due consideration
{chr(10).join(lines)}

{G.get('note', '')}

Take your time per space: open the contact sheet, then the full-size views and the strip frames, then the concept image(s), and compare. Look at neighbouring spaces' sheets when judging transitions (what you see through a doorway is the next space's job to provide, but call it out). Extra eye-level references generated from the concept art for places that have no concept image (use where relevant): {', '.join(refs) or 'none yet'}. The labelled plan shows object ids; the full placement list with ids, assets, positions and the rule that produced each object is in `3d/placements_resolved.json` (filter by "space"), and the space intent files are `3d/spaces/<id>.json` (read them to name the right rule in your fixes — but judge what you SEE, not what the file says it intends).

Write `3d/reviews/r{rnd}/<space_id>.json` for each of your spaces (mkdir the folder if needed). Do not edit anything else."""
open(os.path.join(ROOT, '.scratch', 'briefs', f'review_{g}_r{rnd}.md'), 'w').write(task)
out = subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'brief.py'), '--task', f'.scratch/briefs/review_{g}_r{rnd}.md',
                      '--writes', f'3d/reviews/r{rnd}/', f'.scratch/review_{g}_r{rnd}/'], capture_output=True, text=True, cwd=ROOT).stdout
p = os.path.join(ROOT, '.scratch', 'briefs', f'review_{g}_r{rnd}.prompt'); open(p, 'w').write(out); print(p, len(out.split()))
