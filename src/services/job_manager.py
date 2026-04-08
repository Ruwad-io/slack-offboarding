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

HEARTBEAT_INTERVAL = 15  # seconds between SSE heartbeat comments


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
        pipe = self.redis.pipeline()
        pipe.setex(self._key(job_id), self.EXPIRY, json.dumps(state))
        pipe.setex(f"{self._key(job_id)}:token", self.EXPIRY, token)
        pipe.execute()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        """Get job state."""
        data = self.redis.get(self._key(job_id))
        if data:
            return json.loads(data)
        return None

    def update_job(self, job_id: str, **kwargs):
        """Atomically update job fields using Redis WATCH/MULTI."""
        key = self._key(job_id)
        for _ in range(3):  # retry on contention
            try:
                self.redis.watch(key)
                data = self.redis.get(key)
                if not data:
                    self.redis.unwatch()
                    return
                job = json.loads(data)
                job.update(kwargs)
                pipe = self.redis.pipeline()
                pipe.setex(key, self.EXPIRY, json.dumps(job))
                pipe.execute()
                return
            except Exception:
                continue
        # Fallback: non-atomic update
        data = self.redis.get(key)
        if data:
            job = json.loads(data)
            job.update(kwargs)
            self.redis.setex(key, self.EXPIRY, json.dumps(job))

    def increment_job(self, job_id: str, **increments):
        """Atomically increment numeric job fields."""
        key = self._key(job_id)
        for _ in range(3):
            try:
                self.redis.watch(key)
                data = self.redis.get(key)
                if not data:
                    self.redis.unwatch()
                    return
                job = json.loads(data)
                for field, delta in increments.items():
                    job[field] = job.get(field, 0) + delta
                pipe = self.redis.pipeline()
                pipe.setex(key, self.EXPIRY, json.dumps(job))
                pipe.execute()
                return
            except Exception:
                continue

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
        last_heartbeat = time.time()
        while True:
            try:
                job = self.get_job(job_id)
            except Exception:
                yield ": heartbeat\n\n"
                time.sleep(2)
                continue

            if not job:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                return

            yield f"data: {json.dumps(job)}\n\n"

            if job["status"] in ("completed", "failed"):
                return

            time.sleep(1)

            # Send heartbeat to keep connection alive
            now = time.time()
            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat = now


def run_cleanup_job(job_manager: JobManager, job_id: str):
    """Execute a cleanup job in a background thread using shared nuke_all()."""
    from src.services.slack_cleaner import SlackCleaner

    token = job_manager.get_token(job_id)
    if not token:
        job_manager.update_job(job_id, status="failed", errors=["Token not found"])
        return

    job_manager.update_job(job_id, status="running")

    try:
        cleaner = SlackCleaner(token)

        def on_conversation_start(conv, total):
            job_manager.update_job(
                job_id,
                conversations_total=total,
                current_conversation=conv.get("user_name", "?"),
            )

        def on_conversation_done(conv, stats):
            job_manager.update_job(
                job_id,
                conversations_done=stats.conversations_scanned,
                messages_found=stats.messages_found,
                messages_deleted=stats.messages_deleted,
                messages_failed=stats.messages_failed,
            )

        cleaner.nuke_all(
            on_conversation_start=on_conversation_start,
            on_conversation_done=on_conversation_done,
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
