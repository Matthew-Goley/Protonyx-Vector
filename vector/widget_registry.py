"""
Auto-discovers all VectorWidget subclasses in vector/widget_types/.

Any .py file placed in that folder that defines a subclass of VectorWidget
will automatically appear in the dashboard widget picker.
"""

import importlib
import pkgutil
from pathlib import Path

from vector.widget_base import VectorWidget


_cache: list[type[VectorWidget]] | None = None


def discover_widgets() -> list[type[VectorWidget]]:
    """Return every VectorWidget subclass found in vector/widget_types/."""
    global _cache
    if _cache is not None:
        return _cache
    types_dir = Path(__file__).parent / 'widget_types'
    found: list[type[VectorWidget]] = []
    for _finder, name, _ispkg in pkgutil.iter_modules([str(types_dir)]):
        module = importlib.import_module(f'vector.widget_types.{name}')
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, VectorWidget)
                and obj is not VectorWidget
            ):
                found.append(obj)
    _cache = found
    return found


def get_widget_class(class_name: str) -> type[VectorWidget] | None:
    """Look up a widget class by its Python class name."""
    return next((c for c in discover_widgets() if c.__name__ == class_name), None)
