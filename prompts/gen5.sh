#!/usr/bin/env bash
# usage: gen5.sh <name> <comma-separated refs: lookbook basenames or project-relative paths> <prompt>  -> refs/gen/<name>.png
# Sheets of several textures / models / views per image (owner: chunk to save Codex images).
cd /home/agent-tom/Desktop/volcanospa
name="$1"; refs="$2"; prompt="$3"
style="$(sed 's/ wide 16:9 landscape\.//' prompts/style.txt)"
log="prompts/logs/$name.log"; mkdir -p prompts/logs refs/gen
[ -f "refs/gen/$name.png" ] && exit 0
iargs=()
IFS=',' read -ra rs <<< "$refs"
for r in "${rs[@]}"; do
  [ -z "$r" ] && continue
  if [[ "$r" == */* ]]; then iargs+=(-i "$r"); else iargs+=(-i "lookbook/img/$r.jpg"); fi
done
timeout 1500 codex exec --skip-git-repo-check -s workspace-write -C "$PWD" "${iargs[@]}" -- \
  "Use your image generation tool to create exactly ONE image, using the attached images as visual references for style, materials, lighting and mood (concept art of the same place; stay consistent with it). Do not do anything else and do not ask questions. SUBJECT: $prompt  ART DIRECTION: $style" </dev/null >"$log" 2>&1
sid=$(grep -m1 'session id:' "$log" | awk '{print $3}')
f=$(ls -t ~/.codex/generated_images/"$sid"/*.png 2>/dev/null | head -1)
if [ -n "$f" ]; then cp "$f" "refs/gen/$name.png"; echo "OK $name"; else echo "FAIL $name $(grep -m1 -o 'ERROR.*' "$log" | cut -c1-120)"; fi
