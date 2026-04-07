"""
Background job manager using Redis for state and threading for execution.
Supports SSE streaming of job progress.
"""

import json
import time
import uuid
import threading
import logging
from redis import Redis

logger = logging.getLogger(__name__)


class JobManager:
    """Manages background cleanup jobs with Redis-backed state."""

    KEY_PREFIX = "offboarding:job:"
    EXPIRY = 86400  # jobs expire after 24h

    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"{self.KEY_PREFIX}{job_id}"

    def create_job(self, user_id: str, job_type: str, token: str) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())[:8]
        state = {
            "id": job_id,
            "user_id": user_id,
            "type": job_type,
            "status": "pending",
            "conversations_total": 0,
            "conversations_done": 0,
            "messages_found": 0,
            "messages_deleted": 0,
            "messages_failed": 0,
            "current_conversation": "",
            "errors": [],
            "created_at": time.time(),
        }
        self.redis.setex(self._key(job_id), self.EXPIRY, json.dumps(state))
        # Store token separately (shorter expiry, same lifecycle)
        self.redis.setex(f"{self._key(job_id)}:token", self.EXPIRY, token)
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        """Get job state."""
        data = self.redis.get(self._key(job_id))
        if data:
            return json.loads(data)
        return None

    def update_job(self, job_id: str, **kwargs):
        """Update job fields."""
        job = self.get_job(job_id)
        if job:
            job.update(kwargs)
            self.redis.setex(self._key(job_id), self.EXPIRY, json.dumps(job))

    def get_token(self, job_id: str) -> str | None:
        """Get the Slack token for a job."""
        return self.redis.get(f"{self._key(job_id)}:token")

    def get_active_job(self, user_id: str) -> dict | None:
        """Get the active (running/pending) job for a user, if any."""
        for key in self.redis.scan_iter(f"{self.KEY_PREFIX}*"):
            if key.endswith(":token"):
                continue
            data = self.redis.get(key)
            if data:
                job = json.loads(data)
                if job.get("user_id") == user_id and job.get("status") in ("pending", "running"):
                    return job
        return None

    def stream_progress(self, job_id: str):
        """Generator that yields SSE events until the job completes."""
        while True:
            job = self.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                return

            yield f"data: {json.dumps(job)}\n\n"

            if job["status"] in ("completed", "failed"):
                return

            time.sleep(1)


def run_cleanup_job(job_manager: JobManager, job_id: str):
    """Execute a cleanup job in a background thread."""
    from src.services.slack_cleaner import SlackCleaner

    token = job_manager.get_token(job_id)
    if not token:
        job_manager.update_job(job_id, status="failed", errors=["Token not found"])
        return

    job_manager.update_job(job_id, status="running")

    try:
        cleaner = SlackCleaner(token)
        job = job_manager.get_job(job_id)
        job_type = job.get("type", "nuke")

        if job_type == "nuke":
            conversations = cleaner.list_all_conversations()
        else:
            conversations = cleaner.list_dm_conversations()

        job_manager.update_job(job_id, conversations_total=len(conversations))

        admin_mode = cleaner.can_delete_others

        for conv in conversations:
            job_manager.update_job(
                job_id,
                current_conversation=conv.get("user_name", conv.get("name", "?")),
            )

            # In admin mode, delete ALL messages in DMs
            if admin_mode and conv.get("type") == "dm":
                messages = cleaner.get_all_messages(conv["id"])
            else:
                messages = cleaner.get_my_messages(conv["id"])

            if messages:
                job_manager.update_job(
                    job_id,
                    messages_found=job_manager.get_job(job_id)["messages_found"] + len(messages),
                )

                def on_progress(stats, _jid=job_id):
                    current = job_manager.get_job(_jid)
                    job_manager.update_job(
                        _jid,
                        messages_deleted=current["messages_deleted"]
                        - current.get("_last_deleted", 0)
                        + stats.messages_deleted,
                        messages_failed=current["messages_failed"]
                        - current.get("_last_failed", 0)
                        + stats.messages_failed,
                    )

                result = cleaner.delete_messages(
                    conv["id"], messages=messages, on_progress=None
                )

                current = job_manager.get_job(job_id)
                job_manager.update_job(
                    job_id,
                    messages_deleted=current["messages_deleted"] + result.messages_deleted,
                    messages_failed=current["messages_failed"] + result.messages_failed,
                )

            current = job_manager.get_job(job_id)
            job_manager.update_job(
                job_id,
                conversations_done=current["conversations_done"] + 1,
            )

        job_manager.update_job(job_id, status="completed", current_conversation="")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        job_manager.update_job(job_id, status="failed", errors=[str(e)])


def start_cleanup_job(job_manager: JobManager, job_id: str):
    """Start a cleanup job in a background thread."""
    thread = threading.Thread(
        target=run_cleanup_job,
        args=(job_manager, job_id),
        daemon=True,
    )
    thread.start()
    return thread
