#!/usr/bin/env bash
cd /home/agent-tom/Desktop/volcanospa
while IFS=$'\t' read -r name prompt; do printf '%s\0%s\0' "$name" "$prompt"; done < prompts/list.tsv \
 | xargs -0 -n2 -P5 prompts/gen.sh
