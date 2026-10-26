# Kazan-yu agent rules

## Part A: every agent (included verbatim in every subagent prompt)
1. **Browsers run on the GPU, never headless.** Use only the browser, CDP port, profile and weston socket the lead assigned to you (started via `tools/gpu_chrome.sh` under `sbg`). Never use CDP `:9222` or another session's port. Never touch the shared browser (`gpu-chrome-profile`, `slg-chrome-profile`, Xvfb `:99`, `bu-default`). Blender `-b` is fine. Most agents should not start a browser at all: submit camera requests to the screenshot queue (`tools/shotq.py submit ...`) instead.
2. **Long-running processes go under `sbg`** (`sbg start <name> -- <cmd>`), never `&`, `nohup`, `setsid` or `disown`. Stop only your own units, by exact name. Never `pkill -f` with a pattern that could match your own shell. Clean up before you finish.
3. **Scratch files go only under `/home/agent-tom/Desktop/volcanospa/.scratch/`.** No wildcard paths. Never use `rm`, `mv` or `cp` with shell variables in their paths.
4. **Write only the paths your task names.** Shared files (`3d/layout.json`, `3d/spaces/`, the material library, the master `.blend`, `3d/inventory.csv`, `3d/status.json`, `3d/agents.json`, `3d/gallery.json`) belong to the lead. Report proposed changes to them instead of writing them.
5. **Links go out in the proxied form**: `https://terminal.sels.tech/lp/<port>/<path>`, never localhost.
6. **Start and finish your report the same way.** Begin by echoing the SHA-256 of `3d/AGENT_RULES.md` (`sha256sum 3d/AGENT_RULES.md`). End by listing every process you started and confirming each one has stopped.
7. Machine: 30 GB RAM shared with other sessions. Blender: `/home/agent-tom/.local/bin/blender -b -P script.py` (Cycles + OptiX on the RTX 4090). At most one Blender GPU job per agent at a time.

## Part B: lead only
- **Publishing:** only to the **public** repo `sh1ftmaker/spa-walkthrough` with public GitHub Pages (owner instruction 2026-10-26, replacing `midjourney/spa-walkthrough`). Publish from a clean checkout containing only the built site, never the build packet (brief, images, plans, spec, lookbook). Heavy data as content-addressed parts, upload only changed parts. Order: parts → per-tier manifests → HTML. After each deploy check every tier loads; fail on any 404 for a referenced file.
- **Commit at every gate** with the owner's identity passed per command (`git -c user.name=… -c user.email=…`). Never set global git config.
- **tm-notify** at gates, bake finish/fail, each review score, fly-through films, publish.
- **Machine:** at most two browsers running at once. Screenshot service `kz-shot-browser` (CDP 9310) is owned by the lead and served through the queue.
