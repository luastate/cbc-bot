import discord

from src.storage import DataStore


def is_admin(member: discord.Member, store: DataStore) -> bool:
    if member.guild_permissions.administrator:
        return True
    
    guild_id = str(member.guild.id)
    admin_role_ids = store.get_admin_role_ids_for_guild(guild_id)
    if not admin_role_ids:
        return False
    return any(str(role.id) in [str(rid) for rid in admin_role_ids] for role in member.roles)
