# Bludhaven

Bludhaven is a Django-based web application that provides a dynamic, scene-layered main page with an in-browser visual editor for administrators.

---

## Features

- **Scene-layer architecture** — the main page is assembled from database-driven layers with fixed tier ordering (`bg_image → parallax_far → bg_text → main_image → text/clock/menu → sticker → parallax_near → parallax_ultra_near`).
- **Parallax engine** — smooth mouse-driven parallax for far/near/ultra-near layers.
- **Sticker edit mode** — 4-corner resize, rotation, z-index controls, with dirty-state tracking and bulk PATCH on exit.
- **Image upload pipeline** — webp/avif variant generation, EXIF removal, original file purge, magic-bytes validation.
- **Revision history** — snapshot-based undo/redo with server-side restore.
- **Admin panel** — draggable editor panel with layer list, property editor, undo/redo (20 steps), dirty indicator, and viewport mode preview.

---

## Requirements

| Component | Version |
|---|---|
| Python | 3.12 |
| Django | 5.2.x |
| Pillow (+ libwebp) | 10.4.x |
| djangorestframework | 3.17.x |
| gunicorn | 23.x |
| PostgreSQL (production) | 16 |

---

## Quick Start (Local Development)

```bash
# 1. Clone and create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment variables
cp .env.example .env
# Edit .env — leave DB_ENGINE unset to use SQLite for local dev

# 4. Apply migrations
python manage.py migrate

# 5. Create a superuser (admin)
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Open `http://localhost:8000`. Log in as a superuser to see the editor panel on the main page.

---

## Production Deploy (Docker Compose)

```bash
# 1. Copy and fill in production values
cp .env.example .env
# Set SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DB_* vars

# 2. Build and start
docker compose up -d --build

# 3. Check health
curl http://localhost/healthz  # → "ok"
```

The compose stack runs:
- **db** — PostgreSQL 16
- **web** — Django + gunicorn (migrates and collects static on startup)
- **nginx** — serves `/static/` and `/media/` directly; proxies everything else to gunicorn

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev key | Django secret key — **must** be changed in production |
| `DEBUG` | `True` | Set `False` in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,...` | Comma-separated hostnames |
| `DB_ENGINE` | `django.db.backends.sqlite3` | Set to `django.db.backends.postgresql` for postgres |
| `DB_NAME` | `toybox_db` | Database name |
| `DB_USER` | `admin` | Database user |
| `DB_PASSWORD` | _(empty)_ | Database password |
| `DB_HOST` | `db` | Database host |
| `DB_PORT` | `5432` | Database port |

See [`.env.example`](.env.example) for a ready-to-copy template.

---

## Image Upload Policy

| Item | Limit / Rule |
|---|---|
| Maximum file size | 15 MB |
| Accepted formats | JPEG, PNG, WebP, AVIF, GIF |
| Format validation | Magic-bytes checked (extension alone is insufficient) |
| Variants generated | `full`, `large` (1920px), `medium` (1280px), `thumb` (512px) — each as webp (and avif where Pillow supports it) |
| EXIF data | Stripped during transcode (`ImageOps.exif_transpose` + re-encode) |
| Original file | Purged immediately after transcoding; `original_deleted_at` timestamp recorded in `MediaAsset` |

---

## Admin Usage Guide

### Opening the editor
Log in as a Django superuser, then visit the main page. A draggable **EDITOR** panel appears in the top-right corner.

### Creating a scene
1. Click **새 씬** to create a new scene.
2. Select it in the scene dropdown and click **활성화** to make it live.

### Adding a layer
1. Choose a layer type from the **레이어 추가** dropdown.
2. Click **추가** — the layer appears with default position/size.
3. Select it in the **레이어 목록**, then edit its properties in the **선택 레이어 속성** section.
4. Click **적용** to preview immediately (changes are local until saved).

### Uploading an image asset
1. Click the file picker in **에셋 업로드**, choose an image (JPEG/PNG/WebP/AVIF).
2. Select the asset kind and click **업로드**.
3. Copy the returned asset URL into the selected layer's **Asset URL** field and click **적용**.

### Saving
- **저장** — persists the current scene's viewport mode.  
- **리비전 저장** — takes a full snapshot of all current layers (max 50 per scene retained).

### Undo / Redo
Use the **Undo** / **Redo** buttons (up to 20 local steps each).

### Sticker edit mode
1. Click **스티커 편집** to enter sticker edit mode.  
2. Hover over any sticker to reveal resize handles (4 corners), a rotation handle (top-centre), and z-index `+`/`-` buttons.  
3. Drag a corner to resize; hold **Shift** to constrain the aspect ratio.  
4. Drag the rotation handle to rotate around the sticker's centre.  
5. Click **스티커 편집** again to exit — all dirty stickers are batch-PATCHed to the server.

---

## Backup & Restore (Revisions)

**Create a snapshot (API):**
```http
POST /api/editor/revisions
Content-Type: application/json
X-CSRFToken: <token>

{ "scene_id": 1 }
```

**Restore a snapshot:**
```http
POST /api/editor/revisions/{revision_id}/restore
Content-Type: application/json
X-CSRFToken: <token>

{}
```

Restoring replaces all layers in the scene with the snapshot's layer set atomically.

---

## Running Tests

```bash
python manage.py test
```

Test coverage includes:
- Tier coercion and all `TYPE_TIER_MAP` entries
- `sortLayersForRender` ordering (tier → z_index → id)
- Coordinate/rotation/scale/opacity storage
- Sticker z-index boundary validation (0–999)
- Invalid layer type rejection (400)
- Admin gate on all editor endpoints (403)
- Invalid tier PATCH rejection (400)
- File magic-bytes validation (JPEG, PNG, fakes)
- Upload pipeline (valid JPEG → 201, fake file → 400, anon → 403)
- Revision snapshot + restore flow
- `/healthz` endpoint (200 OK)
