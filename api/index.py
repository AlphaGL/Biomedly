"""Vercel serverless entry point.

Vercel's Python runtime auto-detects any file under /api/ that exposes a
module-level WSGI `app` callable and turns it into a serverless function.
vercel.json routes every request here; Django's own URLconf (config/urls.py)
takes it from there. Static files are served by WhiteNoise from within this
same process (see STORAGES["staticfiles"] in config/settings.py) — simpler
and more reliable than a second Vercel builder + path-matching static route.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
