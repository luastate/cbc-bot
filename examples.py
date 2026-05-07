import discord
from discord.ext import commands
from embed_builder import EmbedBuilder

async def send_paginated_info(ctx, items, items_per_page=5):
    pages = [items[i:i + items_per_page] for i in range(0, len(items), items_per_page)]
    
    for page_num, page_items in enumerate(pages, 1):
        fields = [
            {"name": f"Item {i+1}", "value": item, "inline": False}
            for i, item in enumerate(page_items)
        ]
        
        embed = EmbedBuilder.create_with_fields(
            title=f"Items (Page {page_num}/{len(pages)})",
            description="Here are your items",
            fields=fields
        )
        
        await ctx.send(embed=embed)

async def create_user_stats_embed(member: discord.Member, stats_data: dict):
    fields = []
    
    if 'level' in stats_data:
        fields.append({
            "name": "Level",
            "value": f"⭐ {stats_data['level']}",
            "inline": True
        })
    
    if 'xp' in stats_data:
        fields.append({
            "name": "Experience",
            "value": f"{stats_data['xp']} XP",
            "inline": True
        })
    
    if 'rank' in stats_data:
        fields.append({
            "name": "Rank",
            "value": f"#{stats_data['rank']}",
            "inline": True
        })
    
    if 'achievements' in stats_data and stats_data['achievements']:
        achievement_str = "\n".join([f"🏆 {a}" for a in stats_data['achievements'][:5]])
        fields.append({
            "name": "Recent Achievements",
            "value": achievement_str,
            "inline": False
        })
    
    embed = EmbedBuilder.create_rich(
        title=f"{member.name}'s Stats",
        description=stats_data.get('bio', 'No bio set'),
        color=member.color,
        thumbnail_url=member.avatar.url if member.avatar else None,
        fields=fields,
        footer_text=f"Member since {member.joined_at.strftime('%B %Y')}",
        timestamp=True
    )
    
    return embed

async def create_server_info_embed(guild: discord.Guild):
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    
    role_count = len(guild.roles) - 1
    
    fields = [
        {
            "name": "👑 Owner",
            "value": guild.owner.mention if guild.owner else "Unknown",
            "inline": True
        },
        {
            "name": "📅 Created",
            "value": guild.created_at.strftime("%Y-%m-%d"),
            "inline": True
        },
        {
            "name": "👥 Members",
            "value": str(guild.member_count),
            "inline": True
        },
        {
            "name": "💬 Text Channels",
            "value": str(text_channels),
            "inline": True
        },
        {
            "name": "🔊 Voice Channels",
            "value": str(voice_channels),
            "inline": True
        },
        {
            "name": "🎭 Roles",
            "value": str(role_count),
            "inline": True
        }
    ]
    
    if guild.premium_tier > 0:
        fields.append({
            "name": "✨ Boost Status",
            "value": f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            "inline": False
        })
    
    embed = EmbedBuilder.create_rich(
        title=f"{guild.name}",
        description=guild.description or "No description set",
        color=0x5865f2,
        thumbnail_url=guild.icon.url if guild.icon else None,
        fields=fields,
        footer_text=f"Server ID: {guild.id}",
        timestamp=True
    )
    
    return embed

def create_progress_embed(task_name: str, current: int, total: int):
    percentage = int((current / total) * 100) if total > 0 else 0
    filled = int(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    embed = EmbedBuilder.create_basic(
        title=f"⏳ {task_name}",
        description=f"```\n{bar} {percentage}%\n```",
        color=0x00ff00 if percentage == 100 else 0xffaa00
    )
    
    embed.add_field(
        name="Progress",
        value=f"{current:,} / {total:,}",
        inline=False
    )
    
    if percentage == 100:
        embed.set_footer(text="✅ Complete!")
    
    return embed

def create_leaderboard_embed(leaderboard_data: list, title: str = "Leaderboard"):
    medals = ["🥇", "🥈", "🥉"]
    
    leaderboard_text = []
    for i, entry in enumerate(leaderboard_data[:10], 1):
        medal = medals[i-1] if i <= 3 else f"`{i}.`"
        name = entry['name']
        score = entry['score']
        leaderboard_text.append(f"{medal} **{name}** - {score:,} points")
    
    embed = EmbedBuilder.create_basic(
        title=f"🏆 {title}",
        description="\n".join(leaderboard_text),
        color=0xffd700,
        timestamp=True
    )
    
    embed.set_footer(text="Updated")
    
    return embed

def create_poll_embed(question: str, options: list):
    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    fields = []
    for i, option in enumerate(options[:10]):
        fields.append({
            "name": f"{reactions[i]} Option {i+1}",
            "value": option,
            "inline": False
        })
    
    embed = EmbedBuilder.create_with_fields(
        title="📊 Poll",
        description=question,
        fields=fields,
        color=0x5865f2,
        timestamp=True
    )
    
    embed.set_footer(text="React with the corresponding emoji to vote!")
    
    return embed

def create_announcement_embed(
    title: str,
    message: str,
    announcement_type: str = "general"
):
    styles = {
        "general": {"emoji": "📢", "color": 0x5865f2},
        "important": {"emoji": "⚠️", "color": 0xff0000},
        "event": {"emoji": "🎉", "color": 0xffd700},
        "update": {"emoji": "🔔", "color": 0x00ff00}
    }
    
    style = styles.get(announcement_type, styles["general"])
    
    embed = EmbedBuilder.create_basic(
        title=f"{style['emoji']} {title}",
        description=message,
        color=style['color'],
        timestamp=True
    )
    
    embed.set_footer(text="Server Announcement")
    
    return embed

def create_help_embed(command_categories: dict):
    fields = []
    for category, commands in command_categories.items():
        command_list = "\n".join([f"`{cmd}`" for cmd in commands])
        fields.append({
            "name": f"📁 {category}",
            "value": command_list,
            "inline": False
        })
    
    embed = EmbedBuilder.create_with_fields(
        title="📖 Bot Commands",
        description="Here are all available commands:",
        fields=fields,
        color=0x5865f2,
        timestamp=False
    )
    
    embed.set_footer(text="Use !help <command> for more info on a specific command")
    
    return embed

def create_status_embed(uptime: str, server_count: int, user_count: int):
    fields = [
        {"name": "⏰ Uptime", "value": uptime, "inline": True},
        {"name": "🖥️ Servers", "value": str(server_count), "inline": True},
        {"name": "👥 Users", "value": f"{user_count:,}", "inline": True},
        {"name": "📡 Status", "value": "🟢 Online", "inline": True},
        {"name": "💚 Health", "value": "100%", "inline": True},
        {"name": "🔗 Latency", "value": "< 100ms", "inline": True}
    ]
    
    embed = EmbedBuilder.create_with_fields(
        title="🤖 Bot Status",
        description="Current bot statistics",
        fields=fields,
        color=0x00ff00,
        timestamp=True
    )
    
    return embed