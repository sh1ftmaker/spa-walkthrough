#!/usr/bin/env bash
cd /home/agent-tom/Desktop/volcanospa
while IFS=$'\t' read -r name refs prompt; do printf '%s\0%s\0%s\0' "$name" "$refs" "$prompt"; done < prompts/list4.tsv \
 | xargs -0 -n3 -P4 prompts/gen4.sh
