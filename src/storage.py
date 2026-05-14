from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from src.config import DATA_FILE, DEFAULT_ADMIN_ROLE_IDS, DEFAULT_CURRENCY
from src.utils import to_iso8601, utcnow


class DataStore:
    def __init__(self, path: str = DATA_FILE):
        self.path = path
        self._data = self._load_and_migrate()

    def _default_data(self) -> dict[str, Any]:
        return {
            "users": {},
            "scheduled_content": {},
            "splits": {},
            "content_role_caps": {},
            "content_role_ids": {},
            "content_channel_id": None,
            "admin_role_ids": DEFAULT_ADMIN_ROLE_IDS,
            "pinned_channels": {},
        }

    def _default_user(self, username: str = "Unknown") -> dict[str, Any]:
        return {
            "username": username,
            "currency": DEFAULT_CURRENCY,
            "available_balance": 0,
            "debts_owed": {},
            "last_updated": None,
            "transactions": [],
        }

    def _load_raw(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return self._default_data()
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_and_migrate(self) -> dict[str, Any]:
        data = self._load_raw()
        changed = False

        if "users" not in data:
            data["users"] = {}
            changed = True

        if "scheduled_content" not in data:
            data["scheduled_content"] = {}
            changed = True

        if "splits" not in data:
            data["splits"] = {}
            changed = True

        if "content_role_caps" not in data:
            data["content_role_caps"] = {}
            changed = True

        if "content_role_ids" not in data:
            data["content_role_ids"] = {}
            changed = True

        if "content_channel_id" not in data:
            data["content_channel_id"] = None
            changed = True

        if "admin_role_id" in data and "admin_role_ids" not in data:
            old_role_id = data.pop("admin_role_id")
            data["admin_role_ids"] = [old_role_id] if old_role_id else DEFAULT_ADMIN_ROLE_IDS
            changed = True
        elif "admin_role_ids" not in data:
            data["admin_role_ids"] = DEFAULT_ADMIN_ROLE_IDS
            changed = True

        if "pinned_channels" not in data:
            data["pinned_channels"] = {}
            changed = True

        for user_id, user in data["users"].items():
            if "available_balance" not in user:
                user["available_balance"] = 0
                changed = True

            if "debts_owed" not in user:
                legacy_owed_to = user.pop("owed_to", {})
                user["debts_owed"] = legacy_owed_to
                changed = True

            for creditor_id, debt_entry in list(user["debts_owed"].items()):
                if isinstance(debt_entry, int):
                    user["debts_owed"][creditor_id] = {
                        "amount": debt_entry,
                        "reason": "No reason provided",
                    }
                    changed = True

            if "currency" not in user:
                user["currency"] = DEFAULT_CURRENCY
                changed = True

            if "transactions" not in user:
                user["transactions"] = []
                changed = True

            if "last_updated" not in user:
                user["last_updated"] = None
                changed = True

            if "username" not in user:
                user["username"] = f"user-{user_id}"
                changed = True

            if "debt" in user:
                user.pop("debt")
                changed = True

        for schedule in data.get("scheduled_content", {}).values():
            if "team_assignments" not in schedule:
                schedule["team_assignments"] = {}
                changed = True

        for channel_state in data.get("pinned_channels", {}).values():
            if "managed_message_ids" not in channel_state:
                legacy_message_id = channel_state.pop("managed_message_id", None)
                channel_state["managed_message_ids"] = [legacy_message_id] if legacy_message_id else []
                changed = True
            if "templates" not in channel_state:
                channel_state.pop("latest_source_message_id", None)
                channel_state["templates"] = []
                changed = True
            else:
                normalized_templates = []
                template_changed = False
                for template in channel_state["templates"]:
                    if isinstance(template, str):
                        normalized_templates.append({"content": template, "created_by": "Unknown"})
                        template_changed = True
                    else:
                        normalized_templates.append(template)
                if template_changed:
                    channel_state["templates"] = normalized_templates
                    changed = True
            if "debounce_seconds" not in channel_state:
                channel_state["debounce_seconds"] = 5.0
                changed = True

        if changed:
            self._write(data)

        return data

    def _write(self, data: dict[str, Any] | None = None) -> None:
        payload = data if data is not None else self._data
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def save(self) -> None:
        self._write()

    def get_data(self) -> dict[str, Any]:
        return self._data

    def get_user(self, user_id: int | str, username: str = "Unknown") -> dict[str, Any]:
        user_key = str(user_id)
        users = self._data["users"]

        if user_key not in users:
            users[user_key] = self._default_user(username=username)

        users[user_key]["username"] = username
        users[user_key]["last_updated"] = to_iso8601(utcnow())
        return users[user_key]

    def create_transaction(
        self,
        user: dict[str, Any],
        tx_type: str,
        amount: int,
        reason: str,
        **extra: Any,
    ) -> dict[str, Any]:
        next_id = f"tx_{len(user['transactions']) + 1:03}"
        transaction = {
            "transaction_id": next_id,
            "type": tx_type,
            "amount": amount,
            "reason": reason,
            "timestamp": to_iso8601(utcnow()),
        }
        transaction.update(extra)
        user["transactions"].append(transaction)
        user["last_updated"] = transaction["timestamp"]
        return transaction

    def get_scheduled_content(self) -> dict[str, Any]:
        return self._data["scheduled_content"]

    def add_schedule(self, schedule_id: str, payload: dict[str, Any]) -> None:
        self._data["scheduled_content"][schedule_id] = payload

    def update_schedule(self, schedule_id: str, **updates: Any) -> None:
        if schedule_id not in self._data["scheduled_content"]:
            return
        self._data["scheduled_content"][schedule_id].update(updates)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def get_splits(self) -> dict[str, Any]:
        return self._data["splits"]

    def add_split(self, split_id: str, payload: dict[str, Any]) -> None:
        self._data["splits"][split_id] = payload

    def update_split(self, split_id: str, **updates: Any) -> None:
        if split_id not in self._data["splits"]:
            return
        self._data["splits"][split_id].update(updates)

    def get_content_role_caps(self) -> dict[str, Any]:
        return self._data["content_role_caps"]

    def set_content_role_caps(self, content_type: str, caps: dict[str, int | None]) -> None:
        self._data["content_role_caps"][content_type] = caps

    def get_content_role_ids(self) -> dict[str, Any]:
        return self._data["content_role_ids"]

    def set_content_role_ids(self, content_type: str, role_ids: list[str]) -> None:
        self._data["content_role_ids"][content_type] = role_ids

    def get_content_channel_id(self) -> str | None:
        return self._data["content_channel_id"]

    def set_content_channel_id(self, channel_id: str) -> None:
        self._data["content_channel_id"] = channel_id

    def get_admin_role_ids(self) -> list[str]:
        return self._data.get("admin_role_ids") or DEFAULT_ADMIN_ROLE_IDS

    def set_admin_role_ids(self, role_ids: list[str]) -> None:
        self._data["admin_role_ids"] = role_ids

    def get_pinned_channels(self) -> dict[str, Any]:
        return self._data["pinned_channels"]

    def set_pinned_channel(self, channel_id: str) -> None:
        if channel_id not in self._data["pinned_channels"]:
            self._data["pinned_channels"][channel_id] = {
                "managed_message_ids": [],
                "templates": [],
                "debounce_seconds": 5.0,
            }

    def update_pinned_channel(self, channel_id: str, **updates: Any) -> None:
        if channel_id not in self._data["pinned_channels"]:
            self.set_pinned_channel(channel_id)
        self._data["pinned_channels"][channel_id].update(updates)

    def remove_pinned_channel(self, channel_id: str) -> None:
        self._data["pinned_channels"].pop(channel_id, None)
