"""Central Data Index -- managed file storage with metadata.

Uploaded/loaded LAS files are copied to a central location
(``~/.mpd-overwatch/data/files/``) and indexed in a JSON manifest.
All platform components discover data through this index rather than
ad-hoc file paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path.home() / ".mpd-overwatch" / "data"


class DataIndex:
    """Central indexed file store.

    Parameters
    ----------
    root : Path or str, optional
        Root directory for the index.  Defaults to ``~/.mpd-overwatch/data/``.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = Path(root) if root else _DEFAULT_ROOT
        self._files_dir = self._root / "files"
        self._manifest_path = self._root / "manifest.json"

        self._root.mkdir(parents=True, exist_ok=True)
        self._files_dir.mkdir(parents=True, exist_ok=True)

        self._entries: List[Dict[str, Any]] = []
        if self._manifest_path.exists():
            try:
                with open(self._manifest_path) as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._entries = []
        else:
            self._save_manifest()

    def _save_manifest(self) -> None:
        with open(self._manifest_path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    @staticmethod
    def _file_hash(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def register(
        self,
        filepath: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a file in the central index.

        Copies the file into the managed store and adds it to the manifest.
        If the file (by content hash) is already registered, returns the
        existing entry without duplicating.
        """
        src = Path(filepath)
        file_hash = self._file_hash(filepath)

        existing = self.lookup(file_hash)
        if existing is not None:
            return existing

        stored_name = f"{file_hash}_{src.name}"
        dest = self._files_dir / stored_name
        shutil.copy2(str(src), str(dest))

        entry = {
            "file_hash": file_hash,
            "original_name": src.name,
            "original_path": str(src),
            "stored_name": stored_name,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "size_bytes": src.stat().st_size,
            **(metadata or {}),
        }
        self._entries.append(entry)
        self._save_manifest()

        logger.info("Registered %s as %s", src.name, file_hash)
        return entry

    def list_entries(self) -> List[Dict[str, Any]]:
        """Return all index entries."""
        return list(self._entries)

    def lookup(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Find an entry by file hash."""
        for e in self._entries:
            if e.get("file_hash") == file_hash:
                return e
        return None

    def get_stored_path(self, file_hash: str) -> Optional[Path]:
        """Return the absolute path to the stored copy of a file."""
        entry = self.lookup(file_hash)
        if entry is None:
            return None
        p = self._files_dir / entry["stored_name"]
        return p if p.exists() else None
