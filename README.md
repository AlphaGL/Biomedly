# Biomedly

A help-guide web app for biomedical engineers, technicians (BMETs), and IT staff:
**snap a photo of a medical machine** (or search it by name / UDI barcode) and get
its identity, components and their roles, working principle, and a step-by-step
troubleshooting guide.

## Features

- **Snap & Ask** — upload a photo + a question. AI vision (Gemini, free tier —
  or Claude) identifies the equipment and answers in one of four modes:
  *Identify*, *Components*, *How it works*, *Troubleshoot* (safety-first
  diagnostic procedure). Multiple Gemini keys rotate automatically when one
  hits its daily quota.
- **Research** — live search across:
  - [iFixit Medical Library](https://www.ifixit.com/biomed) (repair guides, device pages, images)
  - [openFDA Device APIs](https://open.fda.gov/apis/device/) (official classification, recalls)
  - [NIH AccessGUDID](https://accessgudid.nlm.nih.gov/) (identify a device from its UDI barcode)
- **Grounded AI answers** — the AI is fed the live iFixit/FDA data for the
  equipment so answers reference real guides and official classifications.
- **History** — every analysis is saved and browsable at `/history/`.

## Stack

Django 5 · HTML/CSS/vanilla JS · Postgres (Neon) via DATABASE_URL, SQLite fallback ·
Gemini API (photos + video; pro→flash accuracy-first, multi-key rotation) or
Claude API · requests (iFixit / openFDA / AccessGUDID).

Chat-style assistant: multi-turn conversations with clickable follow-up
questions, audience levels (student / technician / senior engineer), up to
4 photos + 1 short video (<18 MB) per question — media analyzed in memory,
never stored.

## Setup

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure keys
copy .env.example .env
#    then edit .env and set GEMINI_API_KEY_1=... (free at aistudio.google.com)
#    or ANTHROPIC_API_KEY=... (https://platform.claude.com)
#    Needed for Snap & Ask; search/UDI lookup work without any key.

# 3. Initialize the database
python manage.py migrate

# 4. Run
python manage.py runserver
```

Open http://127.0.0.1:8000/

Optional: `python manage.py createsuperuser` for the `/admin/` panel.

## Project layout

```
config/                 Django settings & root URLs
equipment/
  services/ifixit.py    iFixit public API client
  services/openfda.py   openFDA classification/recalls + AccessGUDID UDI lookup
  services/ai.py        Claude vision analysis (grounded with the above)
  views.py              Pages + JSON endpoints (/api/search, /api/udi, /api/analyze)
templates/              base.html, home, history
static/                 css/style.css, js/app.js
```

## Safety note

Biomedly is an assistant, not a substitute for manufacturer service manuals,
scheduled PM procedures, or hospital biomedical-engineering policy. Always
verify safety-critical steps (electrical isolation, patient disconnection,
gas/pressure hazards) against official documentation.
