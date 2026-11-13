"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.
Run it with uvicorn:

    uv run uvicorn config.asgi:application --reload

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

# runserver serves static files (e.g. the admin's CSS) in DEBUG; uvicorn does not,
# so wrap the app with Django's own static handler for development.
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    application = ASGIStaticFilesHandler(application)
