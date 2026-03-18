"""WSGI entry point for production deployment (Render, Heroku, etc.)."""

from mpd_overwatch.app import create_app

app = create_app()
server = app.server  # Flask server for gunicorn
