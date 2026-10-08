"""Base class and shared helpers for connectome source adapters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SourceMeta:
    id: str
    species: str
    license: str
    modality: str
    data_dir_env: str = ""
    default_data_dir: str = ""


class ConnectomeSource:
    """A reconstructable connectome that yields ``*_profiles.json``.

    Subclasses implement ``available()`` and ``build_profiles(out)``.  The base
    provides the honest ``unavailable`` envelope so an offline install degrades
    gracefully instead of crashing.
    """

    meta: SourceMeta

    def available(self) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError

    def load(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def build_profiles(self, out: Path) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {
            "id": self.meta.id,
            "species": self.meta.species,
            "license": self.meta.license,
            "modality": self.meta.modality,
            "available": self.available(),
        }


def build_unavailable(meta: SourceMeta, reason: str) -> dict[str, Any]:
    """Structured envelope returned when a multi-GB source is not local."""
    return {
        "id": meta.id,
        "species": meta.species,
        "license": meta.license,
        "modality": meta.modality,
        "status": "unavailable",
        "reason": reason,
        "how": ("set %s to a local sample directory (or download the public "
                "bucket) and re-run build_profiles()" % meta.data_dir_env)
        if meta.data_dir_env else "source not bundled",
        "neuron_profiles": {},
    }


def data_dir(meta: SourceMeta) -> Path | None:
    import os
    if meta.data_dir_env and os.environ.get(meta.data_dir_env):
        return Path(os.environ[meta.data_dir_env])
    if meta.default_data_dir:
        p = Path(meta.default_data_dir)
        if p.exists():
            return p
    return None
