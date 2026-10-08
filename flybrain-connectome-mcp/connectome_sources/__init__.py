"""Connectome source adapters (T1 of the foundation roadmap).

A *connectome source* is an external reconstructed connectome that can be turned
into ``*_profiles.json`` -- the same shape as ``larva_profiles.json`` /
``cel_profiles.json`` -- so it becomes an independent line of *evidence* for the
functional-unit library (cross-species consistency), not a replacement for the
MaleCNS anchor.

Design rules (deliberately, so the adapters are verifiable and never leak data):

  * Importing this package NEVER touches the network and NEVER fails because a
    dataset is missing.  Each adapter reports ``available()`` locally.
  * Heavy optional deps (openpyxl for .xlsx) are imported lazily inside the
    method that needs them, so the package imports under plain stdlib.
  * H01 / MICrONS are real adapters with a real parse path, but their data is
    multi-GB and not bundled; offline they report ``available() == False`` and
    ``build_profiles()`` returns a structured ``unavailable`` envelope instead
    of crashing.  They are "sampling-ready": point ``H01_DATA_DIR`` /
    ``MICRONS_DATA_DIR`` at a local sample and they parse it.
  * Zebrafish is the one source we actually ship data for (Petkova 2025,
    TEN + HMI under ``zebrafish_data/``), so its adapter produces a real
    ``zebrafish_profiles.json``.

See scripts/check_sources.py (GATE 20) for the enforcement contract.
"""
from __future__ import annotations

from .base import ConnectomeSource, SourceMeta, build_unavailable
from .zebrafish import ZebrafishSource
from .h01 import H01Source
from .microns import MicronsSource

REGISTRY: dict[str, ConnectomeSource] = {
    "male_cns": None,  # the anchor, handled by the unit library directly
    "zebrafish": ZebrafishSource(),
    "h01": H01Source(),
    "microns": MicronsSource(),
}


def list_sources() -> list[dict]:
    """Compact, serialisable status of every registered adapter."""
    out = []
    for sid, src in REGISTRY.items():
        if src is None:
            continue
        out.append({
            "id": src.meta.id,
            "species": src.meta.species,
            "license": src.meta.license,
            "modality": src.meta.modality,
            "available": src.available(),
        })
    return out


def get_source(source_id: str) -> ConnectomeSource | None:
    return REGISTRY.get(source_id)


__all__ = ["ConnectomeSource", "SourceMeta", "build_unavailable",
           "ZebrafishSource", "H01Source", "MicronsSource",
           "REGISTRY", "list_sources", "get_source"]
