#!/usr/bin/env bash
# Keeps the progress site current: posts new/changed renders every 60 s. Run under sbg as kz-gallery-sync.
cd /home/agent-tom/Desktop/volcanospa
while true; do .venv/bin/python tools/sync_gallery.py 2>&1 | grep -v '^added 0 ' ; sleep 60; done
