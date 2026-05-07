from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from uuid import uuid4

import discord

from src.config import CONTENT_TYPES, GEAR_REACTIONS
from src.embeds import content_live_embed, current_team_embed, scheduled_content_embed
from src.storage import DataStore
from src.utils import from_iso8601, to_iso8601, utcnow


class SchedulingService:
    def __init__(self, bot: discord.Bot, store: DataStore):
        self.bot = bot
        self.store = store
        self._tasks: dict[str, asyncio.Task] = {}
        self._team_update_tasks: dict[str, asyncio.Task] = {}

    def get_content_choices(self) -> list[discord.OptionChoice]:
        return [
            discord.OptionChoice(name=config["label"], value=content_key)
            for content_key, config in CONTENT_TYPES.items()
        ]

    def resolve_roles(self, guild: discord.Guild, content_type: str) -> list[discord.Role]:
        config = CONTENT_TYPES[content_type]
        roles = []
        for role_name in config["role_names"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                roles.append(role)
        return roles

    def get_role_caps_for_content(self, content_type: str) -> dict[str, int | None]:
        stored_caps = self.store.get_content_role_caps().get(content_type, {})
        return {
            "tank": stored_caps.get("tank"),
            "dps": stored_caps.get("dps"),
            "healer": stored_caps.get("healer"),
        }

    def find_schedule_by_announcement_message(self, message_id: int | str) -> dict[str, Any] | None:
        message_key = str(message_id)
        for schedule in self.store.get_scheduled_content().values():
            if schedule.get("announcement_message_id") == message_key:
                return schedule
        return None

    async def _get_channel(self, channel_id: int) -> discord.abc.GuildChannel:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        return channel

    async def _get_signup_message(self, schedule: dict[str, Any]) -> discord.Message:
        channel = await self._get_channel(int(schedule["channel_id"]))
        return await channel.fetch_message(int(schedule["announcement_message_id"]))

    async def _build_team_map(self, schedule: dict[str, Any]) -> dict[str, list[str]]:
        message = await self._get_signup_message(schedule)
        team_map = {role: [] for role in GEAR_REACTIONS}
        emoji_to_role = {emoji: role for role, emoji in GEAR_REACTIONS.items()}

        for reaction in message.reactions:
            role_name = emoji_to_role.get(str(reaction.emoji))
            if not role_name:
                continue
            users = []
            async for user in reaction.users():
                if user.bot:
                    continue
                users.append(f"<@{user.id}>")
            team_map[role_name] = users

        return team_map

    async def _notify_cap_reached(self, schedule: dict[str, Any], user_id: int, role_name: str, cap_value: int) -> None:
        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        content_label = CONTENT_TYPES[schedule["content_type"]]["label"]
        message_text = f"{content_label} {role_name.title()} cap reached ({cap_value}). Your reaction was removed."
        try:
            await user.send(message_text)
            return
        except discord.Forbidden:
            pass

        channel = await self._get_channel(int(schedule["channel_id"]))
        fallback_message = await channel.send(f"<@{user_id}> {message_text}")
        await asyncio.sleep(8)
        try:
            await fallback_message.delete()
        except discord.NotFound:
            pass

    async def _role_is_full(self, schedule: dict[str, Any], role_name: str, user_id: int) -> bool:
        role_caps = schedule.get("role_caps", {})
        cap_value = role_caps.get(role_name)
        if cap_value is None:
            return False

        team_map = await self._build_team_map(schedule)
        member_mentions = team_map[role_name]
        user_mention = f"<@{user_id}>"
        if user_mention in member_mentions:
            return False
        return len(member_mentions) >= cap_value

    async def create_or_update_team_embed(self, schedule: dict[str, Any]) -> None:
        starts_at = from_iso8601(schedule["scheduled_for"])
        content_label = CONTENT_TYPES[schedule["content_type"]]["label"]
        team_map = await self._build_team_map(schedule)
        embed = current_team_embed(content_label, starts_at, team_map, schedule.get("role_caps"))
        channel = await self._get_channel(int(schedule["channel_id"]))

        team_message_id = schedule.get("current_team_message_id")
        if team_message_id:
            try:
                team_message = await channel.fetch_message(int(team_message_id))
                await team_message.edit(embed=embed)
                return
            except discord.NotFound:
                pass

        team_message = await channel.send(embed=embed)
        self.store.update_schedule(schedule["schedule_id"], current_team_message_id=str(team_message.id))
        self.store.save()

    async def sync_reaction_team(self, payload: discord.RawReactionActionEvent, remove_other_roles: bool) -> None:
        schedule = self.find_schedule_by_announcement_message(payload.message_id)
        if not schedule:
            return

        emoji_name = str(payload.emoji)
        emoji_to_role = {emoji: role for role, emoji in GEAR_REACTIONS.items()}
        role_name = emoji_to_role.get(emoji_name)
        if role_name is None:
            return

        message = await self._get_signup_message(schedule)
        if remove_other_roles and await self._role_is_full(schedule, role_name, payload.user_id):
            await message.remove_reaction(emoji_name, discord.Object(id=payload.user_id))
            cap_value = schedule.get("role_caps", {}).get(role_name)
            if cap_value is not None:
                await self._notify_cap_reached(schedule, payload.user_id, role_name, cap_value)
            self.queue_team_update(schedule["schedule_id"])
            return

        if remove_other_roles:
            for other_emoji in GEAR_REACTIONS.values():
                if other_emoji == emoji_name:
                    continue
                await message.remove_reaction(other_emoji, discord.Object(id=payload.user_id))

        self.queue_team_update(schedule["schedule_id"])

    def queue_team_update(self, schedule_id: str, delay_seconds: float = 0.75) -> None:
        existing_task = self._team_update_tasks.get(schedule_id)
        if existing_task and not existing_task.done():
            return
        self._team_update_tasks[schedule_id] = asyncio.create_task(
            self._delayed_team_update(schedule_id, delay_seconds)
        )

    async def _delayed_team_update(self, schedule_id: str, delay_seconds: float) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            schedule = self.store.get_scheduled_content().get(schedule_id)
            if not schedule or schedule.get("started"):
                return
            await self.create_or_update_team_embed(schedule)
        finally:
            self._team_update_tasks.pop(schedule_id, None)

    async def create_schedule(
        self,
        ctx: discord.ApplicationContext,
        content_type: str,
        minutes_from_now: int,
        gearsets: str | None,
    ) -> tuple[dict[str, Any], discord.Message]:
        starts_at = utcnow() + timedelta(minutes=minutes_from_now)
        roles = self.resolve_roles(ctx.guild, content_type)
        if not roles:
            raise ValueError(
                f"No roles configured for `{CONTENT_TYPES[content_type]['label']}`. Update role names in src/config.py."
            )

        role_mentions = " ".join(role.mention for role in roles)
        role_caps = self.get_role_caps_for_content(content_type)
        embed = scheduled_content_embed(
            title=f"{CONTENT_TYPES[content_type]['label']} Scheduled",
            content_label=CONTENT_TYPES[content_type]["label"],
            role_mentions=role_mentions,
            starts_at=starts_at,
            gearsets=gearsets,
            role_caps=role_caps,
        )
        message = await ctx.respond(embed=embed)
        original_message = await ctx.interaction.original_response()

        for emoji in GEAR_REACTIONS.values():
            await original_message.add_reaction(emoji)

        schedule_id = uuid4().hex
        schedule = {
            "schedule_id": schedule_id,
            "content_type": content_type,
            "scheduled_for": to_iso8601(starts_at),
            "gearsets": gearsets,
            "guild_id": str(ctx.guild.id),
            "channel_id": str(ctx.channel.id),
            "role_ids": [str(role.id) for role in roles],
            "created_by": str(ctx.author.id),
            "announcement_message_id": str(original_message.id),
            "current_team_message_id": None,
            "role_caps": role_caps,
            "started": False,
        }
        self.store.add_schedule(schedule_id, schedule)
        self.store.save()
        await self.create_or_update_team_embed(schedule)
        self._tasks[schedule_id] = asyncio.create_task(self._run_schedule(schedule_id))
        return schedule, original_message

    async def restore_pending_jobs(self) -> None:
        for schedule_id, schedule in self.store.get_scheduled_content().items():
            if schedule.get("started"):
                continue
            await self.create_or_update_team_embed(schedule)
            if schedule_id in self._tasks and not self._tasks[schedule_id].done():
                continue
            self._tasks[schedule_id] = asyncio.create_task(self._run_schedule(schedule_id))

    async def _run_schedule(self, schedule_id: str) -> None:
        schedule = self.store.get_scheduled_content().get(schedule_id)
        if not schedule or schedule.get("started"):
            return

        starts_at = from_iso8601(schedule["scheduled_for"])
        delay = max(0, (starts_at - utcnow()).total_seconds())
        if delay:
            await asyncio.sleep(delay)

        await self._send_start_message(schedule_id)

    async def _send_start_message(self, schedule_id: str) -> None:
        schedule = self.store.get_scheduled_content().get(schedule_id)
        if not schedule or schedule.get("started"):
            return

        channel = self.bot.get_channel(int(schedule["channel_id"]))
        if channel is None:
            channel = await self.bot.fetch_channel(int(schedule["channel_id"]))

        guild = self.bot.get_guild(int(schedule["guild_id"]))
        if guild is None:
            guild = channel.guild

        roles = [guild.get_role(int(role_id)) for role_id in schedule["role_ids"]]
        valid_roles = [role for role in roles if role is not None]
        role_mentions = " ".join(role.mention for role in valid_roles) if valid_roles else "@here"
        content_label = CONTENT_TYPES[schedule["content_type"]]["label"]
        embed = content_live_embed(content_label, role_mentions, schedule.get("gearsets"))

        await channel.send(embed=embed)
        self.store.update_schedule(schedule_id, started=True, started_at=to_iso8601(utcnow()))
        self.store.save()
