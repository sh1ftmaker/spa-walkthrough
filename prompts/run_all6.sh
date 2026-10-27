#!/usr/bin/env bash
# texture sheets first (4 at once), then the rest
cd /home/agent-tom/Desktop/volcanospa
while IFS=$'\t' read -r name refs prompt; do printf '%s\0%s\0%s\0' "$name" "$refs" "$prompt"; done < prompts/list6.tsv \
 | xargs -0 -n3 -P4 prompts/gen5.sh
