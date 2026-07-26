#!/bin/bash
# Vercel build script — set this as the project's Build Command in the
# Vercel dashboard (Settings -> Build & Development Settings -> Build
# Command -> "bash setup.sh"). vercel.json intentionally does NOT reference
# this: Vercel's build-hook behavior for @vercel/python is inconsistent
# across config styles, so wiring it through the dashboard setting is the
# one path guaranteed to run every deploy, regardless of platform
# config-format changes.
set -e

echo "==> Installing dependencies"
pip install -r requirements.txt

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Applying database migrations"
# Safe to run on every deploy: migrate is idempotent (a no-op when there's
# nothing new to apply). Requires DATABASE_URL to be set as a Vercel
# environment variable available at build time (it is, by default).
python manage.py migrate --noinput

echo "==> Build complete"
