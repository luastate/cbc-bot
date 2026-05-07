from __future__ import annotations

import math
from uuid import uuid4
from typing import Any

from src.config import (
    ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE,
    ALBION_MARKET_SALE_PREMIUM_TAX_RATE,
    ALBION_MARKET_SETUP_FEE_RATE,
)
from src.storage import DataStore
from src.utils import format_amount, to_iso8601, utcnow


class FinanceService:
    def __init__(self, store: DataStore):
        self.store = store

    @staticmethod
    def _format_debt_entry(counterparty_id: str, amount: int, currency: str, reason: str) -> str:
        return (
            f"**Member:** <@{counterparty_id}>\n"
            f"**Amount:** {format_amount(amount, currency)}\n"
            f"**Reason:** {reason}"
        )

    def get_finance_snapshot(self, member_id: int | str) -> dict[str, Any]:
        data = self.store.get_data()
        member_key = str(member_id)
        user = data["users"].get(member_key)
        if not user:
            return {
                "currency": None,
                "available_balance": 0,
                "owes_total": 0,
                "owes_lines": [],
                "owed_total": 0,
                "owed_lines": [],
            }

        owes_total = 0
        owes_lines = []
        currency = user.get("currency", "silver")
        for creditor_id, debt in user.get("debts_owed", {}).items():
            amount = debt.get("amount", 0)
            reason = debt.get("reason", "No reason provided")
            owes_total += amount
            owes_lines.append(self._format_debt_entry(creditor_id, amount, currency, reason))

        owed_total = 0
        owed_lines = []
        for other_id, other_user in data["users"].items():
            if other_id == member_key:
                continue
            debt = other_user.get("debts_owed", {}).get(member_key)
            if not debt:
                continue
            amount = debt.get("amount", 0)
            reason = debt.get("reason", "No reason provided")
            owed_total += amount
            owed_lines.append(self._format_debt_entry(other_id, amount, currency, reason))

        return {
            "currency": currency,
            "available_balance": user.get("available_balance", 0),
            "owes_total": owes_total,
            "owes_lines": owes_lines,
            "owed_total": owed_total,
            "owed_lines": owed_lines,
        }

    def add_balance(self, member_id: int, username: str, amount: int, reason: str, actor_id: int) -> dict[str, Any]:
        user = self.store.get_user(member_id, username)
        user["available_balance"] += amount
        transaction = self.store.create_transaction(
            user,
            "balance_credit",
            amount,
            reason,
            available_balance_after=user["available_balance"],
            performed_by=str(actor_id),
        )
        self.store.save()
        return transaction

    def withdraw_balance(self, member_id: int, username: str, amount: int, reason: str, actor_id: int) -> dict[str, Any]:
        user = self.store.get_user(member_id, username)
        if user["available_balance"] < amount:
            raise ValueError("Insufficient available balance.")
        user["available_balance"] -= amount
        transaction = self.store.create_transaction(
            user,
            "balance_withdrawal",
            amount,
            reason,
            available_balance_after=user["available_balance"],
            performed_by=str(actor_id),
        )
        self.store.save()
        return transaction

    def add_debt(
        self,
        debtor_id: int,
        debtor_name: str,
        creditor_id: int,
        amount: int,
        reason: str,
        actor_id: int,
    ) -> dict[str, Any]:
        debtor = self.store.get_user(debtor_id, debtor_name)
        creditor_key = str(creditor_id)
        if creditor_key not in debtor["debts_owed"]:
            debtor["debts_owed"][creditor_key] = {"amount": 0, "reason": reason}
        debtor["debts_owed"][creditor_key]["amount"] += amount
        debtor["debts_owed"][creditor_key]["reason"] = reason

        transaction = self.store.create_transaction(
            debtor,
            "debt_added",
            amount,
            reason,
            creditor_id=creditor_key,
            debt_total_after=sum(entry["amount"] for entry in debtor["debts_owed"].values()),
            performed_by=str(actor_id),
        )
        self.store.save()
        return transaction

    def clear_debt(
        self,
        debtor_id: int,
        debtor_name: str,
        creditor_id: int,
        actor_id: int,
    ) -> int:
        debtor = self.store.get_user(debtor_id, debtor_name)
        creditor_key = str(creditor_id)
        if creditor_key not in debtor["debts_owed"]:
            raise ValueError("No debt found for this creditor.")

        amount = debtor["debts_owed"].pop(creditor_key)["amount"]
        self.store.create_transaction(
            debtor,
            "debt_cleared",
            amount,
            "Debt cleared",
            creditor_id=creditor_key,
            debt_total_after=sum(entry["amount"] for entry in debtor["debts_owed"].values()),
            performed_by=str(actor_id),
        )
        self.store.save()
        return amount

    def get_transactions(self, member_id: int | str, limit: int) -> tuple[str | None, list[dict[str, Any]]]:
        data = self.store.get_data()
        user = data["users"].get(str(member_id))
        if not user:
            return None, []
        return user.get("currency"), list(reversed(user.get("transactions", [])[-limit:]))

    def finish_split(
        self,
        members: list[Any],
        gear_value: int,
        bags_value: int,
        has_premium: bool,
        actor_id: int,
    ) -> dict[str, Any]:
        if gear_value < 0 or bags_value < 0:
            raise ValueError("Gear and bags values must be 0 or greater.")
        if not members:
            raise ValueError("At least one member must be specified.")

        gross_value = gear_value + bags_value
        setup_fee = math.ceil(gross_value * ALBION_MARKET_SETUP_FEE_RATE)
        sale_tax_rate = ALBION_MARKET_SALE_PREMIUM_TAX_RATE if has_premium else ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE
        sale_tax = math.ceil(gross_value * sale_tax_rate)
        net_value = gross_value - setup_fee - sale_tax
        if net_value < 0:
            raise ValueError("Net split cannot be negative.")

        split_amount = net_value // len(members)
        remainder = net_value - (split_amount * len(members))
        split_id = uuid4().hex[:10]
        created_at = to_iso8601(utcnow())
        participant_ids = [str(member.id) for member in members]

        for member in members:
            user = self.store.get_user(member.id, member.name)
            user["available_balance"] += split_amount
            self.store.create_transaction(
                user,
                "split_credit",
                split_amount,
                f"Finished split {split_id}",
                split_id=split_id,
                gross_value=gross_value,
                setup_fee=setup_fee,
                sale_tax_rate=sale_tax_rate,
                sale_tax=sale_tax,
                available_balance_after=user["available_balance"],
                performed_by=str(actor_id),
            )

        split_record = {
            "split_id": split_id,
            "gear_value": gear_value,
            "bags_value": bags_value,
            "gross_value": gross_value,
            "setup_fee": setup_fee,
            "has_premium": has_premium,
            "sale_tax_rate": sale_tax_rate,
            "sale_tax": sale_tax,
            "net_value": net_value,
            "participant_ids": participant_ids,
            "split_amount": split_amount,
            "remainder": remainder,
            "performed_by": str(actor_id),
            "created_at": created_at,
            "undone": False,
        }
        self.store.add_split(split_id, split_record)
        self.store.save()
        return split_record

    def undo_split(self, split_id: str, guild: Any, actor_id: int) -> dict[str, Any]:
        split = self.store.get_splits().get(split_id)
        if not split:
            raise ValueError("Split ID not found.")
        if split.get("undone"):
            raise ValueError("That split was already undone.")

        split_amount = split["split_amount"]
        for participant_id in split["participant_ids"]:
            member = guild.get_member(int(participant_id))
            username = member.name if member else f"user-{participant_id}"
            user = self.store.get_user(participant_id, username)
            user["available_balance"] -= split_amount
            self.store.create_transaction(
                user,
                "split_reversal",
                split_amount,
                f"Undo split {split_id}",
                split_id=split_id,
                available_balance_after=user["available_balance"],
                performed_by=str(actor_id),
            )

        self.store.update_split(
            split_id,
            undone=True,
            undone_at=to_iso8601(utcnow()),
            undone_by=str(actor_id),
        )
        self.store.save()
        return split

    def get_split_history(self, limit: int) -> list[dict[str, Any]]:
        splits = list(self.store.get_splits().values())
        splits.sort(key=lambda entry: entry.get("created_at", ""), reverse=True)
        return splits[:limit]
