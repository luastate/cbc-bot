import discord

from src.storage import DataStore


def is_admin(member: discord.Member, store: DataStore) -> bool:
    admin_role_ids = store.get_admin_role_ids()
    if not admin_role_ids:
        return False
    return any(str(role.id) in [str(rid) for rid in admin_role_ids] for role in member.roles)
