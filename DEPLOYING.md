# Deploying / sharing IN-GRES AI

Two ways to let someone else open the app:

| Option | Time | URL | Best for |
|--------|------|-----|----------|
| localhost.run tunnel (`share.ps1`) | ~1 min | `https://<random>.lhr.life` (temporary) | sharing with friends right now |
| Docker on a cloud host | ~15 min | permanent `https://your-app.example.com` | real deployments |

---

## Option 1 - Quick share with a friend (no account, temporary)

Prereqs: the app runs locally (backend + frontend) and OpenSSH client is
enabled (Settings > Apps > Optional features, `ssh` on Windows).

```powershell
# from the repository root
powershell -ExecutionPolicy Bypass -File share.ps1
```

The script:

1. Starts the backend (`uvicorn` on :8000) and frontend (`npm run dev` on :5173)
   if they aren't already running.
2. Opens a free reverse SSH tunnel via [localhost.run](https://localhost.run)
   and prints the public `https://*.lhr.life` URL.

Send that URL to your friend. Keep the ssh window open - closing it revokes
the link.

> Why not Cloudflare quick tunnels? On some networks (incl. this machine's)
> cloudflared's embedded DNS resolver fails right after registering
> (`lookup region1.v2.argotunnel.com: i/o timeout`) and drops the tunnel.
> localhost.run uses the system SSH client and is unaffected.

> The dev credentials (see `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` in your local `.env`) are baked into the
> local SQLite database. For anything beyond a quick demo, use Option 2 with
> changed secrets.

---

## Continuous integration

`.github/workflows/ci.yml` runs on every push/PR to `main`:

- Backend: `pytest` (SQLite test database — PostGIS stays disabled in CI).
- Frontend: `tsc --noEmit`, `vitest`, and a production `vite build`.
- Docker: builds both the base backend image and the ML-stack image
  (`INCLUDE_ML=1`), so a `torch` regression breaks the build, not the deploy.

---

## Option 2 - Permanent deployment with Docker

Prereqs: [Docker with Compose v2](https://docs.docker.com/get-docker/), and
a host (any VPS, or a PaaS like Railway / Render / Fly.io) plus a domain.

### 1. Prepare the environment

```powershell
copy .env.docker.example .env
# then edit .env and replace every CHANGE_ME_ value with real secrets:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
#   python -c "import secrets; print(secrets.token_urlsafe(16))"   # DB + user passwords
```

Key values in `.env`:

- `JWT_SECRET` - long random string (auth tokens are signed with it).
- `POSTGRES_PASSWORD`, `DATABASE_URL` - match each other.
- `SEED_ADMIN_PASSWORD`, `SEED_USER_PASSWORD` - change these before exposing.
- `SEED_DATASET` - `demo` (small, fast first boot) or `national` (full all-India
  synthetic set, ~3-5 min first boot) or `none` (upload your own CSV on the
  Admin > Imports page).
- `CORS_ORIGINS` - add your public origin(s); the compose setup is same-origin
  via nginx so CORS is normally not required.

### 2. Build and start

```bash
docker compose up --build -d
docker compose ps          # all three containers should be "healthy"
```

Optional: enable the deep-learning forecast stack (PyTorch LSTM / Transformer
models from Phase 21) by setting `INCLUDE_ML=1` in `.env` before building:

```bash
docker compose build backend   # honours INCLUDE_ML=1 from .env
```

Without it the forecast UI keeps working — deep-learning methods gracefully
fall back to the best statistical model. See `backend/requirements-ml.txt`.

The web app is served by nginx on port **5173** (`http://localhost:5173` on the
host). Point your domain/load balancer at it and terminate HTTPS there (e.g.
Caddy, Traefik, or a PaaS-provided TLS). Put the proxy in front of nginx:

```caddy
your-app.example.com {
    reverse_proxy localhost:5173
}
```

### 3. First-boot notes

- The backend container creates the schema and seeds the dataset
  (`python -m app.database.local_init`) before starting uvicorn; this is
  idempotent so restarts are fast.
- Web Push (PWA notifications) generates VAPID keys on first boot and stores
  them under `data/`; set `WEB_PUSH_ENABLED=true` only after HTTPS is up.
- The chat websocket is already proxied by nginx (`/api/chat/ws`).

---

## Security checklist (do before going public)

- [ ] `JWT_SECRET` is a fresh random value
- [ ] Seeded passwords changed (`SEED_ADMIN_*`, `SEED_USER_*`)
- [ ] `POSTGRES_PASSWORD` / `DATABASE_URL` use a real password
- [ ] HTTPS enabled at the edge (tunnel HTTPS or your own TLS)
- [ ] `ENVIRONMENT=production`
- [ ] LLM/RAG/voice left disabled unless you also expose those services
- [ ] Don't commit `.env` (it contains secrets)

## Teardown

```bash
docker compose down        # stop (keep data)
docker compose down -v     # stop AND delete the database volume
```