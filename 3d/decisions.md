# Decisions

The build agent records each conflict here, along with what it chose and why.

## Preflight
- **Publish target.** Brief says private `midjourney/spa-walkthrough`; the gh account `sh1ftmaker` has no access to that org. Owner instructed (2026-10-26): publish as a **public** repo under `sh1ftmaker` instead → `sh1ftmaker/spa-walkthrough`, public Pages. Build packet still never published.
- **Where heavy data lives.** Tested 2026-10-26: a page on `sh1ftmaker.github.io/spa-walkthrough` fetches a part from the Pages site fine, but `fetch()` of a GitHub release asset fails (no CORS on the redirect). So the content-addressed parts (`parts/<sha16>.<ext>`) ship **inside the Pages site** on the `gh-pages` branch. Git only stores parts that changed, which keeps the "upload only changed parts" rule. Limits: 1 GB site, 100 MB per file, so keep each part under about 50 MB.
- **Commit identity.** The owner hasn't answered yet, so commits use `sh1ftmaker` / `53912102+sh1ftmaker@users.noreply.github.com` (the GitHub noreply address, so a public repo doesn't expose a personal email). I'll switch if the owner gives another identity.
