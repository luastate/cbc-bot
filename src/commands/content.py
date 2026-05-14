import discord
from discord.commands import option

from src.auth import is_admin
from src.config import CONTENT_TYPES
from src.embeds import error_embed, success_embed
from src.services.pinned_messages import PinnedMessageService
from src.services.scheduling import SchedulingService
from src.storage import DataStore
from src.utils import discord_timestamp, from_iso8601, parse_duration_to_minutes

def register_content_commands(
    bot: discord.Bot,
    store: DataStore,
    scheduling_service: SchedulingService,
    pinned_message_service: PinnedMessageService,
) -> None:
    content_choices = scheduling_service.get_content_choices()

    @bot.slash_command(name="schedule_content", description="Schedule content ping and start reminder.")
    @option("content_type", str, choices=content_choices, description="Type of content to run.")
    @option("time_from_now", str, description="When to start. Example: 30m, 2h, 1h30m.")
    @option("planned_gearsets", str, required=False, description="Optional pre-planned gearsets.")
    async def schedule_content(
        ctx: discord.ApplicationContext,
        content_type: str,
        time_from_now: str,
        planned_gearsets: str = None,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can schedule content."), ephemeral=True)
            return
        if content_type not in CONTENT_TYPES:
            await ctx.respond(embed=error_embed("Invalid Content", "That content type is not configured."), ephemeral=True)
            return

        try:
            minutes_from_now = parse_duration_to_minutes(time_from_now)
        except ValueError as exc:
            await ctx.respond(embed=error_embed("Invalid Time", str(exc)), ephemeral=True)
            return

        try:
            schedule, _ = await scheduling_service.create_schedule(
                ctx,
                content_type,
                minutes_from_now,
                planned_gearsets,
            )
        except ValueError as exc:
            await ctx.respond(embed=error_embed("Schedule Failed", str(exc)), ephemeral=True)
            return

        starts_at = from_iso8601(schedule["scheduled_for"])
        await ctx.followup.send(
            embed=success_embed(
                "Content Scheduled",
                (
                    f"{CONTENT_TYPES[content_type]['label']} set for "
                    f"{discord_timestamp(starts_at, 'F')} ({discord_timestamp(starts_at, 'R')}).\n"
                    "Signup reactions added."
                ),
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="set_content_role", description="Set ping role for a content type.")
    @option("content_type", str, choices=content_choices, description="Type of content to configure.")
    @option("role", discord.Role, description="Role to ping for this content.")
    async def set_content_role(
        ctx: discord.ApplicationContext,
        content_type: str,
        role: discord.Role,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can set content roles."), ephemeral=True)
            return
        if content_type not in CONTENT_TYPES:
            await ctx.respond(embed=error_embed("Invalid Content", "That content type is not configured."), ephemeral=True)
            return

        store.set_content_role_ids(content_type, [str(role.id)])
        store.save()
        await ctx.respond(
            embed=success_embed(
                "Content Role Updated",
                f"{CONTENT_TYPES[content_type]['label']} will now ping {role.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="set_content_channel", description="Set channel where content embeds will be sent.")
    @option("channel", discord.TextChannel, description="Channel for schedule and team embeds.")
    async def set_content_channel(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can set content channel."), ephemeral=True)
            return

        store.set_content_channel_id(str(channel.id))
        store.save()
        await ctx.respond(
            embed=success_embed(
                "Content Channel Updated",
                f"All content embeds will now be sent to {channel.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="set_admin_role", description="Set admin role used for bot admin commands.")
    @option("role", discord.Role, description="Role that should be treated as bot admin.")
    async def set_admin_role(
        ctx: discord.ApplicationContext,
        role: discord.Role,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only current bot admins can set admin role."), ephemeral=True)
            return

        store.set_admin_role_id(str(role.id))
        store.save()
        await ctx.respond(
            embed=success_embed(
                "Admin Role Updated",
                f"Bot admin role is now {role.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="set_content_caps", description="Set tank/dps/healer caps for a content type.")
    @option("content_type", str, choices=content_choices, description="Type of content to configure.")
    @option("tank_cap", int, required=False, description="Tank cap. Leave empty for no cap.")
    @option("dps_cap", int, required=False, description="DPS cap. Leave empty for no cap.")
    @option("healer_cap", int, required=False, description="Healer cap. Leave empty for no cap.")
    async def set_content_caps(
        ctx: discord.ApplicationContext,
        content_type: str,
        tank_cap: int = None,
        dps_cap: int = None,
        healer_cap: int = None,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can set content caps."), ephemeral=True)
            return
        if content_type not in CONTENT_TYPES:
            await ctx.respond(embed=error_embed("Invalid Content", "That content type is not configured."), ephemeral=True)
            return

        caps = {"tank": tank_cap, "dps": dps_cap, "healer": healer_cap}
        if all(value is None for value in caps.values()):
            await ctx.respond(embed=error_embed("No Caps Provided", "Set at least one cap."), ephemeral=True)
            return
        if any(value is not None and value < 0 for value in caps.values()):
            await ctx.respond(embed=error_embed("Invalid Cap", "Caps must be 0 or greater."), ephemeral=True)
            return

        existing_caps = scheduling_service.get_role_caps_for_content(content_type)
        for role_name, value in caps.items():
            if value is not None:
                existing_caps[role_name] = value

        store.set_content_role_caps(content_type, existing_caps)
        store.save()

        cap_lines = [
            f"Tank: {existing_caps['tank'] if existing_caps['tank'] is not None else 'No cap'}",
            f"DPS: {existing_caps['dps'] if existing_caps['dps'] is not None else 'No cap'}",
            f"Healer: {existing_caps['healer'] if existing_caps['healer'] is not None else 'No cap'}",
        ]
        await ctx.respond(
            embed=success_embed(
                "Content Caps Updated",
                f"{CONTENT_TYPES[content_type]['label']}\n\n" + "\n".join(cap_lines),
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="add_pinned_message", description="Add bot-managed pinned message template to channel.")
    @option("channel", discord.TextChannel, description="Channel to manage.")
    @option("content", str, description="Message content bot should keep at bottom.")
    async def add_pinned_message(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        content: str,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can manage pinned messages."), ephemeral=True)
            return

        pinned_message_service.add_template(channel.id, content, ctx.author.display_name)
        await ctx.respond(
            embed=success_embed(
                "Pinned Message Added",
                f"Stored pinned message for {channel.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="remove_pinned_message", description="Remove pinned message template from channel by index.")
    @option("channel", discord.TextChannel, description="Channel to manage.")
    @option("index", int, description="1-based pinned message index.")
    async def remove_pinned_message(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        index: int,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can manage pinned messages."), ephemeral=True)
            return

        try:
            pinned_message_service.remove_template(channel.id, index)
        except ValueError as exc:
            await ctx.respond(embed=error_embed("Remove Failed", str(exc)), ephemeral=True)
            return
        await ctx.respond(
            embed=success_embed(
                "Pinned Message Removed",
                f"Removed pinned message `{index}` from {channel.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="clear_pinned_messages", description="Remove all pinned message templates from channel.")
    @option("channel", discord.TextChannel, description="Channel to clear.")
    async def clear_pinned_messages(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can manage pinned messages."), ephemeral=True)
            return

        pinned_message_service.clear_templates(channel.id)
        await ctx.respond(
            embed=success_embed(
                "Pinned Messages Cleared",
                f"Cleared pinned messages for {channel.mention}.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="set_pinned_message_debounce", description="Set pinned message repost debounce for channel.")
    @option("channel", discord.TextChannel, description="Channel to manage.")
    @option("seconds", int, description="Debounce in seconds.")
    async def set_pinned_message_debounce(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
        seconds: int,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can manage pinned messages."), ephemeral=True)
            return
        if seconds < 1:
            await ctx.respond(embed=error_embed("Invalid Debounce", "Debounce must be at least 1 second."), ephemeral=True)
            return

        pinned_message_service.set_debounce(channel.id, float(seconds))
        await ctx.respond(
            embed=success_embed(
                "Pinned Debounce Updated",
                f"{channel.mention} debounce set to {seconds} seconds.",
            ),
            ephemeral=True,
        )

    @bot.slash_command(name="pinned_messages", description="Show pinned message setup for channel.")
    @option("channel", discord.TextChannel, description="Channel to inspect.")
    async def pinned_messages(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ):
        if not is_admin(ctx.author, store):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can view pinned messages."), ephemeral=True)
            return

        channel_state = pinned_message_service.get_channels().get(str(channel.id))
        if not channel_state:
            await ctx.respond(embed=success_embed("Pinned Messages", f"No pinned messages configured for {channel.mention}."), ephemeral=True)
            return

        templates = channel_state.get("templates", [])
        debounce_seconds = channel_state.get("debounce_seconds", 5.0)
        if not templates:
            description = f"{channel.mention}\nDebounce: {debounce_seconds:.0f}s\nNo pinned messages configured."
        else:
            lines = [
                f"{index}. {template['content']}\nPinned by: {template['created_by']}"
                for index, template in enumerate(templates, start=1)
            ]
            description = f"{channel.mention}\nDebounce: {debounce_seconds:.0f}s\n\n" + "\n\n".join(lines)

        await ctx.respond(
            embed=success_embed("Pinned Messages", description),
            ephemeral=True,
        )
