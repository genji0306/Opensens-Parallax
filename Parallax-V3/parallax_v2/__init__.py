"""Shim package that exposes the V2 gateway namespace."""

from __future__ import annotations

from pathlib import Path

_LOCAL = Path(__file__).resolve().parent
_ROOT = Path(__file__).resolve().parents[2] / "Parallax-V2"
__path__ = [str(_LOCAL)]
if _ROOT.exists():
    __path__.append(str(_ROOT))
