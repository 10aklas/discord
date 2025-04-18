# Premium Discord Bot - Full Implementation
# A comprehensive Discord bot with 15+ premium features
# Built with discord.py v2.0

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import asyncio
import os
import datetime
import logging
import json
import random
import aiohttp
import motor.motor_asyncio
import matplotlib.pyplot as plt
import io
import re
import time
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, List, Dict, Any, Union
import wavelink
from openai import AsyncOpenAI
import requests
from urllib.parse import quote
import traceback
from pytube import YouTube
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from io import BytesIO
from collections import defaultdict, Counter
import textwrap
from better_profanity import profanity
import pytz
import uuid
import seaborn as sns
import concurrent.futures
import hashlib
import csv
from dateutil.relativedelta import relativedelta
import functools

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
TOP_GG_TOKEN = os.getenv('TOP_GG_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("premium_bot")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True
intents.voice_states = True
intents.presences = True

# Bot class
class PremiumBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.synced = False
        self.maintenance_mode = False
        self.db_client = None
        self.db = None
        self.custom_prefixes = {}
        self.premium_servers = set()
        self.command_usage = defaultdict(int)
        self.temp_voice_channels = {}
        self.active_giveaways = {}
        self.ticket_systems = {}
        self.startup_time = datetime.datetime.now()
        self.cached_messages = {}
        self.auto_responses = defaultdict(dict)
        self.reminders = {}
        self.leveling_cooldowns = {}
        self.current_polls = {}
        self.role_menus = {}
        self.welcome_messages = {}
        self.starboard_data = {}
        self.server_stats = {}
        
        # Premium features tracking
        self.premium_features = {
            "advanced_moderation": set(),   # Includes auto-mod, raid protection, filter systems
            "custom_welcome": set(),        # Customizable welcome messages and cards
            "leveling_system": set(),       # XP and level tracking with rewards
            "reaction_roles": set(),        # Role assignment via reactions
            "ticket_system": set(),         # Support ticket creation and management
            "temp_channels": set(),         # Temporary voice channels
            "music_player": set(),          # Advanced music features
            "auto_responder": set(),        # Custom auto-responses
            "analytics": set(),             # Server statistics and analytics
            "giveaways": set(),             # Automated giveaway system
            "polls": set(),                 # Advanced polling system
            "starboard": set(),             # Content highlighting system
            "scheduled_messages": set(),    # Scheduled announcements
            "ai_features": set(),           # AI-powered assistance
            "custom_commands": set(),       # User-defined custom commands
            "server_backups": set(),        # Server configuration backups
            "premium_embeds": set()         # Enhanced embed capabilities
        }
    
    async def get_prefix(self, message):
        # Default prefix
        default_prefix = '!'
        
        # Return default for DMs
        if not message.guild:
            return commands.when_mentioned_or(default_prefix)(self, message)
        
        # Get custom prefix if set
        guild_id = str(message.guild.id)
        prefix = self.custom_prefixes.get(guild_id, default_prefix)
        return commands.when_mentioned_or(prefix)(self, message)
    
    async def setup_hook(self):
        # Connect to MongoDB
        try:
            self.db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
            self.db = self.db_client.premium_bot
            logger.info("Connected to MongoDB")
            
            # Load configurations from database
            await self.load_configurations()
        except Exception as e:
            logger.error(f"Database connection error: {e}")
        
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"Loaded extension: {filename[:-3]}")
                except Exception as e:
                    logger.error(f"Failed to load extension {filename}: {e}")
        
        # Start background tasks
        self.check_reminders.start()
        self.update_server_stats.start()
        self.backup_data.start()
        self.process_scheduled_messages.start()
        self.refresh_cached_data.start()
    
    async def on_ready(self):
        if not self.synced:
            try:
                logger.info(f"Syncing slash commands...")
                await self.tree.sync()
                self.synced = True
                logger.info(f"Slash commands synced successfully")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
        
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | !help"
        )
        await self.change_presence(activity=activity)
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Bot is in {len(self.guilds)} guilds")
    
    async def load_configurations(self):
        # Load custom prefixes
        prefix_data = await self.db.prefixes.find().to_list(length=None)
        for item in prefix_data:
            self.custom_prefixes[item['guild_id']] = item['prefix']
        
        # Load premium servers
        premium_data = await self.db.premium_servers.find().to_list(length=None)
        for item in premium_data:
            self.premium_servers.add(item['guild_id'])
            
            # Load enabled features for this premium server
            for feature, enabled in item.get('features', {}).items():
                if enabled and feature in self.premium_features:
                    self.premium_features[feature].add(item['guild_id'])
        
        # Load auto responses
        auto_responses = await self.db.auto_responses.find().to_list(length=None)
        for item in auto_responses:
            self.auto_responses[item['guild_id']] = item['responses']
        
        # Load welcome messages
        welcome_data = await self.db.welcome_messages.find().to_list(length=None)
        for item in welcome_data:
            self.welcome_messages[item['guild_id']] = item
        
        # Load starboard data
        starboard_data = await self.db.starboard.find().to_list(length=None)
        for item in starboard_data:
            self.starboard_data[item['guild_id']] = item
        
        # Load active giveaways
        giveaways = await self.db.giveaways.find({"active": True}).to_list(length=None)
        for giveaway in giveaways:
            self.active_giveaways[giveaway['message_id']] = giveaway
        
        # Load role menus
        role_menus = await self.db.role_menus.find().to_list(length=None)
        for menu in role_menus:
            self.role_menus[menu['message_id']] = menu
    
    def is_premium(self, guild_id):
        """Check if a server has premium status"""
        return str(guild_id) in self.premium_servers
    
    def has_feature(self, guild_id, feature):
        """Check if a server has access to a specific premium feature"""
        guild_id = str(guild_id)
        return guild_id in self.premium_features.get(feature, set())
    
    async def log_command_usage(self, ctx):
        """Log command usage for analytics"""
        command_name = ctx.command.qualified_name
        guild_id = ctx.guild.id if ctx.guild else "DM"
        
        self.command_usage[command_name] += 1
        
        await self.db.command_analytics.update_one(
            {"command": command_name},
            {"$inc": {"uses": 1, f"guilds.{guild_id}": 1}},
            upsert=True
        )
    
    @tasks.loop(minutes=5)
    async def check_reminders(self):
        """Check and send due reminders"""
        current_time = datetime.datetime.now()
        reminders_to_send = []
        
        try:
            # Get all due reminders
            reminders = await self.db.reminders.find({
                "remind_time": {"$lte": current_time}
            }).to_list(length=None)
            
            for reminder in reminders:
                # Queue reminder for sending
                reminders_to_send.append(reminder)
                
                # Delete from database
                await self.db.reminders.delete_one({"_id": reminder["_id"]})
            
            # Send all due reminders
            for reminder in reminders_to_send:
                try:
                    user = self.get_user(int(reminder["user_id"]))
                    if user:
                        embed = discord.Embed(
                            title="⏰ Reminder",
                            description=reminder["content"],
                            color=0x3498db
                        )
                        embed.set_footer(text=f"Reminder set on {reminder['created_at'].strftime('%Y-%m-%d %H:%M')}")
                        await user.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send reminder: {e}")
        except Exception as e:
            logger.error(f"Error in reminder check: {e}")
    
    @tasks.loop(hours=1)
    async def update_server_stats(self):
        """Update server statistics for analytics"""
        try:
            for guild in self.guilds:
                stats = {
                    "member_count": guild.member_count,
                    "channel_count": len(guild.channels),
                    "role_count": len(guild.roles),
                    "timestamp": datetime.datetime.now()
                }
                
                await self.db.server_stats.insert_one({
                    "guild_id": str(guild.id),
                    **stats
                })
                
                # Update cached stats
                self.server_stats[str(guild.id)] = stats
        except Exception as e:
            logger.error(f"Error updating server stats: {e}")
    
    @tasks.loop(hours=24)
    async def backup_data(self):
        """Create backups of server configuration data"""
        try:
            premium_servers = list(self.premium_servers)
            for guild_id in premium_servers:
                if self.has_feature(guild_id, "server_backups"):
                    # Collect all relevant data for this server
                    server_data = {
                        "guild_id": guild_id,
                        "timestamp": datetime.datetime.now(),
                        "prefix": self.custom_prefixes.get(guild_id, "!"),
                        "auto_responses": self.auto_responses.get(guild_id, {}),
                        "welcome_config": self.welcome_messages.get(guild_id, {}),
                        "starboard_config": self.starboard_data.get(guild_id, {}),
                        "role_menus": {},
                        "custom_commands": []
                    }
                    
                    # Get custom commands
                    custom_commands = await self.db.custom_commands.find({"guild_id": guild_id}).to_list(length=None)
                    server_data["custom_commands"] = custom_commands
                    
                    # Save backup
                    await self.db.server_backups.insert_one(server_data)
                    
                    # Keep only the latest 5 backups
                    all_backups = await self.db.server_backups.find(
                        {"guild_id": guild_id}
                    ).sort("timestamp", -1).to_list(length=None)
                    
                    if len(all_backups) > 5:
                        for backup in all_backups[5:]:
                            await self.db.server_backups.delete_one({"_id": backup["_id"]})
        except Exception as e:
            logger.error(f"Error creating server backups: {e}")
    
    @tasks.loop(minutes=1)
    async def process_scheduled_messages(self):
        """Process and send scheduled messages"""
        current_time = datetime.datetime.now()
        
        try:
            # Get all due scheduled messages
            scheduled_messages = await self.db.scheduled_messages.find({
                "send_time": {"$lte": current_time},
                "sent": False
            }).to_list(length=None)
            
            for message in scheduled_messages:
                try:
                    guild = self.get_guild(int(message["guild_id"]))
                    if not guild:
                        continue
                        
                    channel = guild.get_channel(int(message["channel_id"]))
                    if not channel:
                        continue
                    
                    # Create embed if needed
                    if message.get("use_embed", False):
                        embed = discord.Embed(
                            title=message.get("embed_title", "Scheduled Message"),
                            description=message["content"],
                            color=int(message.get("embed_color", "3447003"), 16)
                        )
                        
                        if message.get("embed_image"):
                            embed.set_image(url=message["embed_image"])
                            
                        if message.get("embed_thumbnail"):
                            embed.set_thumbnail(url=message["embed_thumbnail"])
                            
                        await channel.send(embed=embed)
                    else:
                        await channel.send(message["content"])
                    
                    # Mark as sent
                    await self.db.scheduled_messages.update_one(
                        {"_id": message["_id"]},
                        {"$set": {"sent": True}}
                    )
                    
                    # If recurring, create next occurrence
                    if message.get("recurring"):
                        recurrence = message.get("recurrence_pattern", "daily")
                        next_time = None
                        
                        if recurrence == "daily":
                            next_time = current_time + datetime.timedelta(days=1)
                        elif recurrence == "weekly":
                            next_time = current_time + datetime.timedelta(weeks=1)
                        elif recurrence == "monthly":
                            next_time = current_time + relativedelta(months=1)
                        
                        if next_time:
                            new_message = message.copy()
                            del new_message["_id"]
                            new_message["send_time"] = next_time
                            new_message["sent"] = False
                            await self.db.scheduled_messages.insert_one(new_message)
                            
                except Exception as e:
                    logger.error(f"Error sending scheduled message: {e}")
                    
        except Exception as e:
            logger.error(f"Error in scheduled messages: {e}")
    
    @tasks.loop(minutes=30)
    async def refresh_cached_data(self):
        """Refresh cached data from database"""
        try:
            # Refresh premium server status
            premium_data = await self.db.premium_servers.find().to_list(length=None)
            self.premium_servers.clear()
            
            for feature in self.premium_features:
                self.premium_features[feature].clear()
                
            for item in premium_data:
                guild_id = item['guild_id']
                self.premium_servers.add(guild_id)
                
                # Update enabled features for this premium server
                for feature, enabled in item.get('features', {}).items():
                    if enabled and feature in self.premium_features:
                        self.premium_features[feature].add(guild_id)
            
            logger.info(f"Refreshed premium status cache. {len(self.premium_servers)} premium servers.")
        except Exception as e:
            logger.error(f"Error refreshing cached data: {e}")

# Helper functions
async def is_premium_server(ctx):
    """Check if command is used in a premium server"""
    if not ctx.guild:
        return False
    return bot.is_premium(ctx.guild.id)

async def has_premium_feature(ctx, feature):
    """Check if server has access to a specific premium feature"""
    if not ctx.guild:
        return False
    return bot.has_feature(ctx.guild.id, feature)

def format_time(seconds):
    """Format seconds into a readable time string"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)

def human_readable_size(size_bytes):
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

# Database models (Using motor with MongoDB)
# These are just structures for reference - we use motor directly

"""
User Model:
- user_id (str): Discord user ID
- premium (bool): Premium user status
- premium_since (datetime): When user became premium
- balance (int): Currency balance
- xp (dict): XP in different servers {guild_id: xp_amount}
- levels (dict): Levels in different servers {guild_id: level}
- badges (list): List of earned badges
- inventory (list): List of owned items
- reminders (list): List of active reminders
"""

"""
Guild Model:
- guild_id (str): Discord guild ID
- premium (bool): Premium server status
- premium_tier (int): Premium tier level
- premium_expires (datetime): When premium expires
- prefix (str): Custom prefix
- welcome_channel (str): Channel for welcome messages
- leave_channel (str): Channel for leave messages
- welcome_message (str): Custom welcome message
- leave_message (str): Custom leave message
- auto_roles (list): Roles to auto-assign
- mod_log_channel (str): Channel for mod logs
- mute_role (str): Role for muted users
- disabled_commands (list): Disabled commands
- auto_mod (dict): Auto-mod settings
- temp_channels_category (str): Category for temp channels
- temp_channels (dict): Settings for temp channels
- level_roles (dict): Roles to assign at levels
- level_channel (str): Channel for level up messages
- level_message (str): Custom level up message
- enabled_features (dict): Enabled premium features
"""

# Cog template
class ModuleName(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Commands would go here

# Creating a cog for each premium feature
class WelcomeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._welcome_cache = {}
        self.font = None
        self._load_font()
    
    def _load_font(self):
        """Load font for welcome images"""
        try:
            # Try to load a nice font or fallback to default
            font_path = "./assets/fonts/Montserrat-Bold.ttf"
            if os.path.exists(font_path):
                self.font = ImageFont.truetype(font_path, 36)
            else:
                self.font = ImageFont.load_default()
        except Exception as e:
            logger.error(f"Failed to load font: {e}")
            self.font = ImageFont.load_default()
    
    async def generate_welcome_card(self, member, welcome_data):
        """Generate a custom welcome card"""
        try:
            # Start with a canvas
            canvas_width, canvas_height = 1000, 300
            canvas = Image.new("RGBA", (canvas_width, canvas_height), (47, 49, 54, 255))
            draw = ImageDraw.Draw(canvas)
            
            # Draw background
            bg_color = tuple(int(welcome_data.get("bg_color", "#2f3136")[i:i+2], 16) for i in (1, 3, 5))
            draw.rectangle([(0, 0), (canvas_width, canvas_height)], fill=bg_color)
            
            # Draw accent bar
            accent_color = tuple(int(welcome_data.get("accent_color", "#5865f2")[i:i+2], 16) for i in (1, 3, 5))
            draw.rectangle([(0, 0), (canvas_width, 5)], fill=accent_color)
            
            # Get user avatar
            if member.avatar:
                async with aiohttp.ClientSession() as session:
                    avatar_url = member.avatar.url
                    async with session.get(str(avatar_url)) as resp:
                        if resp.status == 200:
                            avatar_data = await resp.read()
                            avatar = Image.open(BytesIO(avatar_data)).convert("RGBA")
                            
                            # Make avatar circular
                            mask = Image.new("L", avatar.size, 0)
                            draw_mask = ImageDraw.Draw(mask)
                            draw_mask.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                            
                            # Resize avatar
                            avatar_size = 150
                            avatar = avatar.resize((avatar_size, avatar_size))
                            mask = mask.resize((avatar_size, avatar_size))
                            
                            # Position avatar
                            avatar_pos = (50, 75)
                            canvas.paste(avatar, avatar_pos, mask)
            
            # Default font
            title_font = self.font
            subtitle_font = ImageFont.load_default()
            
            # Draw text
            welcome_text = welcome_data.get("title", "Welcome to the server!")
            server_name = member.guild.name
            member_name = f"{member.name}"
            
            # Draw welcome text
            draw.text((230, 90), welcome_text, fill=(255, 255, 255), font=title_font)
            
            # Draw member name
            draw.text((230, 140), member_name, fill=(255, 255, 255), font=title_font)
            
            # Draw member count
            member_count = member.guild.member_count
            draw.text((230, 180), f"You are member #{member_count}", fill=(200, 200, 200), font=subtitle_font)
            
            # Convert to bytes
            buffer = BytesIO()
            canvas.save(buffer, "PNG")
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            logger.error(f"Error generating welcome card: {e}")
            return None
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome message when a member joins"""
        guild_id = str(member.guild.id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "custom_welcome"):
            return
        
        welcome_config = self.bot.welcome_messages.get(guild_id)
        if not welcome_config:
            return
        
        try:
            channel_id = welcome_config.get("channel_id")
            if not channel_id:
                return
            
            channel = member.guild.get_channel(int(channel_id))
            if not channel:
                return
            
            message_template = welcome_config.get("message", "Welcome {user} to {server}!")
            use_card = welcome_config.get("use_card", False)
            
            # Format message
            message = message_template.format(
                user=member.mention,
                server=member.guild.name,
                name=member.name,
                count=member.guild.member_count
            )
            
            if use_card:
                # Generate welcome card
                card_buffer = await self.generate_welcome_card(member, welcome_config)
                
                if card_buffer:
                    card_file = discord.File(card_buffer, filename="welcome.png")
                    await channel.send(content=message, file=card_file)
                else:
                    await channel.send(content=message)
            else:
                # Just send message
                await channel.send(content=message)
                
            # Assign auto roles if configured
            if "auto_roles" in welcome_config:
                for role_id in welcome_config["auto_roles"]:
                    try:
                        role = member.guild.get_role(int(role_id))
                        if role:
                            await member.add_roles(role, reason="Auto role on join")
                    except Exception as e:
                        logger.error(f"Failed to assign auto role: {e}")
            
        except Exception as e:
            logger.error(f"Error in welcome system: {e}")
    
    @app_commands.command(name="welcome", description="Configure the welcome system")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def welcome_config(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        """Configure the welcome system"""
        if not self.bot.has_feature(interaction.guild_id, "custom_welcome"):
            embed = discord.Embed(
                title="Premium Feature",
                description="The custom welcome system is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create welcome configuration view
        await interaction.response.send_message("Opening welcome configuration menu...", ephemeral=True)
        
        # This would be a custom UI view with buttons and select menus
        # For brevity, not implementing the full UI here
        
    @app_commands.command(name="testwelcome", description="Test the welcome message")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def test_welcome(self, interaction: discord.Interaction):
        """Test the welcome message configuration"""
        if not self.bot.has_feature(interaction.guild_id, "custom_welcome"):
            embed = discord.Embed(
                title="Premium Feature",
                description="The custom welcome system is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild_id)
        welcome_config = self.bot.welcome_messages.get(guild_id)
        
        if not welcome_config:
            await interaction.response.send_message("Welcome system is not configured yet!", ephemeral=True)
            return
        
        # Simulate welcome message for the command user
        member = interaction.user
        try:
            channel_id = welcome_config.get("channel_id")
            if not channel_id:
                await interaction.response.send_message("Welcome channel not set!", ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message("Welcome channel not found or inaccessible!", ephemeral=True)
                return
            
            message_template = welcome_config.get("message", "Welcome {user} to {server}!")
            use_card = welcome_config.get("use_card", False)
            
            # Format message
            message = message_template.format(
                user=member.mention,
                server=interaction.guild.name,
                name=member.name,
                count=interaction.guild.member_count
            )
            
            # Send response first to avoid interaction timeout
            await interaction.response.send_message("Sending test welcome message...", ephemeral=True)
            
            if use_card:
                # Generate welcome card
                card_buffer = await self.generate_welcome_card(member, welcome_config)
                
                if card_buffer:
                    card_file = discord.File(card_buffer, filename="welcome_test.png")
                    await channel.send(content=f"**TEST MESSAGE:** {message}", file=card_file)
                else:
                    await channel.send(content=f"**TEST MESSAGE:** {message}")
            else:
                # Just send message
                await channel.send(content=f"**TEST MESSAGE:** {message}")
                
        except Exception as e:
            logger.error(f"Error in test welcome: {e}")
            await interaction.followup.send(f"Error testing welcome message: {e}", ephemeral=True)

class LevelingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldown = {}
        self.level_cache = {}
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages"""
        # Skip if not in a guild, or message is from a bot
        if not message.guild or message.author.bot:
            return
        
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "leveling_system"):
            return
        
        # Check cooldown (1 minute per user per guild)
        cooldown_key = f"{guild_id}:{user_id}"
        current_time = time.time()
        
        if cooldown_key in self.xp_cooldown:
            # If on cooldown, skip
            if current_time - self.xp_cooldown[cooldown_key] < 60:
                return
        
        # Set new cooldown
        self.xp_cooldown[cooldown_key] = current_time
        
        try:
            # Award between 15-25 XP per message
            xp_gain = random.randint(15, 25)
            
            # Get current XP and level from database
            user_data = await self.bot.db.levels.find_one({
                "guild_id": guild_id,
                "user_id": user_id
            })
            
            if not user_data:
                # Create new user entry
                user_data = {
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "xp": 0,
                    "level": 0,
                    "last_message": datetime.datetime.now()
                }
            
            # Calculate new XP and level
            current_xp = user_data["xp"] + xp_gain
            current_level = user_data["level"]
            
            # Calculate XP needed for next level (increases with each level)
            # Formula: 5 * (level ^ 2) + 50 * level + 100
            xp_needed = 5 * (current_level ** 2) + 50 * current_level + 100
            
            # Check if level up
            level_up = False
            if current_xp >= xp_needed:
                current_level += 1
                level_up = True
            
            # Update database
            await self.bot.db.levels.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {
                    "xp": current_xp,
                    "level": current_level,
                    "last_message": datetime.datetime.now()
                }},
                upsert=True
            )
            
            # Handle level up
            if level_up:
                # Get level settings
                level_settings = await self.bot.db.level_settings.find_one({"guild_id": guild_id})
                
                if level_settings:
                    # Check if announcement channel is set
                    if "channel_id" in level_settings:
                        try:
                            channel = message.guild.get_channel(int(level_settings["channel_id"]))
                            
                            if channel:
                                # Create level up message
                                level_message = level_settings.get("level_message", "Congratulations {user}! You've reached level {level}!")
                                formatted_message = level_message.format(
                                    user=message.author.mention,
                                    level=current_level,
                                    name=message.author.name
                                )
                                
                                embed = discord.Embed(
                                    title="Level Up!",
                                    description=formatted_message,
                                    color=discord.Color.green()
                                )
                                embed.set_thumbnail(url=message.author.display_avatar.url)
                                
                                await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Error sending level up message: {e}")
                    
                    # Check for level roles
                    if "level_roles" in level_settings:
                        level_roles = level_settings["level_roles"]
                        
                        for level_req, role_id in level_roles.items():
                            if int(level_req) <= current_level:
                                try:
                                    role = message.guild.get_role(int(role_id))
                                    if role and role not in message.author.roles:
                                        await message.author.add_roles(role, reason=f"Reached level {level_req}")
                                except Exception as e:
                                    logger.error(f"Error assigning level role: {e}")
        
        except Exception as e:
            logger.error(f"Error in leveling system: {e}")
    
    @app_commands.command(name="rank", description="Check your current rank")
    @app_commands.guild_only()
    async def rank(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Check your or someone else's rank"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "leveling_system"):
            embed = discord.Embed(
                title="Premium Feature",
                description="The leveling system is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Use mentioned user or command user
        target_user = user or interaction.user
        user_id = str(target_user.id)
        
        try:
            # Get user data
            user_data = await self.bot.db.levels.find_one({
                "guild_id": guild_id,
                "user_id": user_id
            })
            
            if not user_data:
                await interaction.response.send_message(f"{target_user.mention} hasn't earned any XP yet!", ephemeral=True)
                return
            
            current_xp = user_data["xp"]
            current_level = user_data["level"]
            
            # Calculate XP needed for next level
            xp_needed = 5 * (current_level ** 2) + 50 * current_level + 100
            
            # Get user rank (position)
            all_users = await self.bot.db.levels.find({"guild_id": guild_id}).sort("xp", -1).to_list(length=None)
            user_rank = next((i+1 for i, u in enumerate(all_users) if u["user_id"] == user_id), 0)
            
            # Generate rank card
            buffer = await self.generate_rank_card(target_user, current_level, current_xp, xp_needed, user_rank)
            
            if buffer:
                file = discord.File(buffer, filename="rank.png")
                await interaction.response.send_message(file=file)
            else:
                # Fallback to text response
                embed = discord.Embed(
                    title=f"{target_user.name}'s Rank",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Level", value=str(current_level), inline=True)
                embed.add_field(name="XP", value=f"{current_xp}/{xp_needed}", inline=True)
                embed.add_field(name="Rank", value=f"#{user_rank}", inline=True)
                embed.set_thumbnail(url=target_user.display_avatar.url)
                
                await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in rank command: {e}")
            await interaction.response.send_message("Error retrieving rank information.", ephemeral=True)
    
    async def generate_rank_card(self, user, level, current_xp, xp_needed, rank):
        """Generate a visual rank card"""
        try:
            # Create canvas
            card_width, card_height = 800, 200
            card = Image.new("RGBA", (card_width, card_height), (47, 49, 54, 255))
            draw = ImageDraw.Draw(card)
            
            # Load user avatar
            async with aiohttp.ClientSession() as session:
                avatar_url = user.display_avatar.url
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        avatar = Image.open(BytesIO(avatar_data)).convert("RGBA")
                        
                        # Make avatar circular
                        mask = Image.new("L", avatar.size, 0)
                        draw_mask = ImageDraw.Draw(mask)
                        draw_mask.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                        
                        # Resize avatar
                        avatar_size = 150
                        avatar = avatar.resize((avatar_size, avatar_size))
                        mask = mask.resize((avatar_size, avatar_size))
                        
                        # Position avatar
                        avatar_pos = (25, 25)
                        card.paste(avatar, avatar_pos, mask)
            
            # Load fonts
            try:
                name_font = ImageFont.truetype("./assets/fonts/Arial.ttf", 30)
                detail_font = ImageFont.truetype("./assets/fonts/Arial.ttf", 20)
            except:
                name_font = ImageFont.load_default()
                detail_font = ImageFont.load_default()
            
            # Draw user name
            draw.text((200, 30), user.name, fill=(255, 255, 255), font=name_font)
            
            # Draw level and rank
            draw.text((200, 70), f"Level: {level}", fill=(255, 255, 255), font=detail_font)
            draw.text((350, 70), f"Rank: #{rank}", fill=(255, 255, 255), font=detail_font)
            
            # Draw XP bar background
            bar_width = 550
            bar_height = 30
            bar_pos = (200, 120)
            draw.rectangle([bar_pos, (bar_pos[0] + bar_width, bar_pos[1] + bar_height)], fill=(100, 100, 100))
            
            # Draw XP progress
            if xp_needed > 0:
                progress = min(current_xp / xp_needed, 1.0)
                progress_width = int(bar_width * progress)
                
                if progress_width > 0:
                    draw.rectangle([
                        bar_pos,
                        (bar_pos[0] + progress_width, bar_pos[1] + bar_height)
                    ], fill=(114, 137, 218))  # Discord blurple color
            
            # Draw XP text
            xp_text = f"{current_xp}/{xp_needed} XP"
            draw.text((
                bar_pos[0] + bar_width // 2 - 40,
                bar_pos[1] + 5
            ), xp_text, fill=(255, 255, 255), font=detail_font)
            
            # Convert to bytes
            buffer = BytesIO()
            card.save(buffer, "PNG")
            buffer.seek(0)
            
            return buffer
        
        except Exception as e:
            logger.error(f"Error generating rank card: {e}")
            return None
    
    @app_commands.command(name="leaderboard", description="View the server's XP leaderboard")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction, page: int = 1):
        """Show server XP leaderboard"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "leveling_system"):
            embed = discord.Embed(
                title="Premium Feature",
                description="The leveling system is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Validate page number
            if page < 1:
                page = 1
            
            # Items per page
            items_per_page = 10
            skip_amount = (page - 1) * items_per_page
            
            # Get total count for pagination
            total_users = await self.bot.db.levels.count_documents({"guild_id": guild_id})
            max_pages = max(1, (total_users + items_per_page - 1) // items_per_page)
            
            if page > max_pages:
                page = max_pages
            
            # Get top users for current page
            top_users = await self.bot.db.levels.find({"guild_id": guild_id}) \
                .sort("xp", -1) \
                .skip(skip_amount) \
                .limit(items_per_page) \
                .to_list(length=None)
            
            if not top_users:
                await interaction.response.send_message("No XP data found for this server!", ephemeral=True)
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"{interaction.guild.name} Leaderboard",
                description=f"Top members by XP - Page {page}/{max_pages}",
                color=discord.Color.blue()
            )
            
            # Add leaderboard entries
            for i, user_data in enumerate(top_users, start=1 + skip_amount):
                user_id = int(user_data["user_id"])
                member = interaction.guild.get_member(user_id)
                name = member.name if member else f"User {user_id}"
                
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Level: {user_data['level']} | XP: {user_data['xp']}",
                    inline=False
                )
            
            # Add pagination controls (this would be UI buttons in a full implementation)
            embed.set_footer(text=f"Use /leaderboard [page] to navigate pages")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await interaction.response.send_message("Error retrieving leaderboard.", ephemeral=True)
    
    @app_commands.command(name="givexp", description="Give XP to a user (Admin only)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def givexp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Award XP to a user (admin only)"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "leveling_system"):
            embed = discord.Embed(
                title="Premium Feature",
                description="The leveling system is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need Administrator permission to use this command!", ephemeral=True)
            return
        
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message("XP amount must be positive!", ephemeral=True)
            return
        
        try:
            user_id = str(user.id)
            
            # Get current user data
            user_data = await self.bot.db.levels.find_one({
                "guild_id": guild_id,
                "user_id": user_id
            })
            
            if not user_data:
                # Create new user entry
                user_data = {
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "xp": 0,
                    "level": 0,
                    "last_message": datetime.datetime.now()
                }
            
            # Add XP
            current_xp = user_data["xp"] + amount
            current_level = user_data["level"]
            
            # Check for level ups
            while True:
                xp_needed = 5 * (current_level ** 2) + 50 * current_level + 100
                if current_xp < xp_needed:
                    break
                current_level += 1
            
            # Update database
            await self.bot.db.levels.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {
                    "xp": current_xp,
                    "level": current_level,
                    "last_message": datetime.datetime.now()
                }},
                upsert=True
            )
            
            await interaction.response.send_message(
                f"Added {amount} XP to {user.mention}. They are now level {current_level} with {current_xp} XP.",
                ephemeral=True
            )
        
        except Exception as e:
            logger.error(f"Error in givexp command: {e}")
            await interaction.response.send_message("Error awarding XP.", ephemeral=True)

class AdvancedModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_control = {}
        self.raid_detection = {}
        self.filter_cache = {}
        self.warned_users = {}
        self.profanity.load()  # Load default profanity list
    
    async def load_filters(self, guild_id):
        """Load custom word filters for a guild"""
        try:
            # Try to get from cache first
            if guild_id in self.filter_cache:
                return self.filter_cache[guild_id]
            
            # Get from database
            filter_data = await self.bot.db.word_filters.find_one({"guild_id": guild_id})
            
            if filter_data and "words" in filter_data:
                self.filter_cache[guild_id] = set(filter_data["words"])
                return self.filter_cache[guild_id]
            
            # Return empty set if not found
            return set()
        
        except Exception as e:
            logger.error(f"Error loading filters: {e}")
            return set()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages for moderation"""
        # Skip if DM or bot message
        if not message.guild or message.author.bot:
            return
            
        guild_id = str(message.guild.id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "advanced_moderation"):
            return
        
        try:
            # Get automod settings
            automod_settings = await self.bot.db.automod_settings.find_one({"guild_id": guild_id})
            
            if not automod_settings:
                return
            
            # Skip moderation for admins if configured
            if automod_settings.get("ignore_admins", True) and message.author.guild_permissions.administrator:
                return
            
            # Skip moderation for specific roles if configured
            if "ignored_roles" in automod_settings:
                author_roles = [str(role.id) for role in message.author.roles]
                if any(role_id in automod_settings["ignored_roles"] for role_id in author_roles):
                    return
            
            # Skip moderation in specific channels if configured
            if "ignored_channels" in automod_settings:
                if str(message.channel.id) in automod_settings["ignored_channels"]:
                    return
            
            # Word filter check
            if automod_settings.get("word_filter_enabled", False):
                await self.check_word_filter(message, automod_settings)
            
            # Anti-spam check
            if automod_settings.get("antispam_enabled", False):
                await self.check_spam(message, automod_settings)
            
            # Invite link filter
            if automod_settings.get("invite_filter_enabled", False):
                await self.check_invite_links(message, automod_settings)
            
            # URL filter
            if automod_settings.get("url_filter_enabled", False):
                await self.check_urls(message, automod_settings)
            
            # Mass mention filter
            if automod_settings.get("mass_mention_filter_enabled", False):
                await self.check_mass_mentions(message, automod_settings)
            
            # Raid protection
            if automod_settings.get("raid_protection_enabled", False):
                await self.check_raid(message.author, automod_settings)
        
        except Exception as e:
            logger.error(f"Error in automod: {e}")
    
    async def check_word_filter(self, message, settings):
        """Check message against word filter"""
        guild_id = str(message.guild.id)
        
        # Get custom filter words
        custom_filter = await self.load_filters(guild_id)
        
        # Check against default profanity if enabled
        if settings.get("use_default_profanity_filter", True):
            if profanity.contains_profanity(message.content):
                await self.take_action(message, "profanity", settings)
                return
        
        # Check against custom words
        if custom_filter:
            content_lower = message.content.lower()
            for word in custom_filter:
                if word.lower() in content_lower:
                    await self.take_action(message, "filtered_word", settings)
                    return
    
    async def check_spam(self, message, settings):
        """Check for message spam"""
        author_id = str(message.author.id)
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        
        # Create keys
        user_key = f"{guild_id}:{author_id}"
        channel_key = f"{guild_id}:{channel_id}"
        
        current_time = time.time()
        
        # Initialize if needed
        if user_key not in self.spam_control:
            self.spam_control[user_key] = []
        
        if channel_key not in self.spam_control:
            self.spam_control[channel_key] = []
        
        # Add current message timestamp
        self.spam_control[user_key].append(current_time)
        self.spam_control[channel_key].append(current_time)
        
        # Clean old entries (older than window)
        window = settings.get("spam_window", 5)  # Default 5 seconds
        self.spam_control[user_key] = [t for t in self.spam_control[user_key] if current_time - t <= window]
        self.spam_control[channel_key] = [t for t in self.spam_control[channel_key] if current_time - t <= window]
        
        # Check user spam threshold
        user_threshold = settings.get("user_spam_threshold", 5)  # Default 5 messages
        if len(self.spam_control[user_key]) >= user_threshold:
            await self.take_action(message, "user_spam", settings)
            # Reset after taking action
            self.spam_control[user_key] = []
            return
    
    async def check_invite_links(self, message, settings):
        """Check for Discord invite links"""
        # Use regex to find Discord invite links
        invite_pattern = r"(discord\.gg|discord\.com\/invite)\/[a-zA-Z0-9-]+"
        if re.search(invite_pattern, message.content, re.IGNORECASE):
            # Check whitelist if enabled
            if settings.get("whitelist_own_server_invites", True):
                # Get guild invites
                try:
                    guild_invites = await message.guild.invites()
                    guild_invite_codes = [invite.code for invite in guild_invites]
                    
                    # Extract codes from found invites
                    found_codes = []
                    for match in re.finditer(invite_pattern, message.content, re.IGNORECASE):
                        invite_url = match.group(0)
                        code = invite_url.split('/')[-1]
                        found_codes.append(code)
                    
                    # If all found codes are from this guild, allow
                    if all(code in guild_invite_codes for code in found_codes):
                        return
                except:
                    # If can't check invites, fall back to block
                    pass
            
            await self.take_action(message, "invite_link", settings)
    
    async def check_urls(self, message, settings):
        """Check for URLs"""
        # Use regex to find URLs
        url_pattern = r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
        if re.search(url_pattern, message.content):
            # Check allowlist domains if configured
            if "allowed_domains" in settings:
                allowed_domains = settings["allowed_domains"]
                
                # Extract domains from found URLs
                found_domains = []
                for match in re.finditer(url_pattern, message.content):
                    url = match.group(0)
                    # Simple domain extraction - could be more robust
                    domain = url.split('//')[1].split('/')[0]
                    if 'www.' in domain:
                        domain = domain.split('www.')[1]
                    found_domains.append(domain)
                
                # If all domains are allowed, return
                if all(any(domain.endswith(allowed) for allowed in allowed_domains) for domain in found_domains):
                    return
            
            await self.take_action(message, "url", settings)
    
    async def check_mass_mentions(self, message, settings):
        """Check for too many mentions"""
        # Count mentions
        mention_count = len(message.mentions) + len(message.role_mentions)
        
        # Get threshold
        threshold = settings.get("mention_threshold", 5)
        
        if mention_count >= threshold:
            await self.take_action(message, "mass_mention", settings)
    
    async def check_raid(self, member, settings):
        """Check for potential raid (many joins in short time)"""
        guild_id = str(member.guild.id)
        current_time = time.time()
        
        # Initialize if needed
        if guild_id not in self.raid_detection:
            self.raid_detection[guild_id] = []
        
        # Add current join
        self.raid_detection[guild_id].append(current_time)
        
        # Clean old entries
        window = settings.get("raid_window", 10)  # Default 10 seconds
        self.raid_detection[guild_id] = [t for t in self.raid_detection[guild_id] if current_time - t <= window]
        
        # Check threshold
        threshold = settings.get("raid_threshold", 10)  # Default 10 joins
        if len(self.raid_detection[guild_id]) >= threshold:
            # Enable raid mode
            await self.enable_raid_mode(member.guild, settings)
            # Reset
            self.raid_detection[guild_id] = []
    
    async def enable_raid_mode(self, guild, settings):
        """Enable anti-raid mode"""
        try:
            # Log the raid detection
            logger.warning(f"Raid detected in {guild.name} ({guild.id})!")
            
            # Get settings
            raid_action = settings.get("raid_action", "lockdown")
            raid_duration = settings.get("raid_duration", 300)  # Default 5 minutes
            
            if raid_action == "lockdown":
                # Lock down the server
                for channel in guild.text_channels:
                    try:
                        # Modify default role permissions to prevent sending messages
                        await channel.set_permissions(
                            guild.default_role,
                            send_messages=False,
                            reason="Raid protection lockdown"
                        )
                    except:
                        continue
                
                # Schedule unlock
                self.bot.loop.create_task(self.end_lockdown(guild, raid_duration))
                
                # Notify a log channel if configured
                if "log_channel" in settings:
                    try:
                        log_channel = guild.get_channel(int(settings["log_channel"]))
                        if log_channel:
                            embed = discord.Embed(
                                title="🚨 Raid Protection Activated",
                                description=f"Raid detected! Server has been locked down for {raid_duration // 60} minutes.",
                                color=discord.Color.red()
                            )
                            await log_channel.send(embed=embed)
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error enabling raid mode: {e}")
    
    async def end_lockdown(self, guild, duration):
        """End server lockdown after duration"""
        await asyncio.sleep(duration)
        
        try:
            # Unlock channels
            for channel in guild.text_channels:
                try:
                    # Reset to default permissions
                    await channel.set_permissions(
                        guild.default_role,
                        send_messages=None,  # Reset to role defaults
                        reason="Raid protection lockdown ended"
                    )
                except:
                    continue
            
            # Find log channel
            settings = await self.bot.db.automod_settings.find_one({"guild_id": str(guild.id)})
            if settings and "log_channel" in settings:
                try:
                    log_channel = guild.get_channel(int(settings["log_channel"]))
                    if log_channel:
                        embed = discord.Embed(
                            title="✅ Raid Protection Deactivated",
                            description="The server lockdown has been lifted.",
                            color=discord.Color.green()
                        )
                        await log_channel.send(embed=embed)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error ending lockdown: {e}")
    
    async def take_action(self, message, violation_type, settings):
        """Take configured action based on violation type"""
        try:
            # Default to warning
            action = settings.get(f"{violation_type}_action", "warn")
            
            # Log violation
            await self.log_violation(message, violation_type, action)
            
            # Take action based on configured setting
            if action == "delete":
                try:
                    await message.delete()
                except:
                    pass
            
            elif action == "warn":
                try:
                    await message.delete()
                except:
                    pass
                
                # Track warnings
                user_id = str(message.author.id)
                guild_id = str(message.guild.id)
                warning_key = f"{guild_id}:{user_id}"
                
                if warning_key not in self.warned_users:
                    self.warned_users[warning_key] = {"count": 0, "last_reset": time.time()}
                
                # Increment warning count
                self.warned_users[warning_key]["count"] += 1
                
                # Check for escalation
                warning_threshold = settings.get("warning_threshold", 3)
                warning_timeout = settings.get("warning_timeout", 3600)  # Default 1 hour
                escalation_action = settings.get("escalation_action", "mute")
                
                # Reset warnings if timeout elapsed
                current_time = time.time()
                if current_time - self.warned_users[warning_key]["last_reset"] > warning_timeout:
                    self.warned_users[warning_key] = {"count": 1, "last_reset": current_time}
                
                if self.warned_users[warning_key]["count"] >= warning_threshold:
                    # Reset count
                    self.warned_users[warning_key]["count"] = 0
                    
                    # Escalate action
                    await self.escalate_action(message.author, escalation_action, settings)
                else:
                    # Just send warning message
                    try:
                        warning = await message.channel.send(
                            f"{message.author.mention} Warning: Your message violated our {violation_type.replace('_', ' ')} policy."
                        )
                        # Delete warning after a few seconds
                        await asyncio.sleep(5)
                        await warning.delete()
                    except:
                        pass
            
            elif action == "mute":
                try:
                    await message.delete()
                except:
                    pass
                
                # Get mute duration
                mute_duration = settings.get("mute_duration", 300)  # Default 5 minutes
                await self.mute_user(message.author, mute_duration, violation_type)
            
            elif action == "kick":
                try:
                    await message.delete()
                except:
                    pass
                
                # Send DM notification if possible
                try:
                    await message.author.send(
                        f"You have been kicked from {message.guild.name} for violating our {violation_type.replace('_', ' ')} policy."
                    )
                except:
                    pass
                
                # Kick user
                await message.guild.kick(
                    message.author,
                    reason=f"AutoMod: {violation_type.replace('_', ' ')} violation"
                )
            
            elif action == "ban":
                try:
                    await message.delete()
                except:
                    pass
                
                # Send DM notification if possible
                try:
                    await message.author.send(
                        f"You have been banned from {message.guild.name} for violating our {violation_type.replace('_', ' ')} policy."
                    )
                except:
                    pass
                
                # Ban user
                await message.guild.ban(
                    message.author,
                    reason=f"AutoMod: {violation_type.replace('_', ' ')} violation",
                    delete_message_days=1
                )
        
        except Exception as e:
            logger.error(f"Error taking action: {e}")
    
    async def escalate_action(self, user, action, settings):
        """Escalate punishment after multiple warnings"""
        try:
            if action == "mute":
                # Get mute duration
                mute_duration = settings.get("escalation_mute_duration", 3600)  # Default 1 hour
                await self.mute_user(user, mute_duration, "repeated_violations")
            
            elif action == "kick":
                # Send DM notification if possible
                try:
                    await user.send(
                        f"You have been kicked from {user.guild.name} for repeated violations."
                    )
                except:
                    pass
                
                # Kick user
                await user.guild.kick(
                    user,
                    reason=f"AutoMod: Escalation after repeated violations"
                )
            
            elif action == "ban":
                # Send DM notification if possible
                try:
                    await user.send(
                        f"You have been banned from {user.guild.name} for repeated violations."
                    )
                except:
                    pass
                
                # Ban user
                await user.guild.ban(
                    user,
                    reason=f"AutoMod: Escalation after repeated violations",
                    delete_message_days=1
                )
        
        except Exception as e:
            logger.error(f"Error in escalation: {e}")
    
    async def mute_user(self, user, duration, reason):
        """Mute a user for specified duration"""
        try:
            # Get or create mute role
            mute_role = None
            
            # Check if mute role is configured
            guild_id = str(user.guild.id)
            settings = await self.bot.db.automod_settings.find_one({"guild_id": guild_id})
            
            if settings and "mute_role_id" in settings:
                mute_role = user.guild.get_role(int(settings["mute_role_id"]))
            
            # Create mute role if not found
            if not mute_role:
                # Create new role
                mute_role = await user.guild.create_role(
                    name="Muted",
                    reason="AutoMod: Created mute role"
                )
                
                # Set permissions to deny speaking in all channels
                for channel in user.guild.channels:
                    try:
                        overwrites = channel.overwrites_for(mute_role)
                        
                        if isinstance(channel, discord.TextChannel):
                            overwrites.send_messages = False
                            overwrites.add_reactions = False
                        elif isinstance(channel, discord.VoiceChannel):
                            overwrites.speak = False
                        
                        await channel.set_permissions(
                            mute_role,
                            overwrite=overwrites,
                            reason="AutoMod: Setting up mute role permissions"
                        )
                    except:
                        continue
                
                # Save mute role ID
                if settings:
                    await self.bot.db.automod_settings.update_one(
                        {"guild_id": guild_id},
                        {"$set": {"mute_role_id": str(mute_role.id)}}
                    )
                else:
                    await self.bot.db.automod_settings.insert_one({
                        "guild_id": guild_id,
                        "mute_role_id": str(mute_role.id)
                    })
            
            # Apply mute role
            await user.add_roles(mute_role, reason=f"AutoMod: {reason}")
            
            # Schedule unmute
            self.bot.loop.create_task(self.unmute_user(user, mute_role, duration))
            
            # Log mute
            if settings and "log_channel" in settings:
                try:
                    log_channel = user.guild.get_channel(int(settings["log_channel"]))
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 User Muted",
                            description=f"{user.mention} has been muted for {duration // 60} minutes.",
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="Reason", value=reason)
                        await log_channel.send(embed=embed)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error muting user: {e}")
    
    async def unmute_user(self, user, mute_role, duration):
        """Unmute user after duration"""
        await asyncio.sleep(duration)
        
        try:
            if user.guild and user in user.guild.members:
                # Remove mute role
                if mute_role in user.roles:
                    await user.remove_roles(mute_role, reason="AutoMod: Mute duration expired")
                    
                    # Log unmute
                    guild_id = str(user.guild.id)
                    settings = await self.bot.db.automod_settings.find_one({"guild_id": guild_id})
                    
                    if settings and "log_channel" in settings:
                        try:
                            log_channel = user.guild.get_channel(int(settings["log_channel"]))
                            if log_channel:
                                embed = discord.Embed(
                                    title="🔊 User Unmuted",
                                    description=f"{user.mention} has been automatically unmuted.",
                                    color=discord.Color.green()
                                )
                                await log_channel.send(embed=embed)
                        except:
                            pass
        except Exception as e:
            logger.error(f"Error unmuting user: {e}")
    
    async def log_violation(self, message, violation_type, action):
        """Log moderation action to database and log channel"""
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Store in database
        log_entry = {
            "guild_id": guild_id,
            "user_id": user_id,
            "username": message.author.name,
            "channel_id": str(message.channel.id),
            "channel_name": message.channel.name,
            "violation_type": violation_type,
            "action_taken": action,
            "message_content": message.content,
            "timestamp": datetime.datetime.now()
        }
        
        await self.bot.db.mod_logs.insert_one(log_entry)
        
        # Send to log channel
        settings = await self.bot.db.automod_settings.find_one({"guild_id": guild_id})
        
        if settings and "log_channel" in settings:
            try:
                log_channel = message.guild.get_channel(int(settings["log_channel"]))
                if log_channel:
                    embed = discord.Embed(
                        title="🛡️ AutoMod Action",
                        color=discord.Color.red()
                    )
                    
                    embed.add_field(name="User", value=f"{message.author.mention} ({message.author.name})")
                    embed.add_field(name="Channel", value=f"{message.channel.mention}")
                    embed.add_field(name="Violation", value=violation_type.replace("_", " ").title())
                    embed.add_field(name="Action", value=action.title())
                    
                    # Truncate message content if too long
                    content = message.content
                    if len(content) > 1024:
                        content = content[:1021] + "..."
                    
                    embed.add_field(name="Message", value=content, inline=False)
                    embed.set_footer(text=f"User ID: {user_id}")
                    embed.timestamp = datetime.datetime.now()
                    
                    await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Error sending to log channel: {e}")
    
    @app_commands.command(name="automod", description="Configure automod settings")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def automod_config(self, interaction: discord.Interaction):
        """Configure automod settings"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "advanced_moderation"):
            embed = discord.Embed(
                title="Premium Feature",
                description="Advanced moderation is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # This would be a custom UI view with buttons and select menus
        # For brevity, not implementing the full UI here
        await interaction.response.send_message("Opening automod configuration menu...", ephemeral=True)
    
    @app_commands.command(name="filter", description="Add or remove words from the filter")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def filter_word(self, interaction: discord.Interaction, action: str, word: str):
        """Add or remove words from the filter"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "advanced_moderation"):
            embed = discord.Embed(
                title="Premium Feature",
                description="Advanced moderation is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Validate action
        action = action.lower()
        if action not in ["add", "remove"]:
            await interaction.response.send_message("Action must be either 'add' or 'remove'.", ephemeral=True)
            return
        
        try:
            # Get current filter list
            filter_words = await self.load_filters(guild_id)
            
            if action == "add":
                # Add word to filter
                filter_words.add(word.lower())
                
                await self.bot.db.word_filters.update_one(
                    {"guild_id": guild_id},
                    {"$addToSet": {"words": word.lower()}},
                    upsert=True
                )
                
                await interaction.response.send_message(f"Added '{word}' to the filter.", ephemeral=True)
            
            else:  # remove
                # Remove word from filter
                if word.lower() in filter_words:
                    filter_words.remove(word.lower())
                    
                    await self.bot.db.word_filters.update_one(
                        {"guild_id": guild_id},
                        {"$pull": {"words": word.lower()}}
                    )
                    
                    await interaction.response.send_message(f"Removed '{word}' from the filter.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"'{word}' is not in the filter.", ephemeral=True)
            
            # Update cache
            self.filter_cache[guild_id] = filter_words
            
        except Exception as e:
            logger.error(f"Error updating filter: {e}")
            await interaction.response.send_message("Error updating filter.", ephemeral=True)
    
    @app_commands.command(name="modlogs", description="View moderation logs for a user")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def mod_logs(self, interaction: discord.Interaction, user: discord.Member, page: int = 1):
        """View moderation logs for a user"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status and this feature
        if not self.bot.has_feature(guild_id, "advanced_moderation"):
            embed = discord.Embed(
                title="Premium Feature",
                description="Advanced moderation is a premium feature. Upgrade to premium to use it!",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Validate page number
            if page < 1:
                page = 1
            
            # Items per page  
            items_per_page = 5
            skip_amount = (page - 1) * items_per_page
            
            # Get logs for the user
            total_logs = await self.bot.db.mod_logs.count_documents({
                "guild_id": guild_id,
                "user_id": str(user.id)
            })
            
            max_pages = max(1, (total_logs + items_per_page - 1) // items_per_page)
            
            if page > max_pages:
                page = max_pages
            
            logs = await self.bot.db.mod_logs.find({
                "guild_id": guild_id,
                "user_id": str(user.id)
            }).sort("timestamp", -1).skip(skip_amount).limit(items_per_page).to_list(length=None)
            
            if not logs:
                await interaction.response.send_message(f"No moderation logs found for {user.mention}.", ephemeral=True)
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"Moderation Logs for {user.name}",
                description=f"Page {page}/{max_pages}",
                color=discord.Color.blue()
            )
            
            # Add log entries
            for log in logs:
                timestamp = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                
                embed.add_field(
                    name=f"{timestamp} - {log['violation_type'].replace('_', ' ').title()}",
                    value=f"Action: {log['action_taken'].title()}\nChannel: <#{log['channel_id']}>\nMessage: {log['message_content'][:100] + '...' if len(log['message_content']) > 100 else log['message_content']}",
                    inline=False
                )
            
            # Add pagination controls (this would be UI buttons in a full implementation)
            embed.set_footer(text=f"Use /modlogs @user [page] to navigate pages")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error retrieving mod logs: {e}")
            await interaction.response.send_message("Error retrieving moderation logs.", ephemeral=True)

class MusicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.node_connected = False
        self.queue = {}
        self.volume = {}
        self.now_playing = {}
        self.repeat_mode = {}  # 0: off, 1: one, 2: all
    
    async def cog_load(self):
        """Setup wavelink nodes when cog loads"""
        self.bot.loop.create_task(self.connect_nodes())
    
    async def connect_nodes(self):
        """Connect to Lavalink nodes"""
        await self.bot.wait_until_ready()
        
        try:
            # Wavelink 2.0 node setup
            await wavelink.NodePool.create_node(
                bot=self.bot,
                host='127.0.0.1',  # Lavalink server address
                port=2333,
                password='youshallnotpass',
                https=False
            )
            logger.info("Connected to Lavalink node")
        except Exception as e:
            logger.error(f"Failed to connect to Lavalink node: {e}")
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when wavelink node is ready"""
        logger.info(f"Node {node.identifier} is ready!")
        self.node_connected = True
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):
        """Handle track end event"""
        guild_id = str(player.guild.id)
        
        # Skip processing if not set up
        if guild_id not in self.queue or guild_id not in self.repeat_mode:
            return
        
        # Handle repeat mode
        if self.repeat_mode[guild_id] == 1:  # Repeat single track
            await player.play(track)
            return
            
        # Get next track
        if not self.queue[guild_id]:
            # Queue is empty
            self.now_playing[guild_id] = None
            
            if player.channel:
                await player.channel.send("Queue ended. Add more songs with `/play`!")
            return
            
        if self.repeat_mode[guild_id] == 2:  # Repeat queue
            # Move current track to end of queue
            self.queue[guild_id].append(track)
            
        # Play next track
        next_track = self.queue[guild_id].pop(0)
        self.now_playing[guild_id] = next_track
        
        await player.play(next_track)
        
        # Send now playing message
        if player.channel:
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{next_track.title}]({next_track.uri})",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Duration", value=format_time(next_track.duration // 1000))
            embed.add_field(name="Requested By", value=next_track.info['requester'])
            
            await player.channel.send(embed=embed)
    
    @app_commands.command(name="play", description="Play a song")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song in your voice channel"""
        guild_id = str(interaction.guild_id)
        
        # Check if guild has premium status for advanced features
        has_premium = self.bot.has_feature(guild_id, "music_player")
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel to use this command.", ephemeral=True)
            return
        
        voice_channel = interaction.user.voice.channel
        
        # Check if bot already in a different channel
        if interaction.guild.voice_client and interaction.guild.voice_client.channel != voice_channel:
            await interaction.response.send_message("I'm already playing in another voice channel.", ephemeral=True)
            return
        
        # Defer response due to potential API requests
        await interaction.response.defer()
        
        try:
            # Initialize queue and other settings if not exists
            if guild_id not in self.queue:
                self.queue[guild_id] = []
            
            if guild_id not in self.volume:
                self.volume[guild_id] = 100
                
            if guild_id not in self.repeat_mode:
                self.repeat_mode[guild_id] = 0
            
            # Connect to voice channel if not already connected
            player = interaction.guild.voice_client
            
            if not player:
                player = await voice_channel.connect(cls=wavelink.Player)
                player.channel = interaction.channel  # For notifications
            
            # Search for track
            if query.startswith(('http://', 'https://')):
                # Direct URL
                search_type = wavelink.SearchType.SEARCH if 'youtube.com' in query or 'youtu.be' in query else None
                tracks = await wavelink.NodePool.get_node().get_tracks(query=query, cls=wavelink.Track, search_type=search_type)
                
                if not tracks:
                    await interaction.followup.send("No tracks found for that URL.", ephemeral=True)
                    return
                
                if isinstance(tracks, wavelink.Playlist):
                    # Process playlist
                    for track in tracks.tracks:
                        track.info['requester'] = interaction.user.name
                        self.queue[guild_id].append(track)
                    
                    await interaction.followup.send(f"Added {len(tracks.tracks)} tracks from playlist **{tracks.name}** to the queue.")
                else:
                    # Single track
                    track = tracks[0]
                    track.info['requester'] = interaction.user.name
                    
                    if not player.is_playing():
                        # Play immediately if nothing is playing
                        self.now_playing[guild_id] = track
                        await player.play(track)
                        
                        # Set volume
                        await player.set_volume(self.volume[guild_id])
                        
                        embed = discord.Embed(
                            title="🎵 Now Playing",
                            description=f"[{track.title}]({track.uri})",
                            color=discord.Color.blue()
                        )
                        
                        embed.add_field(name="Duration", value=format_time(track.duration // 1000))
                        embed.add_field(name="Requested By", value=track.info['requester'])
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        # Add to queue
                        self.queue[guild_id].append(track)
                        
                        await interaction.followup.send(
                            f"Added **{track.title}** to the queue at position #{len(self.queue[guild_id])}"
                        )
            else:
                # Search query
                search_prefix = "ytsearch:" if not has_premium else ""  # Premium can search multiple platforms
                tracks = await wavelink.NodePool.get_node().get_tracks(
                    query=f"{search_prefix}{query}", cls=wavelink.Track
                )
                
                if not tracks:
                    await interaction.followup.send("No tracks found for that query.", ephemeral=True)
                    return
                
                # Get first result
                track = tracks[0]
                track.info['requester'] = interaction.user.name
                
                if not player.is_playing():
                    # Play immediately if nothing is playing
                    self.now_playing[guild_id] = track
                    await player.play(track)
                    
                    # Set volume
                    await player.set_volume(self.volume[guild_id])
                    
                    embed = discord.Embed(
                        title="🎵 Now Playing",
                        description=f"[{track.title}]({track.uri})",
                        color=discord.Color.blue()
                    )
                    
                    embed.add_field(name="Duration", value=format_time(track.duration // 1000))
                    embed.add_field(name="Requested By", value=track.info['requester'])
                    
                    await interaction.followup.send(embed=embed)
                else:
                    # Add to queue
                    self.queue[guild_id].append(track)
                    
                    await interaction.followup.send(
                        f"Added **{track.title}** to the queue at position #{len(self.queue[guild_id])}"
                    )
            
        except wavelink.LavalinkException as e:
            await interaction.followup.send(f"Error playing track: {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
    
    @app_commands.command(name="queue", description="Display the current queue")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        """Display the current queue"""
        guild_id = str(interaction.guild_id)
        
        # Check if there's an active player
        if not interaction.guild.voice_client or guild_id not in self.queue:
            await interaction.response.send_message("No active music player found.", ephemeral=True)
            return
        
        try:
            # Validate page number
            if page < 1:
                page = 1
            
            # Items per page
            items_per_page = 10
            queue_list = self.queue[guild_id]
            
            # Calculate pages
            max_pages = max(1, (len(queue_list) + items_per_page - 1) // items_per_page)
            
            if page > max_pages:
                page = max_pages
            
            # Create embed
            embed = discord.Embed(
                title="🎵 Music Queue",
                description=f"Page {page}/{max_pages}",
                color=discord.Color.blue()
            )
            
            # Add now playing
            if guild_id in self.now_playing and self.now_playing[guild_id]:
                current = self.now_playing[guild_id]
                embed.add_field(
                    name="🎵 Now Playing",
                    value=f"[{current.title}]({current.uri}) | Requested by: {current.info['requester']}",
                    inline=False
                )
            
            # Calculate start and end indices
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(queue_list))
            
            # Add queue items
            if queue_list:
                queue_text = []
                
                for i in range(start_idx, end_idx):
                    track = queue_list[i]
                    queue_text.append(
                        f"{i+1}. [{track.title}]({track.uri}) | {format_time(track.duration // 1000)} | Requested by: {track.info['requester']}"
                    )
                
                embed.add_field(
                    name="📜 Queue",
                    value="\n".join(queue_text) if queue_text else "Queue is empty",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📜 Queue",
                    value="Queue is empty",
                    inline=False
                )
            
            # Add info about queue
            total_duration = sum(track.duration for track in queue_list) // 1000
            embed.add_field(name="Songs in queue", value=str(len(queue_list)), inline=True)
            embed.add_field(name="Total duration", value=format_time(total_duration), inline=True)
            
            # Add repeat mode status
            repeat_status = "Off"
            if guild_id in self.repeat_mode:
                if self.repeat_mode[guild_id] == 1:
                    repeat_status = "Current song"
                elif self.repeat_mode[guild_id] == 2:
                    repeat_status = "Queue"
            
            embed.add_field(name="Repeat mode", value=repeat_status, inline=True)
            
            # Add pagination controls (this would be UI buttons in a full implementation)
            embed.set_footer(text=f"Use /queue [page] to navigate pages")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error displaying queue: {e}")
            await interaction.response.send_message("Error displaying queue.", ephemeral=True)
    
    @app_commands.command(name="skip", description="Skip the current song")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel to use this command.", ephemeral=True)
            return
        
        # Check if bot is playing something
        player = interaction.guild.voice_client
        if not player or not player.is_playing():
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return
        
        # Check if user is in the same channel as the bot
        if player.channel != interaction.user.voice.channel:
            await interaction.response.send_message("You need to be in the same voice channel as the bot.", ephemeral=True)
            return
        
        # Skip current track
        await interaction.response.send_message("⏭️ Skipping to next track...")
        await player.stop()
    
    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        """Stop playback and clear the queue"""
        guild_id = str(interaction.guild_id)
        
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("You need to be in a voice channel to use this command.", ephemeral=True)
            return
        
        # Check if bot is in a voice channel
        player = interaction.guild.voice_client
        if