#!/usr/bin/env bash
# usage: gen.sh <name> <prompt>   -> images/<name>.png
cd /home/agent-tom/Desktop/volcanospa
name="$1"; prompt="$2"; style="$(cat prompts/style.txt)"
log="prompts/logs/$name.log"; mkdir -p prompts/logs
[ -f "images/$name.png" ] && exit 0
timeout 900 codex exec --skip-git-repo-check -s workspace-write -C "$PWD" \
  "Use your image generation tool to create exactly ONE image. Do not do anything else and do not ask questions. SUBJECT: $prompt  $style" </dev/null >"$log" 2>&1
sid=$(grep -m1 'session id:' "$log" | awk '{print $3}')
f=$(ls -t ~/.codex/generated_images/"$sid"/*.png 2>/dev/null | head -1)
if [ -n "$f" ]; then cp "$f" "images/$name.png"; echo "OK $name"; else echo "FAIL $name"; fi
