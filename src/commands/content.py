import discord
from discord.commands import option

from src.config import ADMIN_ROLE_NAMES, CONTENT_TYPES
from src.embeds import error_embed, success_embed
from src.services.scheduling import SchedulingService
from src.storage import DataStore
from src.utils import discord_timestamp, from_iso8601, parse_duration_to_minutes


def is_admin(member: discord.Member) -> bool:
    return any(role.name in ADMIN_ROLE_NAMES for role in member.roles)


def register_content_commands(bot: discord.Bot, store: DataStore, scheduling_service: SchedulingService) -> None:
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
        if not is_admin(ctx.author):
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
        if not is_admin(ctx.author):
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
