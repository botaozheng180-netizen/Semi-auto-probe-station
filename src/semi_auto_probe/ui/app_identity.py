"""Desktop application identity for Windows taskbar grouping."""

from __future__ import annotations

import ctypes
import logging
import sys


WINDOWS_APP_ID = "SemiAutoProbe.Desktop"
logger = logging.getLogger(__name__)


def set_windows_app_identity() -> None:
    """Identify SAP independently of python.exe before creating its window."""
    if sys.platform != "win32":
        return
    try:
        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        result = set_app_id(WINDOWS_APP_ID)
        if result < 0:
            logger.warning("Failed to set Windows application identity: HRESULT %#x", result & 0xFFFFFFFF)
    except (AttributeError, OSError) as exc:
        logger.warning("Windows application identity is unavailable: %s", exc)
