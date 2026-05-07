import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.commands.content import register_content_commands
from src.commands.finance import register_finance_commands
from src.config import DISCORD_BOT_TOKEN
from src.services.scheduling import SchedulingService
from src.storage import DataStore

load_dotenv()


intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.message_content = False
intents.members = True

bot = discord.Bot(intents=intents)
store = DataStore()
scheduling_service = SchedulingService(bot, store)

register_finance_commands(bot, store)
register_content_commands(bot, store, scheduling_service)

_startup_complete = False


@bot.event
async def on_ready():
    global _startup_complete

    print(f"{bot.user} is online")

    if not _startup_complete:
        await bot.sync_commands(force=True)
        await scheduling_service.restore_pending_jobs()
        _startup_complete = True
        print("Commands synced")
        print("Pending schedules restored")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    await scheduling_service.sync_reaction_team(payload, remove_other_roles=True)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    await scheduling_service.sync_reaction_team(payload, remove_other_roles=False)


bot.run(DISCORD_BOT_TOKEN or os.getenv("DISCORD_BOT_TOKEN"))
