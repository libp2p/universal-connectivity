"""Bitswap-backed file sharing: shared state, queueing, and workers."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from queue import Empty, Full
from typing import Any

import trio

from ..constants import FILE_MESSAGE_PREFIX
from ..errors import NotReadyError, NotFoundError, OperationError, ValidationError

logger = logging.getLogger("app.services.files")


def is_within(path: str, directory: str) -> bool:
    """True when ``path`` resolves inside ``directory`` (symlinks followed)."""
    try:
        path_real = os.path.realpath(path)
        dir_real = os.path.realpath(directory)
        return os.path.commonpath([dir_real, path_real]) == dir_real
    except (OSError, ValueError):
        return False


def _write_bytes(path: str, data: bytes) -> None:
    """Blocking file write, called from a worker thread when possible."""
    with open(path, "wb") as f:
        f.write(data)


class FileService:
    """Share and download files; owns the shared-file registry."""

    def __init__(self, engine: Any, notifications: Any = None) -> None:
        self._engine = engine
        self._notifications = notifications
        self._shared: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def download_dir(self) -> str:
        return self._engine.download_dir

    # ------------------------------------------------------------------ #
    #  Shared-file registry
    # ------------------------------------------------------------------ #
    def mark_shared(self, cid: str, metadata: dict[str, Any]) -> None:
        with self._lock:
            self._shared[cid] = metadata

    def shared_files(self) -> list[dict[str, Any]]:
        """Snapshot shared-file metadata without exposing local paths."""
        with self._lock:
            return [
                {
                    "cid": cid,
                    "filename": meta.get("filename"),
                    "filesize": meta.get("filesize"),
                }
                for cid, meta in self._shared.items()
            ]

    def shared_file(self, cid: str) -> dict[str, Any]:
        meta = self.shared_file_raw(cid)
        if not meta:
            raise NotFoundError(f"No shared file with CID '{cid}'.")
        return meta

    def shared_file_raw(self, cid: str) -> dict[str, Any] | None:
        """Return one serialized shared-file entry, or None."""
        with self._lock:
            meta = self._shared.get(cid)
            if not meta:
                return None
            return {
                "cid": cid,
                "filename": meta.get("filename"),
                "filesize": meta.get("filesize"),
            }

    # ------------------------------------------------------------------ #
    #  Adapter-facing operations
    # ------------------------------------------------------------------ #
    def share_local_file(
        self,
        file_path: str,
        topic: str,
        *,
        allow_outside_download_dir: bool = False,
    ) -> dict[str, Any]:
        """Queue a share for a file that already exists on disk.

        Remote/HTTP callers must not be able to publish arbitrary host files, so
        the file must live inside the download directory unless the caller is a
        trusted local adapter that explicitly opts out.
        """
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a file share.")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValidationError("'file_path' field is required.")
        if not isinstance(topic, str) or not topic.strip():
            raise ValidationError("'topic' field is required.")
        path = os.path.expanduser(file_path.strip())
        if not os.path.isfile(path):
            raise ValidationError(f"File not found: {path}")
        if not allow_outside_download_dir and not is_within(
            path, self.download_dir
        ):
            raise ValidationError(
                "'file_path' must be inside the peer's download directory."
            )
        chat_room = getattr(self._engine, "chat_room", None)
        subscribed = (
            set(chat_room.get_subscribed_topics()) if chat_room else set()
        )
        if topic not in subscribed:
            raise ValidationError(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST "
                "/api/v1/topics."
            )
        if not self.queue_share(path, topic):
            raise OperationError("Failed to queue file share.")
        return {
            "message": "File share request queued",
            "filename": os.path.basename(path),
            "topic": topic,
        }

    def download(
        self, cid: str, file_name: str = "unknown"
    ) -> dict[str, Any]:
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a download.")
        if not isinstance(cid, str) or not cid.strip():
            raise ValidationError("'file_cid' field is required.")
        cid = cid.strip()
        try:
            cid_bytes = bytes.fromhex(cid)
        except ValueError as exc:
            raise ValidationError(
                "'file_cid' must be a hexadecimal CID."
            ) from exc
        if not cid_bytes:
            raise ValidationError("'file_cid' must be a hexadecimal CID.")
        cid = cid_bytes.hex()
        name = (file_name or "unknown").strip() or "unknown"
        if not self.queue_download(cid, name):
            raise OperationError("Failed to queue download.")
        return {
            "message": "Download request queued",
            "file_cid": cid,
            "file_name": name,
        }

    def store_upload(self, filename: str, data: bytes) -> dict[str, Any]:
        """Persist uploaded bytes inside the download directory."""
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot store an upload.")
        name = os.path.basename(filename or "upload").strip()
        if name in ("", ".", ".."):
            name = "upload"
        directory = self.download_dir
        os.makedirs(directory, exist_ok=True)
        save_path = os.path.join(directory, name)
        base, ext = os.path.splitext(name)
        counter = 1
        while os.path.exists(save_path):
            save_path = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        if not is_within(save_path, directory):
            raise ValidationError("Invalid upload filename.")
        with open(save_path, "wb") as handle:
            handle.write(data)
        return {
            "path": save_path,
            "filename": os.path.basename(save_path),
            "size": len(data),
        }

    # ------------------------------------------------------------------ #
    #  Queueing (thread-safe)
    # ------------------------------------------------------------------ #
    def queue_share(self, file_path: str, topic: str) -> bool:
        engine = self._engine
        queue = getattr(engine, "file_share_queue", None)
        if not getattr(engine, "running", False) or queue is None:
            logger.warning("Cannot share file: service not ready")
            return False
        try:
            queue.sync_q.put_nowait(
                {
                    "file_path": file_path,
                    "topic": topic,
                    "timestamp": time.time(),
                }
            )
            logger.info(f"Queued file share request: {file_path} -> {topic}")
            return True
        except Full:
            logger.warning("File share queue is full; dropping request")
            return False
        except Exception as e:
            logger.error(f"Failed to queue file share: {e}")
            return False

    def queue_download(self, file_cid: str, file_name: str = "unknown") -> bool:
        engine = self._engine
        queue = getattr(engine, "file_download_queue", None)
        if not getattr(engine, "running", False) or queue is None:
            logger.warning("Cannot download file: service not ready")
            return False
        try:
            queue.sync_q.put_nowait(
                {
                    "file_cid": file_cid,
                    "file_name": file_name,
                    "timestamp": time.time(),
                }
            )
            logger.info(
                f"Queued file download request: {file_name} "
                f"(CID: {str(file_cid)[:16]}...)"
            )
            return True
        except Full:
            logger.warning("File download queue is full; dropping request")
            return False
        except Exception as e:
            logger.error(f"Failed to queue file download: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Workers
    # ------------------------------------------------------------------ #
    async def process_file_shares(self) -> None:
        """Process file sharing requests from adapters."""
        engine = self._engine
        while getattr(engine, "running", False):
            queue = getattr(engine, "file_share_queue", None)
            if queue is None:
                await trio.sleep(0.1)
                continue
            try:
                try:
                    share_data = queue.sync_q.get_nowait()
                    if share_data:
                        file_path = share_data.get("file_path")
                        topic = share_data.get("topic")

                        if not file_path or not os.path.exists(file_path):
                            logger.error(f"File not found: {file_path}")
                            await self._system(f"File not found: {file_path}")
                            continue

                        filename = os.path.basename(file_path)
                        filesize = os.path.getsize(file_path)

                        logger.info(
                            f"📁 Sharing file: {filename} ({filesize} bytes)"
                        )
                        await self._system(f"Preparing to share: {filename}...")

                        try:
                            root_cid = await engine.merkle_dag.add_file(
                                file_path, wrap_with_directory=True
                            )
                            cid_hex = root_cid.hex()

                            # filepath stays server-side; the API only returns
                            # filename/size.
                            self.mark_shared(
                                cid_hex,
                                {
                                    "filename": filename,
                                    "filesize": filesize,
                                    "filepath": file_path,
                                },
                            )

                            logger.info(
                                f"✅ File added to DAG. CID: {cid_hex}"
                            )

                            file_meta = {
                                "cid": cid_hex,
                                "filename": filename,
                                "filesize": filesize,
                            }
                            file_message = (
                                f"{FILE_MESSAGE_PREFIX}{json.dumps(file_meta)}"
                            )

                            if topic and engine.chat_room:
                                success = await engine.chat_room.publish_to_topic(
                                    topic, file_message
                                )
                                if success:
                                    logger.info(
                                        f"✅ File shared to topic '{topic}': "
                                        f"{filename}"
                                    )
                                    # Don't store the message here - the pubsub
                                    # echo stores it. Notify the UI immediately
                                    # so it shows the bubble.
                                    self._message(
                                        {
                                            "type": "file_shared",
                                            "topic": topic,
                                            "file_cid": cid_hex,
                                            "file_name": filename,
                                            "file_size": filesize,
                                            "sender_nick": "You",
                                            "sender_id": "self",
                                            "timestamp": time.time(),
                                        }
                                    )
                                else:
                                    await self._system(
                                        "Failed to share file to topic"
                                    )
                            else:
                                await self._system(
                                    "No topic specified for file sharing"
                                )

                        except Exception as e:
                            logger.error(f"Failed to share file: {e}")
                            logger.exception("Full traceback:")
                            await self._system(f"Failed to share file: {str(e)}")

                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing file share: {e}")
                    await trio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in file share processing: {e}")
                await trio.sleep(0.1)

    async def process_file_downloads(self) -> None:
        """Process file download requests from adapters."""
        engine = self._engine
        while getattr(engine, "running", False):
            queue = getattr(engine, "file_download_queue", None)
            if queue is None:
                await trio.sleep(0.1)
                continue
            try:
                try:
                    download_data = queue.sync_q.get_nowait()
                    if download_data:
                        cid_hex = download_data.get("file_cid")
                        filename = download_data.get("file_name", "unknown")

                        if not cid_hex:
                            logger.error("No CID provided for download")
                            continue

                        logger.info(
                            f"📥 Downloading file: {filename} (CID: {cid_hex})"
                        )
                        await self._system(f"Downloading: {filename}...")

                        try:
                            root_cid = bytes.fromhex(cid_hex)
                            file_data, extracted_filename = (
                                await engine.merkle_dag.fetch_file(
                                    root_cid, timeout=60.0
                                )
                            )

                            # Both names are attacker-controlled (the filename
                            # travels inside the pubsub message), so strip path
                            # components before joining.
                            save_filename = os.path.basename(
                                extracted_filename or filename
                            ).strip()
                            if save_filename in ("", ".", ".."):
                                save_filename = "download"

                            os.makedirs(self.download_dir, exist_ok=True)
                            save_path = os.path.join(
                                self.download_dir, save_filename
                            )
                            download_root = os.path.realpath(self.download_dir)
                            if (
                                os.path.commonpath(
                                    [
                                        download_root,
                                        os.path.realpath(save_path),
                                    ]
                                )
                                != download_root
                            ):
                                raise ValueError(
                                    "Refusing to write outside the download "
                                    "directory"
                                )
                            if os.path.exists(save_path):
                                name, ext = os.path.splitext(save_filename)
                                counter = 1
                                while os.path.exists(save_path):
                                    save_path = os.path.join(
                                        self.download_dir,
                                        f"{name}_{counter}{ext}",
                                    )
                                    counter += 1

                            # Large downloads must not stall pubsub/DHT.
                            await trio.to_thread.run_sync(
                                _write_bytes, save_path, file_data
                            )

                            logger.info(
                                f"✅ File downloaded: {save_path} "
                                f"({len(file_data)} bytes)"
                            )

                            self._message(
                                {
                                    "type": "file_downloaded",
                                    "file_cid": cid_hex,
                                    "file_name": save_filename,
                                    "file_size": len(file_data),
                                    "save_path": save_path,
                                    "timestamp": time.time(),
                                }
                            )

                        except Exception as e:
                            logger.error(f"Failed to download file: {e}")
                            logger.exception("Full traceback:")
                            self._message(
                                {
                                    "type": "file_download_failed",
                                    "file_cid": cid_hex,
                                    "file_name": filename,
                                    "error": str(e),
                                    "timestamp": time.time(),
                                }
                            )

                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing file download: {e}")
                    await trio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in file download processing: {e}")
                await trio.sleep(0.1)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    async def _system(self, message: str) -> None:
        if self._notifications is not None:
            await self._notifications.system(message)

    def _message(self, payload: dict[str, Any]) -> None:
        if self._notifications is not None:
            self._notifications.message(payload)
