"""
Slack Cleaner Service
Handles all Slack API interactions for message deletion and offboarding tasks.
"""

import time
import logging
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

    # Slack API rate limit: ~50 requests per minute for chat.delete
    DELETE_DELAY = 1.2  # seconds between deletions
    # Tier 3 APIs allow ~50 req/min — 2 workers + delay keeps us under limit
    MAX_WORKERS = 2
    READ_DELAY = 0.8  # seconds between read API calls

    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self._user_id = None
        self._user_name = None
        self._user_cache = {}

    def _api_call_with_retry(self, api_method, **kwargs):
        """Call a Slack API method with automatic rate-limit retry."""
        for attempt in range(5):
            try:
                return api_method(**kwargs)
            except SlackApiError as e:
                if e.response.get("error") == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    delay = retry_after * (1.5 ** attempt)
                    logger.debug(f"Rate limited, sleeping {delay:.0f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                else:
                    raise
        raise SlackApiError("Rate limited after 5 retries", e.response)

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

    def _fetch_identity(self):
        resp = self._api_call_with_retry(self.client.auth_test)
        self._user_id = resp["user_id"]
        self._user_name = resp["user"]

    def _prefetch_users(self):
        """Bulk-fetch all workspace users into cache (1-2 API calls instead of N)."""
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
                "name": ch.get("name", "group-dm"),
                "purpose": ch.get("purpose", {}).get("value", ""),
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
                "name": ch.get("name", ""),
                "is_private": ch.get("is_private", False),
                "num_members": ch.get("num_members", 0),
            }
            for ch in channels
            if ch.get("is_member", False)
        ]

    # ------------------------------------------------------------------
    # Message retrieval
    # ------------------------------------------------------------------

    def get_my_messages(self, channel_id: str) -> list[dict]:
        """Get all messages sent by the current user in a conversation."""
        all_messages = []
        cursor = None
        while True:
            kwargs = {"channel": channel_id, "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
                time.sleep(self.READ_DELAY)
            resp = self._api_call_with_retry(self.client.conversations_history, **kwargs)
            my_msgs = [m for m in resp["messages"] if m.get("user") == self.user_id]
            all_messages.extend(my_msgs)
            # Stop early if no more pages or no user messages in this batch
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return all_messages

    def count_my_messages(self, channel_id: str) -> int:
        """Count messages by current user in a conversation."""
        return len(self.get_my_messages(channel_id))

    def count_my_messages_batch(
        self, channel_ids: list[str], on_each: callable = None
    ) -> dict[str, int]:
        """Count messages in multiple conversations concurrently.

        Args:
            channel_ids: List of channel IDs to count.
            on_each: Optional callback(channel_id, count) after each completes.

        Returns:
            Dict mapping channel_id -> message count.
        """
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
        """
        Delete user's messages from a conversation.

        Args:
            channel_id: Slack channel/DM ID
            messages: Pre-fetched messages (if None, will fetch them)
            dry_run: If True, simulate without deleting
            on_progress: Callback(stats) called after each deletion
        """
        if messages is None:
            messages = self.get_my_messages(channel_id)

        stats = CleanupStats(conversations_scanned=1, messages_found=len(messages))

        for msg in messages:
            if dry_run:
                stats.messages_deleted += 1
                if on_progress:
                    on_progress(stats)
                continue

            try:
                self._api_call_with_retry(self.client.chat_delete, channel=channel_id, ts=msg["ts"])
                stats.messages_deleted += 1
                time.sleep(self.DELETE_DELAY)
            except SlackApiError as e:
                error_code = e.response.get("error", "unknown")
                if error_code == "message_not_found":
                    stats.messages_deleted += 1  # already gone
                else:
                    stats.messages_failed += 1
                    stats.errors.append(f"{error_code}: {msg.get('text', '')[:50]}")
                    logger.error(f"Delete failed ({error_code}): {msg.get('text', '')[:50]}")

            if on_progress:
                on_progress(stats)

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
