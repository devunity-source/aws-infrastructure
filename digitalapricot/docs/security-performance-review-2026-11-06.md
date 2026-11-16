# Digital Apricot security and performance review, 2026-11-06

Scope: `digitalapricot/` (site source, config, public files, deploy script and nginx config) and its deploy workflow, `.github/workflows/deploy-digitalapricot.yml`.

Verified: `npm run build` passes (109 pages); `bash -n deploy/deploy.sh` passes.
Not verified: `nginx` and `actionlint` were not installed, so the nginx and workflow edits were read by eye only. Run `nginx -t` and check the workflow on a branch before relying on it.

## Fixed

| Severity | Where | Change |
|---|---|---|
| Medium | `deploy-digitalapricot.yml` | Added `permissions: contents: read`, `persist-credentials: false`, `timeout-minutes: 15`. |
| Medium | `deploy-digitalapricot.yml` | Secrets were interpolated into shell with `${{ secrets.* }}`, a script-injection and leak risk. They now go through `env:`. The deploy key is written under `umask 077`. |
| Low | `deploy-digitalapricot.yml` | `cancel-in-progress` set to false so a newer push cannot kill `rsync --delete` half way. |
| Medium | `deploy/deploy.sh` | Remote path escaped with `printf %q`, `--` added before the host, rsync `-e` string quoted. |
| Medium | `deploy/digitalapricot.io.conf` | `add_header` inside a location replaces the server-level headers, so `/_astro/` and image responses lost the security headers. They are repeated there. |
| Low | `deploy/digitalapricot.io.conf` | `server_tokens off`, `Permissions-Policy`, better gzip level, minimum size and MIME types. |
| Low | `src/components/ProductCard.astro` | Source links now `rel="noopener nofollow"` (already on main). |

No issues found: XSS (`set:html` is only used on the site's own JSON-LD; the search `innerHTML` escapes every value), third-party scripts (only Google), image handling (dimensions, lazy loading and WebP are in place, largest PNG about 123 KB), secrets in the repo. The IDs in `site.ts` and the Pinterest verification tag are public by design.

## Open items

### High
- **Dependency vulnerabilities.** `npm audit` reports 5 (3 high, 2 moderate) in `undici`, `vite`, `zod` and `postcss-selector-parser`. They are build-time tools and the site ships as static files, so runtime exposure is low. `npm audit fix` failed on the `/mnt/c` copy with a permissions error. Run it from a normal shell and commit `package-lock.json`. The `postcss-selector-parser` fix needs `--force`; test it separately.

### Medium
- **Consent default.** `src/layouts/Base.astro` loads GTM and gtag with no `gtag('consent','default')` before them. PR #29 (the `/cookies` page and Consent Mode v2) is not on this branch. Re-check after it merges.
- **Pin GitHub Actions by commit SHA** (they use `@v4`/`@v5` tags) and add Dependabot.
- **`deploy.sh` uses `StrictHostKeyChecking=accept-new`.** The workflow pins the host key but the script does not. Pre-seed `known_hosts`.
- **TLS and HSTS.** `digitalapricot.io.conf` is HTTP-only and certbot adds HTTPS. HSTS is left commented out. Enable it once HTTPS is confirmed, and make sure certbot's 443 block keeps the headers. Brotli and HTTP/2 belong in the global nginx config or the HTTPS block.

### Low
- **No Content-Security-Policy.** The site uses inline scripts and AdSense, so it needs a policy built for them.
- **Render-blocking Google Fonts** (`Base.astro`, `RetroMonitor.astro`). Self-hosting the fonts would fix it.
