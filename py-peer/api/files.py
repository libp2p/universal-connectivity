"""
File sharing endpoints (Bitswap / MerkleDag).

GET  /api/v1/files/shared          - list files this node has shared
GET  /api/v1/files/shared/{cid}    - metadata for a specific shared file
POST /api/v1/files/share           - share a local file to a topic
POST /api/v1/files/download        - download a file by CID hex
POST /api/v1/files/upload          - upload via multipart and share to a topic
"""

import os
from .base import BaseHandler


class SharedFilesHandler(BaseHandler):
    """GET /api/v1/files/shared"""

    def get(self):
        if not self.require_ready():
            return
        files = [
            {"cid": cid, **meta}
            for cid, meta in self.service.shared_files.items()
        ]
        self.send_success({"shared_files": files, "count": len(files)})


class SharedFileDetailHandler(BaseHandler):
    """GET /api/v1/files/shared/{cid}"""

    def get(self, cid):
        if not self.require_ready():
            return
        meta = self.service.shared_files.get(cid)
        if not meta:
            self.send_error_response(f"No shared file with CID '{cid}'.", status=404)
            return
        self.send_success({"cid": cid, **meta})


class ShareFileHandler(BaseHandler):
    """POST /api/v1/files/share — share a file that already exists on disk"""

    def post(self):
        if not self.require_ready():
            return
        body = self.get_json_body()
        file_path = body.get("file_path", "").strip()
        topic = body.get("topic", "").strip()

        if not file_path:
            self.send_error_response("'file_path' is required.")
            return
        if not topic:
            self.send_error_response("'topic' is required.")
            return
        if not os.path.exists(file_path):
            self.send_error_response(f"File not found: {file_path}", status=400)
            return

        subscribed = self.service.get_subscribed_topics()
        if topic not in subscribed:
            self.send_error_response(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST /api/v1/topics.",
                status=400,
            )
            return

        queued = self.service.share_file(file_path, topic)
        if queued:
            filename = os.path.basename(file_path)
            self.send_success(
                {"message": "File share request queued", "filename": filename, "topic": topic},
                status=202,
            )
        else:
            self.send_error_response("Failed to queue file share — service not ready.", status=503)


class DownloadFileHandler(BaseHandler):
    """POST /api/v1/files/download — download a file by CID hex"""

    def post(self):
        if not self.require_ready():
            return
        body = self.get_json_body()
        cid = body.get("file_cid", "").strip()
        name = body.get("file_name", "unknown").strip()

        if not cid:
            self.send_error_response("'file_cid' is required.")
            return

        queued = self.service.download_file(cid, name)
        if queued:
            self.send_success(
                {"message": "Download request queued", "file_cid": cid, "file_name": name},
                status=202,
            )
        else:
            self.send_error_response("Failed to queue download — service not ready.", status=503)


class UploadAndShareHandler(BaseHandler):
    """
    POST /api/v1/files/upload
    Accepts multipart/form-data with fields:
      - file   : the file bytes
      - topic  : the topic to share to
    Saves the file to the service's download_dir and queues a share.
    """

    def post(self):
        if not self.require_ready():
            return

        topic = self.get_argument("topic", "").strip()
        if not topic:
            self.send_error_response("'topic' form field is required.")
            return

        if "file" not in self.request.files:
            self.send_error_response("'file' form-data field is required.")
            return

        file_info = self.request.files["file"][0]
        filename = file_info["filename"] or "upload"
        file_data = file_info["body"]

        # Save to download_dir
        save_path = os.path.join(self.service.download_dir, filename)
        # Handle name collisions
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(save_path):
            save_path = os.path.join(self.service.download_dir, f"{base}_{counter}{ext}")
            counter += 1

        with open(save_path, "wb") as f:
            f.write(file_data)

        subscribed = self.service.get_subscribed_topics()
        if topic not in subscribed:
            self.send_error_response(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST /api/v1/topics.",
                status=400,
            )
            return

        queued = self.service.share_file(save_path, topic)
        if queued:
            self.send_success(
                {
                    "message": "File uploaded and share request queued",
                    "filename": os.path.basename(save_path),
                    "size": len(file_data),
                    "topic": topic,
                    "saved_path": save_path,
                },
                status=202,
            )
        else:
            self.send_error_response("Failed to queue file share — service not ready.", status=503)
