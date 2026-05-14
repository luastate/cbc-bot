import asyncio
import time

import discord

from src.embeds import pinned_message_embed
from src.storage import DataStore


class PinnedMessageService:
    def __init__(self, bot: discord.Bot, store: DataStore):
        self.bot = bot
        self.store = store
        self._channel_locks: dict[str, asyncio.Lock] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}
        self._last_activity: dict[str, float] = {}

    def add_channel(self, channel_id: int) -> None:
        self.store.set_pinned_channel(str(channel_id))
        self.store.save()

    def remove_channel(self, channel_id: int) -> None:
        self.store.remove_pinned_channel(str(channel_id))
        self.store.save()

    def get_channels(self) -> dict[str, dict]:
        return self.store.get_pinned_channels()

    def is_enabled(self, channel_id: int) -> bool:
        return str(channel_id) in self.store.get_pinned_channels()

    def _get_lock(self, channel_id: str) -> asyncio.Lock:
        if channel_id not in self._channel_locks:
            self._channel_locks[channel_id] = asyncio.Lock()
        return self._channel_locks[channel_id]

    def add_template(self, channel_id: int, content: str, created_by: str) -> None:
        channel_key = str(channel_id)
        self.store.set_pinned_channel(channel_key)
        channel_state = self.store.get_pinned_channels()[channel_key]
        channel_state["templates"].append({"content": content, "created_by": created_by})
        self.store.save()

    def remove_template(self, channel_id: int, index: int) -> None:
        channel_key = str(channel_id)
        channel_state = self.store.get_pinned_channels().get(channel_key)
        if not channel_state:
            raise ValueError("Pinned channel not configured.")
        templates = channel_state["templates"]
        if index < 1 or index > len(templates):
            raise ValueError("Pinned message index out of range.")
        templates.pop(index - 1)
        self.store.save()

    def clear_templates(self, channel_id: int) -> None:
        channel_key = str(channel_id)
        self.store.set_pinned_channel(channel_key)
        self.store.update_pinned_channel(channel_key, templates=[])
        self.store.save()

    def set_debounce(self, channel_id: int, debounce_seconds: float) -> None:
        channel_key = str(channel_id)
        self.store.set_pinned_channel(channel_key)
        self.store.update_pinned_channel(channel_key, debounce_seconds=debounce_seconds)
        self.store.save()

    def queue_refresh(self, channel_id: int) -> None:
        channel_key = str(channel_id)
        if channel_key not in self.store.get_pinned_channels():
            return

        self._last_activity[channel_key] = time.monotonic()
        running_task = self._refresh_tasks.get(channel_key)
        if running_task and not running_task.done():
            return

        debounce_seconds = self.store.get_pinned_channels()[channel_key].get("debounce_seconds", 5.0)
        self._refresh_tasks[channel_key] = asyncio.create_task(
            self._refresh_channel_after_delay(channel_key, debounce_seconds)
        )

    async def _refresh_channel_after_delay(self, channel_id: str, delay_seconds: float) -> None:
        try:
            while True:
                await asyncio.sleep(delay_seconds)
                last_activity = self._last_activity.get(channel_id, 0.0)
                if time.monotonic() - last_activity >= delay_seconds:
                    break
            await self.refresh_channel(channel_id)
        finally:
            self._refresh_tasks.pop(channel_id, None)

    async def refresh_channel(self, channel_id: str) -> None:
        async with self._get_lock(channel_id):
            channel_state = self.store.get_pinned_channels().get(channel_id)
            if not channel_state:
                return

            templates = channel_state.get("templates", [])
            if not templates:
                return

            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                channel = await self.bot.fetch_channel(int(channel_id))

            for managed_message_id in channel_state.get("managed_message_ids", []):
                try:
                    managed_message = await channel.fetch_message(int(managed_message_id))
                    await managed_message.delete()
                except discord.NotFound:
                    pass

            managed_message_ids = []
            for template in templates:
                embed = pinned_message_embed(template["content"], template["created_by"])
                managed_message = await channel.send(embed=embed)
                managed_message_ids.append(str(managed_message.id))

            self.store.update_pinned_channel(channel_id, managed_message_ids=managed_message_ids)
            self.store.save()
