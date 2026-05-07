import discord
from datetime import datetime
from typing import Optional, List, Dict

class EmbedBuilder:
    
    color_default = 0x5C4B51
    color_success = 0xC97B84
    color_error   = 0xE8A0A8
    color_warning = 0xF2C6A0
    color_info    = 0xD8A7B1
        
    @staticmethod
    def create_basic(
        title: str,
        description: str,
        color: int = color_default,
        timestamp: bool = False
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_with_fields(
        title: str,
        description: str,
        fields: List[Dict[str, any]],
        color: int = color_default,
        timestamp: bool = False
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        for field in fields:
            embed.add_field(
                name=field.get('name', 'Field'),
                value=field.get('value', 'No value'),
                inline=field.get('inline', True)
            )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_rich(
        title: str,
        description: str,
        color: int = color_default,
        footer_text: Optional[str] = None,
        footer_icon: Optional[str] = None,
        author_name: Optional[str] = None,
        author_icon: Optional[str] = None,
        author_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        fields: Optional[List[Dict[str, any]]] = None,
        timestamp: bool = True,
        url: Optional[str] = None
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            url=url
        )
        
        if footer_text:
            embed.set_footer(text=footer_text, icon_url=footer_icon)
        
        if author_name:
            embed.set_author(name=author_name, icon_url=author_icon, url=author_url)
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        
        if image_url:
            embed.set_image(url=image_url)
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Field'),
                    value=field.get('value', 'No value'),
                    inline=field.get('inline', True)
                )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_error(
        title: str = "Error",
        description: str = "An error occurred",
        error_details: Optional[str] = None,
        timestamp: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=EmbedBuilder.color_error
        )
        
        if error_details:
            embed.add_field(name="Details", value=error_details, inline=False)
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_success(
        title: str = "Success",
        description: str = "Operation completed successfully",
        details: Optional[str] = None,
        timestamp: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=EmbedBuilder.color_success
        )
        
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_warning(
        title: str = "Warning",
        description: str = "Please review this warning",
        warning_details: Optional[str] = None,
        timestamp: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=EmbedBuilder.color_warning
        )
        
        if warning_details:
            embed.add_field(name="Details", value=warning_details, inline=False)
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_info(
        title: str = "Information",
        description: str = "Here's some information",
        fields: Optional[List[Dict[str, any]]] = None,
        timestamp: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=EmbedBuilder.color_info
        )
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Field'),
                    value=field.get('value', 'No value'),
                    inline=field.get('inline', True)
                )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        return embed
    
    @staticmethod
    def create_custom(
        **kwargs
    ) -> discord.Embed:
        return discord.Embed(**kwargs)