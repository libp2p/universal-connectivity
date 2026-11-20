"""
File sharing endpoints (Bitswap / MerkleDag).

GET  /api/v1/files/shared          - list files this node has shared
GET  /api/v1/files/shared/{cid}    - metadata for a specific shared file
POST /api/v1/files/share           - share a local file to a topic
POST /api/v1/files/download        - download a file by CID hex
POST /api/v1/files/upload          - upload via multipart and share to a topic
"""

import asyncio

from app.services.files import is_within as _is_within  # noqa: F401  # re-exported for tests

from .base import BaseHandler, parse_string_field

# Cap an individual upload. Tornado still has a global body limit, but this
# keeps the in-memory multipart buffer and the on-disk write bounded.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class SharedFilesHandler(BaseHandler):
    """GET /api/v1/files/shared"""

    def get(self) -> None:
        if not self.require_ready():
            return
        files = self.file_service.shared_files()
        self.send_success({"shared_files": files, "count": len(files)})


class SharedFileDetailHandler(BaseHandler):
    """GET /api/v1/files/shared/{cid}"""

    def get(self, cid: str) -> None:
        if not self.require_ready():
            return
        self.send_success(self.file_service.shared_file(cid))


class ShareFileHandler(BaseHandler):
    """POST /api/v1/files/share — share a file that already exists on disk"""

    def post(self) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            file_path = parse_string_field(body, "file_path", required=True)
            topic = parse_string_field(body, "topic", required=True)
        except ValueError as e:
            self.send_error_response(str(e))
            return
        # Remote callers may only share files inside the download directory;
        # the service enforces the same boundary.
        self.send_success(
            self.file_service.share_local_file(file_path, topic),
            status=202,
        )


class DownloadFileHandler(BaseHandler):
    """POST /api/v1/files/download — download a file by CID hex"""

    def post(self) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            cid = parse_string_field(body, "file_cid", required=True)
            name = parse_string_field(body, "file_name", default="unknown")
        except ValueError as e:
            self.send_error_response(str(e))
            return
        self.send_success(self.file_service.download(cid, name), status=202)


class UploadAndShareHandler(BaseHandler):
    """
    POST /api/v1/files/upload
    Accepts multipart/form-data with fields:
      - file   : the file bytes
      - topic  : the topic to share to
    Saves the file to the service's download_dir and queues a share.
    """

    async def post(self) -> None:
        if not self.require_ready():
            return

        topic = self.get_argument("topic", "").strip()
        if not topic:
            self.send_error_response("'topic' form field is required.")
            return

        if "file" not in self.request.files:
            self.send_error_response("'file' form-data field is required.")
            return

        # Validate the topic before writing anything to disk.
        if topic not in self.messaging_service.subscribed_topics():
            self.send_error_response(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST /api/v1/topics.",
                status=400,
            )
            return

        file_info = self.request.files["file"][0]
        file_data = file_info["body"]
        if len(file_data) > MAX_UPLOAD_BYTES:
            self.send_error_response(
                f"Upload is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
                status=413,
            )
            return

        # Offload the write: a synchronous multi-megabyte write would block
        # every API/WebSocket client on the single Tornado IOLoop thread. The
        # service sanitises the attacker-controlled multipart filename.
        stored = await asyncio.to_thread(
            lambda: self.file_service.store_upload(
                file_info["filename"],
                file_data,
            )
        )
        self.file_service.share_local_file(stored["path"], topic)
        self.send_success(
            {
                "message": "File uploaded and share request queued",
                "filename": stored["filename"],
                "size": stored["size"],
                "topic": topic,
            },
            status=202,
        )
