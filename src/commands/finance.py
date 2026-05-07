import re

import discord

from src.config import (
    ADMIN_ROLE_NAMES,
    ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE,
    ALBION_MARKET_SALE_PREMIUM_TAX_RATE,
    ALBION_MARKET_SETUP_FEE_RATE,
    DEFAULT_CURRENCY,
    MAX_SPLIT_HISTORY_LIMIT,
    MAX_TRANSACTION_HISTORY_LIMIT,
    SPLIT_HISTORY_DEFAULT_LIMIT,
    TRANSACTION_HISTORY_DEFAULT_LIMIT,
)
from src.embeds import balance_embed, debt_summary_embed, error_embed, split_history_embed, split_result_embed, success_embed, transactions_embed
from src.services.finance import FinanceService
from src.storage import DataStore
from src.utils import format_amount


def is_admin(member: discord.Member) -> bool:
    return any(role.name in ADMIN_ROLE_NAMES for role in member.roles)


def transaction_line(entry: dict, currency: str) -> str:
    amount = format_amount(entry["amount"], currency)
    tx_type = entry["type"].replace("_", " ").title()
    timestamp = entry["timestamp"]
    reason = entry.get("reason", "No reason provided")
    detail_parts = [f"`{entry['transaction_id']}` • {tx_type}", f"Amount: {amount}", f"Reason: {reason}", f"At: {timestamp}"]

    if "available_balance_after" in entry:
        detail_parts.append(f"Balance After: {format_amount(entry['available_balance_after'], currency)}")
    if "debt_total_after" in entry:
        detail_parts.append(f"Debt After: {format_amount(entry['debt_total_after'], currency)}")
    if "creditor_id" in entry:
        detail_parts.append(f"Counterparty: <@{entry['creditor_id']}>")
    if "split_id" in entry:
        detail_parts.append(f"Split ID: `{entry['split_id']}`")

    return "\n".join(detail_parts)


def parse_member_mentions(raw_value: str, guild: discord.Guild) -> list[discord.Member]:
    member_ids = re.findall(r"\d{17,20}", raw_value)
    seen = set()
    members = []
    for member_id in member_ids:
        if member_id in seen:
            continue
        seen.add(member_id)
        member = guild.get_member(int(member_id))
        if member:
            members.append(member)
    return members


def split_history_line(split: dict, guild: discord.Guild) -> str:
    participant_mentions = ", ".join(
        guild.get_member(int(participant_id)).mention if guild.get_member(int(participant_id)) else f"<@{participant_id}>"
        for participant_id in split["participant_ids"]
    )
    status = "Undone" if split.get("undone") else "Active"
    return (
        f"**Split ID:** `{split['split_id']}`\n"
        f"**Status:** {status}\n"
        f"**Created:** {split['created_at']}\n"
        f"**Premium:** {'Yes' if split.get('has_premium') else 'No'}\n"
        f"**Gross:** {format_amount(split['gross_value'], DEFAULT_CURRENCY)}\n"
        f"**Net:** {format_amount(split['net_value'], DEFAULT_CURRENCY)}\n"
        f"**Per Person:** {format_amount(split['split_amount'], DEFAULT_CURRENCY)}\n"
        f"**Participants:** {participant_mentions}"
    )


def register_finance_commands(bot: discord.Bot, store: DataStore) -> None:
    finance_service = FinanceService(store)

    @bot.slash_command(name="balance", description="Show debt summary and withdrawable balance.")
    async def balance(ctx: discord.ApplicationContext, member: discord.Member = None):
        await ctx.defer()
        target = member or ctx.author
        store.get_user(target.id, target.name)
        snapshot = finance_service.get_finance_snapshot(target.id)
        store.save()

        currency = snapshot["currency"] or DEFAULT_CURRENCY
        debt_embed = debt_summary_embed(
            target,
            snapshot["owes_total"],
            snapshot["owes_lines"],
            snapshot["owed_total"],
            snapshot["owed_lines"],
            currency,
        )
        funds_embed = balance_embed(target, snapshot["available_balance"], currency)
        await ctx.followup.send(embeds=[debt_embed, funds_embed])

    @bot.slash_command(name="transactions", description="Show recent balance and debt transactions.")
    async def transactions(
        ctx: discord.ApplicationContext,
        member: discord.Member = None,
        limit: int = TRANSACTION_HISTORY_DEFAULT_LIMIT,
    ):
        target = member or ctx.author
        ephemeral = target != ctx.author and not is_admin(ctx.author)
        await ctx.defer(ephemeral=ephemeral)
        safe_limit = max(1, min(limit, MAX_TRANSACTION_HISTORY_LIMIT))
        currency, entries = finance_service.get_transactions(target.id, safe_limit)
        embed = transactions_embed(
            target,
            [transaction_line(entry, currency or DEFAULT_CURRENCY) for entry in entries],
        )
        await ctx.followup.send(embed=embed, ephemeral=ephemeral)

    @bot.slash_command(name="add_balance", description="Admin: add withdrawable balance.")
    async def add_balance(ctx: discord.ApplicationContext, member: discord.Member, amount: int, reason: str):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can add balance."), ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond(embed=error_embed("Invalid Amount", "Amount must be greater than 0."), ephemeral=True)
            return

        finance_service.add_balance(member.id, member.name, amount, reason, ctx.author.id)
        await ctx.respond(
            embed=success_embed(
                "Balance Added",
                f"{member.mention} now has {format_amount(store.get_user(member.id, member.name)['available_balance'], DEFAULT_CURRENCY)} available.",
            )
        )

    @bot.slash_command(name="withdraw_balance", description="Admin: pull from available balance for in-game withdrawal.")
    async def withdraw_balance(ctx: discord.ApplicationContext, member: discord.Member, amount: int, reason: str):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can withdraw balance."), ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond(embed=error_embed("Invalid Amount", "Amount must be greater than 0."), ephemeral=True)
            return

        try:
            finance_service.withdraw_balance(member.id, member.name, amount, reason, ctx.author.id)
        except ValueError as exc:
            await ctx.respond(embed=error_embed("Withdrawal Blocked", str(exc)), ephemeral=True)
            return

        await ctx.respond(
            embed=success_embed(
                "Balance Withdrawn",
                f"Pulled {format_amount(amount, DEFAULT_CURRENCY)} from {member.mention}. Remaining: {format_amount(store.get_user(member.id, member.name)['available_balance'], DEFAULT_CURRENCY)}.",
            )
        )

    @bot.slash_command(name="add_debt", description="Admin: add debt from one member to another.")
    async def add_debt(
        ctx: discord.ApplicationContext,
        debtor: discord.Member,
        creditor: discord.Member,
        amount: int,
        reason: str = "Debt",
    ):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can add debt."), ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond(embed=error_embed("Invalid Amount", "Amount must be greater than 0."), ephemeral=True)
            return

        finance_service.add_debt(debtor.id, debtor.name, creditor.id, amount, reason, ctx.author.id)
        await ctx.respond(
            embed=success_embed(
                "Debt Added",
                f"{debtor.mention} now owes {creditor.mention} {format_amount(amount, DEFAULT_CURRENCY)}.\nReason: {reason}",
            )
        )

    @bot.slash_command(name="clear_debt", description="Admin: clear debt between two members.")
    async def clear_debt(ctx: discord.ApplicationContext, debtor: discord.Member, creditor: discord.Member):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can clear debt."), ephemeral=True)
            return

        try:
            cleared_amount = finance_service.clear_debt(debtor.id, debtor.name, creditor.id, ctx.author.id)
        except ValueError as exc:
            await ctx.respond(embed=error_embed("Clear Debt Failed", str(exc)), ephemeral=True)
            return

        await ctx.respond(
            embed=success_embed(
                "Debt Cleared",
                f"Removed {format_amount(cleared_amount, DEFAULT_CURRENCY)} debt between {debtor.mention} and {creditor.mention}.",
            )
        )

    @bot.slash_command(name="finish_split", description="Admin: calculate post-tax split and credit each participant.")
    async def finish_split(
        ctx: discord.ApplicationContext,
        gear_value: int,
        bags_value: int,
        has_premium: bool,
        users: str,
    ):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can finish splits."), ephemeral=True)
            return

        members = parse_member_mentions(users, ctx.guild)
        if not members:
            await ctx.respond(
                embed=error_embed("No Users Found", "Mention at least one valid server member in `users`."),
                ephemeral=True,
            )
            return

        await ctx.defer()
        try:
            split = finance_service.finish_split(members, gear_value, bags_value, has_premium, ctx.author.id)
        except ValueError as exc:
            await ctx.followup.send(embed=error_embed("Split Failed", str(exc)), ephemeral=True)
            return

        participant_lines = [
            f"{member.mention} • {format_amount(split['split_amount'], DEFAULT_CURRENCY)}"
            for member in members
        ]
        mention_string = " ".join(member.mention for member in members)
        sale_tax_rate = ALBION_MARKET_SALE_PREMIUM_TAX_RATE if has_premium else ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE
        description = (
            f"{mention_string}\n\n"
            f"**Gear Value:** {format_amount(gear_value, DEFAULT_CURRENCY)}\n"
            f"**Bags Value:** {format_amount(bags_value, DEFAULT_CURRENCY)}\n"
            f"**Premium:** {'Yes' if has_premium else 'No'}\n"
            f"**Gross Value:** {format_amount(split['gross_value'], DEFAULT_CURRENCY)}\n"
            f"**Setup Fee ({ALBION_MARKET_SETUP_FEE_RATE * 100:.1f}%):** {format_amount(split['setup_fee'], DEFAULT_CURRENCY)}\n"
            f"**Sale Tax ({sale_tax_rate * 100:.1f}%):** {format_amount(split['sale_tax'], DEFAULT_CURRENCY)}\n"
            f"**Net Split Pool:** {format_amount(split['net_value'], DEFAULT_CURRENCY)}\n"
            f"**Per Person:** {format_amount(split['split_amount'], DEFAULT_CURRENCY)}\n"
            f"**Remainder:** {format_amount(split['remainder'], DEFAULT_CURRENCY)}\n"
            f"**Split ID:** `{split['split_id']}`"
        )
        await ctx.followup.send(
            content=mention_string,
            embed=split_result_embed("Split Finished", description, participant_lines),
        )

    @bot.slash_command(name="undo_split", description="Admin: reverse a previous finish_split by split ID.")
    async def undo_split(ctx: discord.ApplicationContext, split_id: str):
        if not is_admin(ctx.author):
            await ctx.respond(embed=error_embed("Admin Only", "Only admins can undo splits."), ephemeral=True)
            return

        await ctx.defer()
        try:
            split = finance_service.undo_split(split_id, ctx.guild, ctx.author.id)
        except ValueError as exc:
            await ctx.followup.send(embed=error_embed("Undo Failed", str(exc)), ephemeral=True)
            return

        members = [
            ctx.guild.get_member(int(participant_id))
            for participant_id in split["participant_ids"]
        ]
        participant_lines = [
            f"{member.mention if member else f'<@{participant_id}>'} • removed {format_amount(split['split_amount'], DEFAULT_CURRENCY)}"
            for member, participant_id in zip(members, split["participant_ids"])
        ]
        mention_string = " ".join(
            member.mention if member else f"<@{participant_id}>"
            for member, participant_id in zip(members, split["participant_ids"])
        )
        description = (
            f"{mention_string}\n\n"
            f"Reversed split `{split_id}`.\n"
            f"**Removed Per Person:** {format_amount(split['split_amount'], DEFAULT_CURRENCY)}\n"
            f"**Original Net Pool:** {format_amount(split['net_value'], DEFAULT_CURRENCY)}"
        )
        await ctx.followup.send(
            content=mention_string,
            embed=split_result_embed("Split Undone", description, participant_lines),
        )

    @bot.slash_command(name="split_history", description="Show recent split history and split IDs.")
    async def split_history(ctx: discord.ApplicationContext, limit: int = SPLIT_HISTORY_DEFAULT_LIMIT):
        safe_limit = max(1, min(limit, MAX_SPLIT_HISTORY_LIMIT))
        await ctx.defer()
        splits = finance_service.get_split_history(safe_limit)
        embed = split_history_embed([split_history_line(split, ctx.guild) for split in splits])
        await ctx.followup.send(embed=embed)
