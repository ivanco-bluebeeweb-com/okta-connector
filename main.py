"""Okta Connector entrypoint."""
from __future__ import annotations

import handlers  # noqa: F401
import panels  # noqa: F401
import panels_center  # noqa: F401
import panels_settings  # noqa: F401
from app import ext

extension = ext
