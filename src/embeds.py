from __future__ import annotations

from typing import Iterable

import discord

from src.config import DEFAULT_CURRENCY, GEAR_REACTIONS
from src.utils import discord_timestamp, format_amount


BASE_COLOR = 0x4A0F14
SUCCESS_COLOR = 0x7A1820
WARNING_COLOR = 0xA61E2A
ERROR_COLOR = 0xC62839
INFO_COLOR = 0x8B1E2D
SECTION_DIVIDER = "────────────────"


def basic_embed(title: str, description: str, color: int = BASE_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def error_embed(title: str, description: str) -> discord.Embed:
    return basic_embed(title, description, color=ERROR_COLOR)


def success_embed(title: str, description: str) -> discord.Embed:
    return basic_embed(title, description, color=SUCCESS_COLOR)


def debt_summary_embed(
    member: discord.Member,
    owes_total: int,
    owes_lines: Iterable[str],
    owed_total: int,
    owed_lines: Iterable[str],
    currency: str = DEFAULT_CURRENCY,
) -> discord.Embed:
    embed = basic_embed(
        title=f"{member.display_name} Finance Summary",
        description="",
        color=INFO_COLOR,
    )
    embed.add_field(
        name=f"Debt You Owe • {format_amount(owes_total, currency)}",
        value=f"{SECTION_DIVIDER}\n\n" + "\n\n".join(owes_lines) if owes_lines else f"{SECTION_DIVIDER}\n\nNo outstanding debt.",
        inline=False,
    )
    embed.add_field(
        name=f"Debt Owed To You • {format_amount(owed_total, currency)}",
        value=f"{SECTION_DIVIDER}\n\n" + "\n\n".join(owed_lines) if owed_lines else f"{SECTION_DIVIDER}\n\nNobody owes you right now.",
        inline=False,
    )
    return embed


def balance_embed(member: discord.Member, balance: int, currency: str = DEFAULT_CURRENCY) -> discord.Embed:
    embed = basic_embed(
        title=f"{member.display_name} Withdrawable Balance",
        description="Funds admins can pull for in-game withdrawals.",
        color=SUCCESS_COLOR,
    )
    embed.add_field(
        name="Available Balance",
        value=format_amount(balance, currency),
        inline=False,
    )
    return embed


def transactions_embed(member: discord.Member, lines: list[str]) -> discord.Embed:
    embed = basic_embed(
        title=f"{member.display_name} Transaction History",
        description="\n\n".join(lines) if lines else "No transactions recorded.",
        color=BASE_COLOR,
    )
    return embed


def split_result_embed(
    title: str,
    description: str,
    participant_lines: list[str],
    color: int = SUCCESS_COLOR,
) -> discord.Embed:
    embed = basic_embed(title=title, description=description, color=color)
    embed.add_field(
        name="Participants",
        value="\n".join(participant_lines) if participant_lines else "No participants.",
        inline=False,
    )
    return embed


def split_history_embed(lines: list[str]) -> discord.Embed:
    return basic_embed(
        title="Split History",
        description="\n\n".join(lines) if lines else "No splits recorded.",
        color=INFO_COLOR,
    )


def scheduled_content_embed(
    title: str,
    content_label: str,
    role_mentions: str,
    starts_at,
    gearsets: str | None,
    role_caps: dict[str, int | None] | None = None,
) -> discord.Embed:
    embed = basic_embed(
        title=title,
        description=f"{role_mentions}",
        color=WARNING_COLOR,
    )
    embed.add_field(
        name="Start Time",
        value=f"{discord_timestamp(starts_at, 'F')}\n{discord_timestamp(starts_at, 'R')}",
        inline=False,
    )
    if gearsets:
        embed.add_field(
            name="Pre-Planned Gearsets",
            value=gearsets,
            inline=False,
        )
    role_lines = []
    for role_name in ("tank", "dps", "healer"):
        cap_value = role_caps.get(role_name) if role_caps else None
        cap_text = str(cap_value) if cap_value is not None else "No cap"
        role_lines.append(f"{GEAR_REACTIONS[role_name]} {role_name.title()} (Limit: {cap_text})")
    embed.add_field(
        name="React With Role",
        value="\n".join(role_lines),
        inline=False,
    )
    return embed


def current_team_embed(
    content_label: str,
    starts_at,
    team_map: dict[str, list[str]],
    role_caps: dict[str, int | None] | None = None,
) -> discord.Embed:
    embed = basic_embed(
        title=f"{content_label} Current Team",
        description=f"Live signup board.\nStarts {discord_timestamp(starts_at, 'F')} ({discord_timestamp(starts_at, 'R')})",
        color=INFO_COLOR,
    )
    tank_count = len(team_map["tank"])
    dps_count = len(team_map["dps"])
    healer_count = len(team_map["healer"])
    tank_cap = role_caps.get("tank") if role_caps else None
    dps_cap = role_caps.get("dps") if role_caps else None
    healer_cap = role_caps.get("healer") if role_caps else None
    embed.add_field(
        name=f"{GEAR_REACTIONS['tank']} Tank ({tank_count}/{tank_cap if tank_cap is not None else '∞'})",
        value="\n".join(team_map["tank"]) if team_map["tank"] else "None yet.",
        inline=True,
    )
    embed.add_field(
        name=f"{GEAR_REACTIONS['dps']} DPS ({dps_count}/{dps_cap if dps_cap is not None else '∞'})",
        value="\n".join(team_map["dps"]) if team_map["dps"] else "None yet.",
        inline=True,
    )
    embed.add_field(
        name=f"{GEAR_REACTIONS['healer']} Healer ({healer_count}/{healer_cap if healer_cap is not None else '∞'})",
        value="\n".join(team_map["healer"]) if team_map["healer"] else "None yet.",
        inline=True,
    )
    return embed


def content_live_embed(content_label: str, role_mentions: str, gearsets: str | None) -> discord.Embed:
    embed = basic_embed(
        title=f"{content_label} Starting Now",
        description=f"{role_mentions}\n\nForm up now.",
        color=SUCCESS_COLOR,
    )
    if gearsets:
        embed.add_field(
            name="Planned Gearsets",
            value=gearsets,
            inline=False,
        )
    return embed
