from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return absolute path to a bundled read-only resource."""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller standalone
        base = Path(sys._MEIPASS)
    elif getattr(sys, "frozen", False):
        # Nuitka standalone — assets are placed next to the executable
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)


def user_data_dir() -> Path:
    """Return the writable user app-data directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "Protonyx" / "Vector"
    else:
        path = Path.home() / "Vector" / "data"

    path.mkdir(parents=True, exist_ok=True)
    return path


def user_file(*parts: str) -> Path:
    """Return a path inside the user data directory."""
    return user_data_dir().joinpath(*parts)