"""Vercel entrypoint: Vercel looks for a FastAPI instance named `app` in this file."""

from tdd_api.main import app

__all__ = ["app"]
