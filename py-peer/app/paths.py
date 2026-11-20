"""Data-directory resolution and writability preflight.

Everything the peer writes down lives under one root so it can be backed up,
moved, or deleted as a unit instead of leaking into the current working
directory:

    <root>/identity/peer.key       private peer identity (mode 0600)
    <root>/history.db              SQLite message history
    <root>/logs/system_messages.txt rotating system log

The root is chosen once, at startup, with a documented precedence:

1. ``--data-dir`` on the command line
2. ``UC_DATA_DIR`` in the environment
3. the platform data directory (macOS: ``~/Library/Application Support``,
   Linux: ``$XDG_DATA_HOME``, Windows: ``%LOCALAPPDATA%``)

Relative values resolve against the current working directory. This module is
pure bookkeeping: it creates directories and probes writability, but never
opens the database or writes application data.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Mapping

from platformdirs import user_data_dir

from .errors import DataDirectoryError

logger = logging.getLogger("app.paths")

ENV_DATA_DIR = "UC_DATA_DIR"
APP_NAME = "py-peer"
APP_AUTHOR = "universal-connectivity"

IDENTITY_DIRNAME = "identity"
IDENTITY_FILENAME = "peer.key"
LOG_DIRNAME = "logs"
SYSTEM_LOG_FILENAME = "system_messages.txt"
DATABASE_FILENAME = "history.db"

SOURCE_FLAG = "flag"
SOURCE_ENV = "env"
SOURCE_PLATFORM = "platformdirs"


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_path(value: str | os.PathLike[str]) -> Path:
    """Expand ``~`` and anchor relative paths at the current directory."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


@dataclass(frozen=True)
class DataPaths:
    """Concrete locations under one data root."""

    root: Path
    source: str
    identity_file: Path
    system_log_file: Path
    database_file: Path
    database_in_memory: bool = False

    @classmethod
    def resolve(
        cls,
        *,
        data_dir: str | os.PathLike[str] | None = None,
        storage_path: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "DataPaths":
        """Decide where this process stores its files.

        Passing ``storage_path`` keeps an explicit database location (Phase 3
        flag) while still deriving the identity and log locations from the
        data root. ``storage_path=":memory:"`` is preserved verbatim.
        """
        environment = os.environ if env is None else env

        source = SOURCE_FLAG
        root_value = _first_non_empty(_as_text(data_dir))
        if root_value is None:
            root_value = _first_non_empty(environment.get(ENV_DATA_DIR))
            source = SOURCE_ENV
        if root_value is None:
            root_value = user_data_dir(APP_NAME, APP_AUTHOR)
            source = SOURCE_PLATFORM

        root = _resolve_path(root_value)
        database_value = _as_text(storage_path)
        in_memory = database_value == ":memory:"
        if in_memory:
            database_file = root / DATABASE_FILENAME
        elif database_value:
            database_file = _resolve_path(database_value)
        else:
            database_file = root / DATABASE_FILENAME

        return cls(
            root=root,
            source=source,
            identity_file=root / IDENTITY_DIRNAME / IDENTITY_FILENAME,
            system_log_file=root / LOG_DIRNAME / SYSTEM_LOG_FILENAME,
            database_file=database_file,
            database_in_memory=in_memory,
        )

    # ------------------------------------------------------------------ #
    #  Filesystem
    # ------------------------------------------------------------------ #
    def directories(self) -> list[Path]:
        """Unique directories that must exist and be writable."""
        candidates = [
            self.root,
            self.identity_file.parent,
            self.system_log_file.parent,
        ]
        if not self.database_in_memory:
            candidates.append(self.database_file.parent)
        unique: list[Path] = []
        for directory in candidates:
            if directory not in unique:
                unique.append(directory)
        return unique

    def ensure_writable(self) -> "DataPaths":
        """Create the layout and prove we can write to it.

        Raises ``DataDirectoryError`` with an actionable message instead of
        letting a later SQLite/key write fail in the middle of startup.
        """
        for directory in self.directories():
            mode = 0o700 if directory == self.identity_file.parent else 0o755
            try:
                directory.mkdir(parents=True, exist_ok=True, mode=mode)
            except OSError as exc:
                raise DataDirectoryError(_unwritable_message(directory, exc)) from exc
            _probe(directory)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "source": self.source,
            "identity_file": str(self.identity_file),
            "database_file": ":memory:"
            if self.database_in_memory
            else str(self.database_file),
            "system_log_file": str(self.system_log_file),
        }


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    return os.fspath(value)


def _unwritable_message(directory: Path, exc: OSError) -> str:
    reason = exc.strerror or str(exc)
    return (
        f"Data directory is not writable: {directory} ({reason}). "
        f"Set {ENV_DATA_DIR} or pass --data-dir with a writable location."
    )


def _probe(directory: Path) -> None:
    """Write and remove a probe file so permissions fail here, not mid-run."""
    probe = directory / f".uc-write-test-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        with open(probe, "wb") as handle:
            handle.write(b"ok")
        probe.unlink()
    except OSError as exc:
        try:
            probe.unlink()
        except OSError:  # pragma: no cover - probe was never created
            pass
        raise DataDirectoryError(_unwritable_message(directory, exc)) from exc


__all__ = [
    "APP_NAME",
    "APP_AUTHOR",
    "DATABASE_FILENAME",
    "DataPaths",
    "ENV_DATA_DIR",
    "IDENTITY_FILENAME",
    "SYSTEM_LOG_FILENAME",
]
