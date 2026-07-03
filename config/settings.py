"""Compatibility loader for split settings modules."""

import os


env = os.getenv("DJANGO_ENV", "dev").lower()

if env == "prod":
    from .settings_prod import *  # noqa: F401,F403
else:
    from .settings_dev import *  # noqa: F401,F403
