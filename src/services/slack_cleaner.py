"""
Slack Cleaner Service
Handles all Slack API interactions for message deletion and offboarding tasks.
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


@dataclass
class CleanupStats:
    """Tracks cleanup progress and results."""

    conversations_scanned: int = 0
    messages_found: int = 0
    messages_deleted: int = 0
    messages_failed: int = 0
    errors: list = field(default_factory=list)

    @property
    def progress_pct(self) -> float:
        if self.messages_found == 0:
            return 100.0
        return round((self.messages_deleted + self.messages_failed) / self.messages_found * 100, 1)

    def to_dict(self) -> dict:
        return {
            "conversations_scanned": self.conversations_scanned,
            "messages_found": self.messages_found,
            "messages_deleted": self.messages_deleted,
            "messages_failed": self.messages_failed,
            "progress_pct": self.progress_pct,
            "errors": self.errors[-10:],  # last 10 errors
        }


class SlackCleaner:
    """Service to clean up a user's Slack messages."""

    INITIAL_DELETE_DELAY = 0.3  # start aggressive
    MAX_DELETE_DELAY = 2.0  # back off up to this
    MAX_WORKERS = 2
    MAX_DELETE_WORKERS = 3  # start with 3 concurrent deletions
    READ_DELAY = 0.8  # seconds between read API calls

    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self._user_id = None
        self._user_name = None
        self._user_cache = {}
        self._scopes = set()

    def _api_call_with_retry(self, api_method, **kwargs):
        """Call a Slack API method with automatic rate-limit retry."""
        last_error = None
        for attempt in range(5):
            try:
                return api_method(**kwargs)
            except SlackApiError as e:
                if e.response.get("error") == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    delay = retry_after * (1.5 ** attempt)
                    logger.debug(f"Rate limited, sleeping {delay:.0f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    last_error = e
                else:
                    raise
        raise SlackApiError("Rate limited after 5 retries", last_error.response)

    def _paginate(self, api_method, result_key, **kwargs):
        """Generic paginated API call. Returns all items across pages."""
        items = []
        cursor = None
        first = True
        while True:
            if cursor:
                kwargs["cursor"] = cursor
            if not first:
                time.sleep(self.READ_DELAY)
            resp = self._api_call_with_retry(api_method, **kwargs)
            items.extend(resp[result_key])
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            first = False
        return items

    @property
    def user_id(self) -> str:
        if not self._user_id:
            self._fetch_identity()
        return self._user_id

    @property
    def user_name(self) -> str:
        if not self._user_name:
            self._fetch_identity()
        return self._user_name

    @property
    def can_delete_others(self) -> bool:
        """Whether the token has admin scope to delete other users' messages."""
        if not self._scopes:
            self._fetch_identity()
        return "admin.conversations:write" in self._scopes

    def _fetch_identity(self):
        resp = self._api_call_with_retry(self.client.auth_test)
        self._user_id = resp["user_id"]
        self._user_name = resp["user"]
        # Scopes come back in the response headers
        scope_header = resp.headers.get("x-oauth-scopes", "")
        self._scopes = {s.strip() for s in scope_header.split(",") if s.strip()}

    def _prefetch_users(self):
        """Bulk-fetch all workspace users into cache."""
        if self._user_cache:
            return
        users = self._paginate(self.client.users_list, "members", limit=200)
        for u in users:
            name = u.get("real_name") or u.get("name") or u["id"]
            self._user_cache[u["id"]] = name

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def list_dm_conversations(self) -> list[dict]:
        """List all 1-to-1 DM conversations with user info."""
        self._prefetch_users()
        channels = self._paginate(self.client.conversations_list, "channels", types="im", limit=200)
        return [
            {
                "id": ch["id"],
                "user_id": ch.get("user", ""),
                "user_name": self._get_user_name(ch.get("user", "")),
                "type": "dm",
            }
            for ch in channels
        ]

    def list_group_dms(self) -> list[dict]:
        """List all multi-party DM (group DM) conversations."""
        channels = self._paginate(
            self.client.conversations_list, "channels", types="mpim", limit=200
        )
        return [
            {
                "id": ch["id"],
                "user_name": ch.get("name", "group-dm"),
                "purpose": ch.get("purpose", {}).get("value", ""),
                "type": "group_dm",
            }
            for ch in channels
        ]

    def list_channels(self) -> list[dict]:
        """List public/private channels the user is a member of."""
        channels = self._paginate(
            self.client.conversations_list,
            "channels",
            types="public_channel,private_channel",
            limit=200,
        )
        return [
            {
                "id": ch["id"],
                "user_name": f"#{ch.get('name', '')}",
                "is_private": ch.get("is_private", False),
                "num_members": ch.get("num_members", 0),
                "type": "channel",
            }
            for ch in channels
            if ch.get("is_member", False)
        ]

    def list_all_conversations(self) -> list[dict]:
        """List ALL conversations: DMs + group DMs + channels."""
        self._prefetch_users()
        dms = self.list_dm_conversations()
        group_dms = self.list_group_dms()
        channels = self.list_channels()
        return dms + group_dms + channels

    # ------------------------------------------------------------------
    # Message retrieval (includes thread replies)
    # ------------------------------------------------------------------

    def get_my_messages(self, channel_id: str, include_threads: bool = True) -> list[dict]:
        """Get all messages sent by the current user, including thread replies."""
        return self._get_messages(channel_id, include_threads=include_threads, only_mine=True)

    def get_all_messages(self, channel_id: str, include_threads: bool = True) -> list[dict]:
        """Get ALL messages in a conversation (requires admin scope for deletion)."""
        return self._get_messages(channel_id, include_threads=include_threads, only_mine=False)

    def _get_messages(
        self, channel_id: str, include_threads: bool = True, only_mine: bool = True
    ) -> list[dict]:
        """Get messages from a conversation, optionally filtering to current user only."""
        all_messages = []
        thread_parents = []
        cursor = None
        while True:
            kwargs = {"channel": channel_id, "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
                time.sleep(self.READ_DELAY)
            resp = self._api_call_with_retry(self.client.conversations_history, **kwargs)
            for m in resp["messages"]:
                if not only_mine or m.get("user") == self.user_id:
                    all_messages.append(m)
                if include_threads and m.get("reply_count", 0) > 0:
                    thread_parents.append(m["ts"])
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        # Fetch thread replies
        if include_threads and thread_parents:
            seen_ts = {m["ts"] for m in all_messages}
            for parent_ts in thread_parents:
                time.sleep(self.READ_DELAY)
                try:
                    replies = self._paginate(
                        self.client.conversations_replies,
                        "messages",
                        channel=channel_id,
                        ts=parent_ts,
                        limit=200,
                    )
                    for r in replies:
                        if r["ts"] not in seen_ts:
                            if not only_mine or r.get("user") == self.user_id:
                                all_messages.append(r)
                                seen_ts.add(r["ts"])
                except SlackApiError as e:
                    if e.response.get("error") != "thread_not_found":
                        logger.debug(f"Thread fetch failed: {e.response.get('error')}")

        return all_messages

    def count_my_messages(self, channel_id: str) -> int:
        """Count messages by current user in a conversation (including threads)."""
        return len(self.get_my_messages(channel_id))

    def count_my_messages_batch(
        self, channel_ids: list[str], on_each: callable = None
    ) -> dict[str, int]:
        """Count messages in multiple conversations concurrently."""
        results = {}

        def _count(cid):
            return cid, self.count_my_messages(cid)

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            futures = {pool.submit(_count, cid): cid for cid in channel_ids}
            for future in as_completed(futures):
                cid, count = future.result()
                results[cid] = count
                if on_each:
                    on_each(cid, count)

        return results

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_messages(
        self,
        channel_id: str,
        messages: list[dict] | None = None,
        dry_run: bool = False,
        on_progress: callable = None,
    ) -> CleanupStats:
        """Delete user's messages with adaptive concurrency."""
        if messages is None:
            messages = self.get_my_messages(channel_id)

        # Delete thread replies before parent messages (child first)
        messages.sort(key=lambda m: (m.get("thread_ts", m["ts"]), m["ts"]), reverse=True)

        stats = CleanupStats(conversations_scanned=1, messages_found=len(messages))

        if dry_run:
            for msg in messages:
                stats.messages_deleted += 1
                if on_progress:
                    on_progress(stats)
            return stats

        # Adaptive delay: starts fast, slows down on rate limits
        delay = self.INITIAL_DELETE_DELAY
        lock = threading.Lock()

        def _delete_one(msg):
            nonlocal delay
            try:
                self._api_call_with_retry(self.client.chat_delete, channel=channel_id, ts=msg["ts"])
                with lock:
                    stats.messages_deleted += 1
                    # Speed back up gradually after success
                    delay = max(self.INITIAL_DELETE_DELAY, delay * 0.95)
            except SlackApiError as e:
                error_code = e.response.get("error", "unknown")
                if error_code == "message_not_found":
                    with lock:
                        stats.messages_deleted += 1
                elif error_code == "ratelimited":
                    with lock:
                        delay = min(self.MAX_DELETE_DELAY, delay * 2)
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    time.sleep(retry_after)
                    # Retry once more
                    try:
                        self._api_call_with_retry(
                            self.client.chat_delete, channel=channel_id, ts=msg["ts"]
                        )
                        with lock:
                            stats.messages_deleted += 1
                    except SlackApiError:
                        with lock:
                            stats.messages_failed += 1
                else:
                    with lock:
                        stats.messages_failed += 1
                        stats.errors.append(f"{error_code}: {msg.get('text', '')[:50]}")
            with lock:
                if on_progress:
                    on_progress(stats)
            time.sleep(delay)

        with ThreadPoolExecutor(max_workers=self.MAX_DELETE_WORKERS) as pool:
            list(pool.map(_delete_one, messages))

        return stats

    def cleanup_all_dms(
        self,
        dry_run: bool = False,
        on_progress: callable = None,
    ) -> CleanupStats:
        """Delete all user's messages across all DM conversations."""
        total_stats = CleanupStats()
        dms = self.list_dm_conversations()

        for dm in dms:
            logger.info(f"Cleaning DM with {dm['user_name']}...")
            messages = self.get_my_messages(dm["id"])
            total_stats.messages_found += len(messages)
            total_stats.conversations_scanned += 1

            if messages:
                result = self.delete_messages(
                    dm["id"], messages, dry_run=dry_run, on_progress=on_progress
                )
                total_stats.messages_deleted += result.messages_deleted
                total_stats.messages_failed += result.messages_failed
                total_stats.errors.extend(result.errors)

        return total_stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_user_name(self, user_id: str) -> str:
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        try:
            resp = self._api_call_with_retry(self.client.users_info, user=user_id)
            user = resp["user"]
            name = user.get("real_name") or user.get("name") or user_id
        except SlackApiError:
            name = user_id
        self._user_cache[user_id] = name
        return name
