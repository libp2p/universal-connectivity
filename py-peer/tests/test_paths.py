"""Tests for data-directory resolution, identity persistence, and log location."""

import logging
import os
import stat
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import ApplicationRuntime, DataDirectoryError, RuntimeConfig
from app.paths import (
    ENV_DATA_DIR,
    DataPaths,
)
from app.chatroom import configure_system_log, system_logger


class _TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        configure_system_log(None)
        self._tmp.cleanup()


class DataPathsTests(_TempDirTest):
    def test_flag_wins_over_environment(self):
        paths = DataPaths.resolve(
            data_dir=os.path.join(self.tmp, "flag"),
            env={ENV_DATA_DIR: os.path.join(self.tmp, "env")},
        )
        self.assertEqual(paths.source, "flag")
        self.assertEqual(paths.root, Path(self.tmp) / "flag")

    def test_environment_used_when_no_flag(self):
        paths = DataPaths.resolve(env={ENV_DATA_DIR: self.tmp})
        self.assertEqual(paths.source, "env")
        self.assertEqual(paths.root, Path(self.tmp))

    def test_platform_default_when_nothing_is_set(self):
        paths = DataPaths.resolve(env={})
        self.assertEqual(paths.source, "platformdirs")
        self.assertTrue(paths.root.is_absolute())
        self.assertIn("py-peer", str(paths.root))

    def test_blank_values_fall_through(self):
        paths = DataPaths.resolve(data_dir="  ", env={ENV_DATA_DIR: self.tmp})
        self.assertEqual(paths.source, "env")

    def test_relative_path_is_anchored_at_cwd(self):
        paths = DataPaths.resolve(data_dir="relative-data", env={})
        self.assertEqual(paths.root, Path.cwd() / "relative-data")

    def test_tilde_is_expanded(self):
        paths = DataPaths.resolve(data_dir="~/uc-test", env={})
        self.assertNotIn("~", str(paths.root))
        self.assertEqual(paths.root, Path.home() / "uc-test")

    def test_layout_is_under_one_root(self):
        paths = DataPaths.resolve(data_dir=self.tmp, env={})
        self.assertEqual(paths.identity_file, Path(self.tmp) / "identity" / "peer.key")
        self.assertEqual(paths.database_file, Path(self.tmp) / "history.db")
        self.assertEqual(
            paths.system_log_file, Path(self.tmp) / "logs" / "system_messages.txt"
        )

    def test_explicit_storage_path_overrides_database_location(self):
        database = os.path.join(self.tmp, "elsewhere", "chat.db")
        paths = DataPaths.resolve(data_dir=self.tmp, storage_path=database, env={})
        self.assertEqual(paths.database_file, Path(database))
        self.assertEqual(paths.identity_file, Path(self.tmp) / "identity" / "peer.key")
        self.assertFalse(paths.database_in_memory)

    def test_memory_storage_does_not_probe_a_database_directory(self):
        paths = DataPaths.resolve(
            data_dir=self.tmp, storage_path=":memory:", env={}
        )
        self.assertTrue(paths.database_in_memory)
        self.assertEqual(paths.to_dict()["database_file"], ":memory:")
        self.assertNotIn(Path(":memory:"), paths.directories())

    def test_ensure_writable_creates_the_layout(self):
        paths = DataPaths.resolve(data_dir=self.tmp, env={}).ensure_writable()
        self.assertTrue(paths.root.is_dir())
        self.assertTrue(paths.identity_file.parent.is_dir())
        self.assertTrue(paths.system_log_file.parent.is_dir())

    def test_unwritable_directory_raises_actionable_error(self):
        if os.geteuid() == 0:  # pragma: no cover - root bypasses permissions
            self.skipTest("running as root; permission bits are not enforced")
        locked = os.path.join(self.tmp, "locked")
        os.makedirs(locked)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        try:
            with self.assertRaises(DataDirectoryError) as raised:
                DataPaths.resolve(data_dir=locked, env={}).ensure_writable()
            self.assertIn("not writable", raised.exception.message)
            self.assertIn(ENV_DATA_DIR, raised.exception.message)
        finally:
            os.chmod(locked, stat.S_IRWXU)

    def test_file_in_place_of_directory_raises_clear_error(self):
        blocker = os.path.join(self.tmp, "not-a-dir")
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("x")
        with self.assertRaises(DataDirectoryError) as raised:
            DataPaths.resolve(data_dir=blocker, env={}).ensure_writable()
        self.assertIn(blocker, raised.exception.message)


class IdentityPersistenceTests(_TempDirTest):
    """Identity rules: seed is explicit, otherwise one persisted random key."""

    def _service(self, **kwargs):
        from core.headless import HeadlessService

        kwargs.setdefault("ui_mode", True)
        return HeadlessService("tester", **kwargs)

    def _peer_id(self, key_pair):
        from libp2p.peer.id import ID

        return str(ID.from_pubkey(key_pair.public_key))

    def test_first_run_creates_a_persisted_identity(self):
        path = os.path.join(self.tmp, "identity", "peer.key")
        service = self._service(identity_path=path)
        key_pair = service._load_identity()

        self.assertEqual(service.identity_source, "created")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertTrue(self._peer_id(key_pair))

    def test_restart_reuses_the_same_peer_id(self):
        path = os.path.join(self.tmp, "identity", "peer.key")
        first = self._service(identity_path=path)._load_identity()
        second_service = self._service(identity_path=path)
        second = second_service._load_identity()

        self.assertEqual(second_service.identity_source, "persisted")
        self.assertEqual(self._peer_id(first), self._peer_id(second))

    def test_explicit_seed_is_deterministic_and_not_written(self):
        path = os.path.join(self.tmp, "identity", "peer.key")
        seeded = self._service(seed="phase4", identity_path=path)
        key_pair = seeded._load_identity()

        self.assertEqual(seeded.identity_source, "seed")
        self.assertFalse(os.path.exists(path))
        self.assertEqual(
            self._peer_id(key_pair),
            self._peer_id(self._service(seed="phase4")._load_identity()),
        )

    def test_explicit_seed_overrides_a_stored_identity(self):
        path = os.path.join(self.tmp, "identity", "peer.key")
        stored = self._service(identity_path=path)._load_identity()
        seeded = self._service(seed="other", identity_path=path)._load_identity()

        self.assertNotEqual(self._peer_id(stored), self._peer_id(seeded))

    def test_missing_identity_path_gives_an_ephemeral_key(self):
        first = self._service()
        second = self._service()
        first_key = first._load_identity()
        second_key = second._load_identity()

        self.assertEqual(first.identity_source, "ephemeral")
        self.assertNotEqual(self._peer_id(first_key), self._peer_id(second_key))

    def test_corrupt_identity_file_fails_instead_of_regenerating(self):
        path = os.path.join(self.tmp, "identity", "peer.key")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as handle:
            handle.write(b"not a key")

        with self.assertRaises(RuntimeError) as raised:
            self._service(identity_path=path)._load_identity()
        self.assertIn("unreadable", str(raised.exception))
        self.assertIn(path, str(raised.exception))


class SystemLogTests(_TempDirTest):
    def _rotating_handlers(self):
        return [
            handler
            for handler in system_logger.handlers
            if isinstance(handler, RotatingFileHandler)
        ]

    def test_import_does_not_create_a_cwd_log(self):
        # The handler is attached at startup, never at import time.
        configure_system_log(None)
        self.assertEqual(self._rotating_handlers(), [])

    def test_configure_writes_into_the_data_directory(self):
        path = os.path.join(self.tmp, "logs", "system_messages.txt")
        active = configure_system_log(path)

        self.assertEqual(active, os.path.abspath(path))
        system_logger.info("phase four log line")
        for handler in self._rotating_handlers():
            handler.flush()

        with open(path, encoding="utf-8") as handle:
            self.assertIn("phase four log line", handle.read())

    def test_configure_is_idempotent(self):
        path = os.path.join(self.tmp, "logs", "system_messages.txt")
        configure_system_log(path)
        configure_system_log(path)
        self.assertEqual(len(self._rotating_handlers()), 1)

    def test_configure_accepts_none_to_disable(self):
        path = os.path.join(self.tmp, "logs", "system_messages.txt")
        configure_system_log(path)
        self.assertIsNone(configure_system_log(None))
        self.assertEqual(self._rotating_handlers(), [])


class RuntimeDataDirectoryTests(_TempDirTest):
    def _runtime(self, **config_kwargs):
        config_kwargs.setdefault("nickname", "path-test")
        config_kwargs.setdefault("data_dir", self.tmp)
        return ApplicationRuntime(RuntimeConfig(**config_kwargs))

    def test_default_database_lives_in_the_data_directory(self):
        runtime = self._runtime()
        self.addCleanup(runtime.store.close)

        self.assertEqual(runtime.paths.root, Path(self.tmp))
        self.assertEqual(runtime.store.backend, "sqlite")
        self.assertEqual(runtime.store.path, os.path.join(self.tmp, "history.db"))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "history.db")))

    def test_identity_path_is_injected_into_the_service(self):
        runtime = self._runtime()
        self.addCleanup(runtime.store.close)

        self.assertEqual(
            runtime.service.identity_path,
            os.path.join(self.tmp, "identity", "peer.key"),
        )
        snapshot = runtime.config_snapshot()
        self.assertEqual(snapshot["data_dir"], self.tmp)
        self.assertEqual(
            snapshot["identity_file"], os.path.join(self.tmp, "identity", "peer.key")
        )

    def test_system_log_is_configured_from_the_runtime(self):
        runtime = self._runtime()
        self.addCleanup(runtime.store.close)
        self.assertTrue(
            any(
                isinstance(handler, RotatingFileHandler)
                for handler in system_logger.handlers
            )
        )
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "logs")))

    def test_explicit_storage_path_still_uses_the_data_root_for_identity(self):
        database = os.path.join(self.tmp, "custom", "messages.db")
        runtime = self._runtime(storage_path=database)
        self.addCleanup(runtime.store.close)

        self.assertEqual(runtime.store.path, database)
        self.assertEqual(runtime.paths.root, Path(self.tmp))

    def test_memory_storage_keeps_identity_persistent(self):
        runtime = self._runtime(storage_path=":memory:")
        self.addCleanup(runtime.store.close)

        self.assertEqual(runtime.store.backend, "sqlite")
        self.assertEqual(runtime.store.path, ":memory:")
        self.assertEqual(
            runtime.service.identity_path,
            os.path.join(self.tmp, "identity", "peer.key"),
        )

    def test_unwritable_data_directory_fails_at_construction(self):
        if os.geteuid() == 0:  # pragma: no cover - root bypasses permissions
            self.skipTest("running as root; permission bits are not enforced")
        locked = os.path.join(self.tmp, "runtime-locked")
        os.makedirs(locked)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        try:
            with self.assertRaises(DataDirectoryError):
                ApplicationRuntime(
                    RuntimeConfig(nickname="path-test", data_dir=locked)
                )
        finally:
            os.chmod(locked, stat.S_IRWXU)

    def test_service_injection_does_not_require_a_data_directory(self):
        from app.storage import MemoryStore

        class _Service:
            nickname = "fake"
            port = 1234
            topic = None
            strict_signing = True
            download_dir = self.tmp
            transport_addrs = []
            full_multiaddrs = []
            connect_addrs = []
            message_store = MemoryStore()

        runtime = ApplicationRuntime(service=_Service())
        self.assertIsNone(runtime.paths)
        self.assertIsNone(runtime.config_snapshot()["data_dir"])


if __name__ == "__main__":
    unittest.main()
