# DiscordBotPro - A Comprehensive Discord Bot with Free and Premium Features
# Author: Claude
# Date: April 18, 2025

import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import random
import json
import os
import datetime
import logging
import sqlite3
import time
import yaml
import re
import wavelink
import motor.motor_asyncio
import traceback
import typing
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import matplotlib.pyplot as plt
import humanfriendly
import psutil
import itertools
from typing import Optional, List, Dict, Union, Any
from contextlib import contextmanager
from collections import defaultdict, Counter, deque
from functools import wraps

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')
WAVELINK_URI = os.getenv('WAVELINK_URI')
WAVELINK_PASSWORD = os.getenv('WAVELINK_PASSWORD')
PREMIUM_BOT_KEY = os.getenv('PREMIUM_BOT_KEY')

# Intents Setup
intents = discord.Intents.all()

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("discord_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DiscordBotPro')

# Initialize Bot
bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents, case_insensitive=True)

# Constants
EMBED_COLOR = 0x3498db
ERROR_COLOR = 0xe74c3c
SUCCESS_COLOR = 0x2ecc71
WARNING_COLOR = 0xf1c40f
INFO_COLOR = 0x3498db
PREMIUM_COLOR = 0x9b59b6

# Database Setup
class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client.discord_bot
        self.users = self.db.users
        self.guilds = self.db.guilds
        self.economy = self.db.economy
        self.leveling = self.db.leveling
        self.music = self.db.music
        self.tickets = self.db.tickets
        self.moderation = self.db.moderation
        self.premium = self.db.premium
        self.stats = self.db.stats
        logger.info("Connected to MongoDB")
        
    async def get_user(self, user_id: int):
        return await self.users.find_one({"_id": user_id})
    
    async def update_user(self, user_id: int, data: dict):
        await self.users.update_one({"_id": user_id}, {"$set": data}, upsert=True)
    
    async def get_guild(self, guild_id: int):
        return await self.guilds.find_one({"_id": guild_id})
    
    async def update_guild(self, guild_id: int, data: dict):
        await self.guilds.update_one({"_id": guild_id}, {"$set": data}, upsert=True)
    
    async def get_economy(self, user_id: int):
        return await self.economy.find_one({"_id": user_id})
    
    async def update_economy(self, user_id: int, data: dict):
        await self.economy.update_one({"_id": user_id}, {"$set": data}, upsert=True)
    
    async def get_level(self, user_id: int, guild_id: int):
        return await self.leveling.find_one({"user_id": user_id, "guild_id": guild_id})
    
    async def update_level(self, user_id: int, guild_id: int, data: dict):
        await self.leveling.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {"$set": data},
            upsert=True
        )
    
    async def get_premium(self, guild_id: int):
        return await self.premium.find_one({"_id": guild_id})
    
    async def update_premium(self, guild_id: int, data: dict):
        await self.premium.update_one({"_id": guild_id}, {"$set": data}, upsert=True)
    
    async def is_premium(self, guild_id: int) -> bool:
        data = await self.get_premium(guild_id)
        if not data:
            return False
        return data.get("active", False) and data.get("expiry", 0) > time.time()
    
    async def get_ticket(self, ticket_id: str):
        return await self.tickets.find_one({"_id": ticket_id})
    
    async def update_ticket(self, ticket_id: str, data: dict):
        await self.tickets.update_one({"_id": ticket_id}, {"$set": data}, upsert=True)
    
    async def get_guild_tickets(self, guild_id: int):
        return await self.tickets.find({"guild_id": guild_id}).to_list(length=100)
    
    async def get_moderation_case(self, case_id: int, guild_id: int):
        return await self.moderation.find_one({"case_id": case_id, "guild_id": guild_id})
    
    async def create_moderation_case(self, case_data: dict):
        await self.moderation.insert_one(case_data)
    
    async def get_user_cases(self, user_id: int, guild_id: int):
        return await self.moderation.find({"user_id": user_id, "guild_id": guild_id}).to_list(length=100)
    
    async def increment_stats(self, stat_name: str, amount: int = 1):
        await self.stats.update_one(
            {"_id": "bot_stats"},
            {"$inc": {stat_name: amount}},
            upsert=True
        )
    
    async def get_stats(self):
        return await self.stats.find_one({"_id": "bot_stats"})

# Initialize Database
db = Database()

# Premium Decorator
def premium_only():
    async def predicate(ctx):
        is_premium = await db.is_premium(ctx.guild.id)
        if not is_premium:
            embed = discord.Embed(
                title="⭐ Premium Feature",
                description="This feature is only available to premium servers. Use `!premium` to learn more.",
                color=PREMIUM_COLOR
            )
            await ctx.send(embed=embed)
            return False
        return True
    return commands.check(predicate)

# Error Handler
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Command is missing a required argument: `{error.param.name}`",
            color=ERROR_COLOR
        )
        await ctx.send(embed=embed)
        return
    
    if isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ Invalid Argument",
            description=str(error),
            color=ERROR_COLOR
        )
        await ctx.send(embed=embed)
        return
    
    if isinstance(error, commands.CheckFailure):
        if "premium_only" in str(error):
            # Already handled by the decorator
            return
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You don't have permission to use this command.",
            color=ERROR_COLOR
        )
        await ctx.send(embed=embed)
        return
    
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Cooldown",
            description=f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
            color=WARNING_COLOR
        )
        await ctx.send(embed=embed)
        return
    
    # Log the error
    logger.error(f"Command error in {ctx.command}: {error}")
    logger.error(traceback.format_exc())
    
    # Notify user
    embed = discord.Embed(
        title="❌ Error",
        description="An unexpected error occurred while running this command.",
        color=ERROR_COLOR
    )
    await ctx.send(embed=embed)

# Bot Events
@bot.event
async def on_ready():
    logger.info(f"Bot connected as {bot.user.name} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!help | Premium Bot"))
    
    # Start background tasks
    update_stats.start()
    check_premium_status.start()
    
    # Connect to Wavelink nodes
    try:
        nodes = [
            wavelink.Node(uri=WAVELINK_URI, password=WAVELINK_PASSWORD),
        ]
        await wavelink.Pool.connect(nodes=nodes, client=bot)
        logger.info("Connected to Wavelink nodes")
    except Exception as e:
        logger.error(f"Failed to connect to Wavelink nodes: {e}")

@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    logger.info(f"Wavelink node {node.identifier} ready")

@bot.event
async def on_guild_join(guild):
    logger.info(f"Bot joined guild: {guild.name} ({guild.id})")
    
    # Create default guild config
    default_config = {
        "welcome_channel": None,
        "welcome_message": "Welcome {user} to {server}!",
        "farewell_message": "Goodbye {user}, we'll miss you!",
        "autorole": None,
        "prefix": "!",
        "moderation": {
            "log_channel": None,
            "mute_role": None
        },
        "join_date": datetime.datetime.utcnow(),
        "premium_trial_used": False
    }
    
    await db.update_guild(guild.id, default_config)
    await db.increment_stats("guilds_joined")
    
    # Try to send welcome message to system channel
    try:
        if guild.system_channel:
            embed = discord.Embed(
                title=f"Thanks for adding {bot.user.name}!",
                description=f"Hello {guild.name}! I'm a feature-rich Discord bot with moderation, economy, music, and more!\n\nUse `!help` to see all my commands.",
                color=EMBED_COLOR
            )
            embed.add_field(name="🛡️ Setup", value="Start by using `!setup` to configure me", inline=False)
            embed.add_field(name="⭐ Premium", value="Check out `!premium` to see exclusive features", inline=False)
            embed.set_footer(text="Made with ❤️ by Claude")
            await guild.system_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send welcome message to guild {guild.id}: {e}")

@bot.event
async def on_guild_remove(guild):
    logger.info(f"Bot removed from guild: {guild.name} ({guild.id})")
    await db.increment_stats("guilds_left")

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return
    
    # Process commands
    await bot.process_commands(message)
    
    # Only process further for guild messages
    if not message.guild:
        return
    
    # XP System
    await add_xp(message.author, message.guild)
    
    # AFK Check
    await check_afk(message)
    
    # Auto-mod features can be added here

# Background Tasks
@tasks.loop(minutes=30)
async def update_stats():
    logger.info("Updating bot statistics")
    stats = {
        "guilds": len(bot.guilds),
        "users": len(bot.users),
        "commands_run": bot.command_count if hasattr(bot, "command_count") else 0,
        "last_updated": datetime.datetime.utcnow()
    }
    await db.update_stats(stats)

@tasks.loop(hours=12)
async def check_premium_status():
    logger.info("Checking premium status of guilds")
    async for premium_data in db.premium.find({"active": True}):
        guild_id = premium_data["_id"]
        expiry = premium_data.get("expiry", 0)
        
        if expiry < time.time():
            # Premium expired
            await db.update_premium(guild_id, {"active": False})
            logger.info(f"Premium expired for guild {guild_id}")
            
            guild = bot.get_guild(guild_id)
            if guild and guild.system_channel:
                embed = discord.Embed(
                    title="⭐ Premium Expired",
                    description="Your server's premium subscription has expired. Renew with `!premium renew` to continue enjoying premium features!",
                    color=WARNING_COLOR
                )
                try:
                    await guild.system_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send premium expiry message to guild {guild_id}: {e}")

# Utility Functions
async def add_xp(user, guild, amount=None):
    if amount is None:
        amount = random.randint(5, 15)
    
    user_level_data = await db.get_level(user.id, guild.id)
    
    if not user_level_data:
        user_level_data = {
            "user_id": user.id,
            "guild_id": guild.id,
            "xp": amount,
            "level": 0,
            "last_message": time.time()
        }
    else:
        # Check if user can earn XP (cooldown of 60 seconds)
        if time.time() - user_level_data.get("last_message", 0) < 60:
            return
        
        user_level_data["xp"] += amount
        user_level_data["last_message"] = time.time()
    
    # Calculate level
    current_level = user_level_data["level"]
    new_level = int(0.1 * (user_level_data["xp"] ** 0.5))
    
    user_level_data["level"] = new_level
    await db.update_level(user.id, guild.id, user_level_data)
    
    # Level up message
    if new_level > current_level:
        guild_data = await db.get_guild(guild.id)
        level_channel_id = guild_data.get("level_channel") if guild_data else None
        
        if level_channel_id:
            channel = bot.get_channel(level_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{user.mention} has reached level **{new_level}**!",
                    color=SUCCESS_COLOR
                )
                await channel.send(embed=embed)

async def check_afk(message):
    # Check if the author is AFK
    author_data = await db.get_user(message.author.id)
    if author_data and author_data.get("afk"):
        await db.update_user(message.author.id, {"afk": None})
        try:
            await message.channel.send(f"Welcome back {message.author.mention}! Your AFK status has been removed.")
        except:
            pass
    
    # Check for mentioned users who are AFK
    for mention in message.mentions:
        user_data = await db.get_user(mention.id)
        if user_data and user_data.get("afk"):
            afk_time = user_data["afk"]["time"]
            afk_reason = user_data["afk"]["reason"]
            time_ago = humanfriendly.format_timespan(time.time() - afk_time)
            
            embed = discord.Embed(
                title="⚠️ User is AFK",
                description=f"{mention.display_name} is AFK: {afk_reason} - {time_ago} ago",
                color=WARNING_COLOR
            )
            await message.channel.send(embed=embed)

def generate_level_image(user, level_data):
    # This would create a fancy level card image
    # For brevity, I'll just outline the logic
    background = Image.new('RGBA', (500, 150), (44, 47, 51, 255))
    draw = ImageDraw.Draw(background)
    
    # Draw user avatar
    # Draw XP bar
    # Draw level text
    # Add username
    
    buffer = BytesIO()
    background.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

# Help Command
bot.remove_command('help')  # Remove default help command

@bot.group(invoke_without_command=True)
async def help(ctx, command=None):
    """Shows help about the bot, a command, or a category"""
    if command is None:
        embed = discord.Embed(
            title=f"{bot.user.name} Help",
            description="Here are all the available command categories:",
            color=EMBED_COLOR
        )
        
        # List all cogs/categories
        categories = {
            "⚙️ General": ["help", "ping", "info", "invite", "setup"],
            "🔨 Moderation": ["ban", "kick", "mute", "warn", "infractions"],
            "💰 Economy": ["balance", "daily", "work", "shop", "inventory"],
            "🎵 Music": ["play", "skip", "queue", "now", "volume"],
            "📊 Leveling": ["rank", "leaderboard", "rewards"],
            "🎫 Tickets": ["ticket", "close", "transcript"],
            "⭐ Premium": ["premium", "perks", "redeem"]
        }
        
        for category, commands in categories.items():
            embed.add_field(
                name=category,
                value=f"`!help {category.split(' ')[1].lower()}`",
                inline=True
            )
            
        embed.set_footer(text="Use !help <command> to get more info on a specific command")
        await ctx.send(embed=embed)
    else:
        cmd = bot.get_command(command)
        if cmd:
            embed = discord.Embed(
                title=f"Command: {cmd.name}",
                description=cmd.help or "No description available",
                color=EMBED_COLOR
            )
            
            # Add usage, aliases, etc.
            if cmd.usage:
                embed.add_field(name="Usage", value=f"`!{cmd.name} {cmd.usage}`", inline=False)
            else:
                embed.add_field(name="Usage", value=f"`!{cmd.name}`", inline=False)
                
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join([f"`{alias}`" for alias in cmd.aliases]), inline=False)
                
            await ctx.send(embed=embed)
        else:
            # Check if it's a category
            category = command.capitalize()
            if category in ["General", "Moderation", "Economy", "Music", "Leveling", "Tickets", "Premium"]:
                embed = discord.Embed(
                    title=f"{category} Commands",
                    description=f"Here are the {category.lower()} commands:",
                    color=EMBED_COLOR
                )
                
                # This is simplified - you'd need to filter commands by category
                commands_in_category = []
                for cmd in bot.commands:
                    if hasattr(cmd, "category") and cmd.category.lower() == category.lower():
                        commands_in_category.append(cmd)
                
                if commands_in_category:
                    for cmd in commands_in_category:
                        embed.add_field(
                            name=cmd.name,
                            value=cmd.help or "No description",
                            inline=False
                        )
                else:
                    embed.description = "No commands found in this category."
                
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Command Not Found",
                    description=f"Command or category `{command}` not found.\nUse `!help` to see all commands.",
                    color=ERROR_COLOR
                )
                await ctx.send(embed=embed)

# General Commands
@bot.command()
async def ping(ctx):
    """Check the bot's latency"""
    start_time = time.time()
    message = await ctx.send("Pinging...")
    end_time = time.time()
    
    api_latency = round(bot.latency * 1000)
    response_time = round((end_time - start_time) * 1000)
    
    embed = discord.Embed(title="🏓 Pong!", color=EMBED_COLOR)
    embed.add_field(name="API Latency", value=f"{api_latency}ms", inline=True)
    embed.add_field(name="Response Time", value=f"{response_time}ms", inline=True)
    
    await message.edit(content=None, embed=embed)
    await db.increment_stats("commands_used")

@bot.command()
async def info(ctx):
    """Display information about the bot"""
    embed = discord.Embed(
        title=f"{bot.user.name} Information",
        description="A professional Discord bot with moderation, economy, music, and more!",
        color=EMBED_COLOR
    )
    
    # Bot stats
    total_users = sum(guild.member_count for guild in bot.guilds)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Users", value=str(total_users), inline=True)
    embed.add_field(name="Commands", value=str(len(bot.commands)), inline=True)
    
    # System stats
    uptime = datetime.datetime.utcnow() - bot.uptime if hasattr(bot, "uptime") else "Unknown"
    cpu_usage = psutil.cpu_percent()
    mem = psutil.virtual_memory()
    mem_usage = mem.percent
    
    embed.add_field(name="Uptime", value=str(uptime).split('.')[0], inline=True)
    embed.add_field(name="CPU Usage", value=f"{cpu_usage}%", inline=True)
    embed.add_field(name="Memory Usage", value=f"{mem_usage}%", inline=True)
    
    embed.add_field(name="Creator", value="Made with ❤️ by Claude", inline=False)
    embed.add_field(name="Premium", value="Use `!premium` to check out premium features!", inline=False)
    
    embed.set_footer(text="Thank you for using our bot!")
    embed.set_thumbnail(url=bot.user.avatar.url)
    
    await ctx.send(embed=embed)
    await db.increment_stats("commands_used")

@bot.command()
async def invite(ctx):
    """Get an invite link for the bot"""
    permissions = discord.Permissions(
        administrator=False,
        manage_roles=True,
        manage_channels=True,
        kick_members=True,
        ban_members=True,
        manage_messages=True,
        read_messages=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        add_reactions=True,
        connect=True,
        speak=True
    )
    
    invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions)
    
    embed = discord.Embed(
        title="📨 Invite Me",
        description=f"[Click here to invite me to your server]({invite_url})",
        color=EMBED_COLOR
    )
    embed.add_field(name="⭐ Premium", value="Use `!premium` to check out premium features!", inline=False)
    
    await ctx.send(embed=embed)
    await db.increment_stats("commands_used")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Interactive setup for the bot"""
    embed = discord.Embed(
        title="🛠️ Bot Setup",
        description="Let's set up the bot for your server! Please choose an option below:",
        color=EMBED_COLOR
    )
    
    embed.add_field(
        name="Categories",
        value="1️⃣ Welcome System\n2️⃣ Moderation\n3️⃣ Leveling\n4️⃣ Economy\n5️⃣ Tickets\n❌ Cancel Setup",
        inline=False
    )
    
    setup_msg = await ctx.send(embed=embed)
    options = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "❌"]
    
    for option in options:
        await setup_msg.add_reaction(option)
    
    try:
        reaction, user = await bot.wait_for(
            "reaction_add",
            check=lambda r, u: u == ctx.author and str(r.emoji) in options and r.message.id == setup_msg.id,
            timeout=60.0
        )
        
        await setup_msg.delete()
        
        if str(reaction.emoji) == "❌":
            await ctx.send("Setup cancelled.")
            return
        
        if str(reaction.emoji) == "1️⃣":
            await welcome_setup(ctx)
        elif str(reaction.emoji) == "2️⃣":
            await moderation_setup(ctx)
        elif str(reaction.emoji) == "3️⃣":
            await leveling_setup(ctx)
        elif str(reaction.emoji) == "4️⃣":
            await economy_setup(ctx)
        elif str(reaction.emoji) == "5️⃣":
            await tickets_setup(ctx)
            
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the bot.")

async def welcome_setup(ctx):
    embed = discord.Embed(
        title="👋 Welcome Setup",
        description="Please mention the channel where welcome messages should be sent.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)
    
    try:
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if not msg.channel_mentions:
            await ctx.send("❌ No channel mentioned. Setup cancelled.")
            return
        
        welcome_channel = msg.channel_mentions[0].id
        
        embed = discord.Embed(
            title="Welcome Message",
            description="Please enter the welcome message. You can use these placeholders:\n"
                        "{user} - Mentions the user\n"
                        "{server} - Server name\n"
                        "{count} - Member count",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=120.0
        )
        
        welcome_message = msg.content
        
        # Update guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        guild_data["welcome_channel"] = welcome_channel
        guild_data["welcome_message"] = welcome_message
        
        await db.update_guild(ctx.guild.id, guild_data)
        
        embed = discord.Embed(
            title="✅ Welcome System Configured",
            description=f"Welcome channel set to <#{welcome_channel}>\nWelcome message set!",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the welcome system.")

async def moderation_setup(ctx):
    embed = discord.Embed(
        title="🛡️ Moderation Setup",
        description="Please mention the channel where moderation logs should be sent.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)
    
    try:
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if not msg.channel_mentions:
            await ctx.send("❌ No channel mentioned. Setup cancelled.")
            return
        
        log_channel = msg.channel_mentions[0].id
        
        embed = discord.Embed(
            title="Mute Role",
            description="Please mention the role to use for mutes, or type 'create' to create a new one.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if msg.content.lower() == "create":
            # Create mute role
            mute_role = await ctx.guild.create_role(name="Muted", reason="Automatically created by bot setup")
            
            # Update channel permissions
            for channel in ctx.guild.channels:
                try:
                    await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)
                except:
                    pass
            
            mute_role_id = mute_role.id
        elif msg.role_mentions:
            mute_role_id = msg.role_mentions[0].id
        else:
            await ctx.send("❌ No role mentioned or 'create' specified. Using default settings.")
            mute_role_id = None
        
        # Update guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if "moderation" not in guild_data:
            guild_data["moderation"] = {}
            
        guild_data["moderation"]["log_channel"] = log_channel
        guild_data["moderation"]["mute_role"] = mute_role_id
        
        await db.update_guild(ctx.guild.id, guild_data)
        
        embed = discord.Embed(
            title="✅ Moderation System Configured",
            description=f"Log channel set to <#{log_channel}>\n" +
                        (f"Mute role set to <@&{mute_role_id}>" if mute_role_id else "No mute role set."),
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the moderation system.")

async def leveling_setup(ctx):
    embed = discord.Embed(
        title="📊 Leveling Setup",
        description="Please mention the channel where level-up announcements should be sent, or type 'none' for no announcements.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)
    
    try:
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if msg.content.lower() == "none":
            level_channel = None
        elif msg.channel_mentions:
            level_channel = msg.channel_mentions[0].id
        else:
            await ctx.send("❌ No valid channel mentioned. Disabling level-up announcements.")
            level_channel = None
        
        # Ask about role rewards
        embed = discord.Embed(
            title="Role Rewards",
            description="Would you like to set up automatic role rewards for levels? (yes/no)",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        role_rewards = {}
        if msg.content.lower() in ("yes", "y"):
            embed = discord.Embed(
                title="Role Rewards Setup",
                description="Please enter up to 5 level-role pairs in the format: `level: @role`\n"
                            "For example: `5: @Level 5`\n"
                            "Type 'done' when finished.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            
            for _ in range(5):  # Maximum 5 role rewards
                msg = await bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                
                if msg.content.lower() == "done":
                    break
                
                try:
                    level_part, role_part = msg.content.split(":", 1)
                    level = int(level_part.strip())
                    
                    if msg.role_mentions:
                        role_id = msg.role_mentions[0].id
                        role_rewards[str(level)] = role_id
                        await ctx.send(f"✅ Added role reward for level {level}.")
                    else:
                        await ctx.send("❌ No role mentioned. Skipping this entry.")
                except:
                    await ctx.send("❌ Invalid format. Please use the format: `level: @role`")
        
        # Update guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        guild_data["level_channel"] = level_channel
        guild_data["role_rewards"] = role_rewards
        
        await db.update_guild(ctx.guild.id, guild_data)
        
        embed = discord.Embed(
            title="✅ Leveling System Configured",
            description=(f"Level-up announcement channel: <#{level_channel}>" if level_channel else "Level-up announcements disabled") +
                        f"\nRole rewards: {len(role_rewards)} configured",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the leveling system.")

async def economy_setup(ctx):
    embed = discord.Embed(
        title="💰 Economy Setup",
        description="Do you want to enable the economy system for your server? (yes/no)",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)
    
    try:
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if msg.content.lower() not in ("yes", "y"):
            await ctx.send("Economy system setup cancelled.")
            return
        
        # Currency name
        embed = discord.Embed(
            title="Currency Name",
            description="What would you like to call your server's currency?",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        currency_name = msg.content.strip()
        
        # Starting balance
        embed = discord.Embed(
            title="Starting Balance",
            description="How much currency should new users start with?",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        try:
            starting_balance = int(msg.content.strip())
        except:
            await ctx.send("❌ Invalid number. Setting starting balance to 100.")
            starting_balance = 100
        
        # Update guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        guild_data["economy"] = {
            "enabled": True,
            "currency_name": currency_name,
            "starting_balance": starting_balance,
            "currency_symbol": currency_name[0] if currency_name else "$"
        }
        
        await db.update_guild(ctx.guild.id, guild_data)
        
        embed = discord.Embed(
            title="✅ Economy System Configured",
            description=f"Economy system enabled!\nCurrency: {currency_name}\nStarting Balance: {starting_balance}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the economy system.")

async def tickets_setup(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System Setup",
        description="Please mention the channel where the ticket panel should be sent.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)
    
    try:
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        if not msg.channel_mentions:
            await ctx.send("❌ No channel mentioned. Setup cancelled.")
            return
        
        ticket_channel = msg.channel_mentions[0]
        
        # Support roles
        embed = discord.Embed(
            title="Support Roles",
            description="Please mention the roles that should have access to tickets, separated by spaces.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
        
        support_roles = [role.id for role in msg.role_mentions]
        
        # Ticket panel message
        embed = discord.Embed(
            title="Ticket Panel Message",
            description="Please enter the message that should appear on the ticket panel.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=120.0
        )
        
        panel_message = msg.content
        
        # Create ticket panel
        ticket_embed = discord.Embed(
            title="🎫 Support Tickets",
            description=panel_message,
            color=EMBED_COLOR
        )
        ticket_embed.set_footer(text="Click the button below to create a ticket")
        
        # Create ticket button
        ticket_view = discord.ui.View(timeout=None)
        ticket_button = discord.ui.Button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket")
        ticket_view.add_item(ticket_button)
        
        panel_message = await ticket_channel.send(embed=ticket_embed, view=ticket_view)
        
        # Update guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        guild_data["tickets"] = {
            "enabled": True,
            "panel_channel": ticket_channel.id,
            "panel_message": panel_message.id,
            "support_roles": support_roles,
            "category": None  # Will be created when first ticket is opened
        }
        
        await db.update_guild(ctx.guild.id, guild_data)
        
        embed = discord.Embed(
            title="✅ Ticket System Configured",
            description=f"Ticket system enabled!\nPanel sent to {ticket_channel.mention}\nSupport roles: {len(support_roles)}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please run the command again if you want to set up the ticket system.")

# Moderation Commands
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kick a member from the server"""
    if member == ctx.author:
        await ctx.send("❌ You cannot kick yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot kick someone with a higher or equal role.")
        return
    
    try:
        # Create moderation case
        guild_data = await db.get_guild(ctx.guild.id) or {}
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "action": "kick",
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # DM the user
        try:
            embed = discord.Embed(
                title=f"You were kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Case ID:** {case_count}",
                color=ERROR_COLOR
            )
            await member.send(embed=embed)
        except:
            pass  # Member might have DMs disabled
        
        # Kick the member
        await ctx.guild.kick(member, reason=f"{reason} - By {ctx.author}")
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ Member Kicked",
            description=f"{member.mention} has been kicked from the server.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Member Kicked | Case #{case_count}",
                    description=f"**Member:** {member} ({member.id})\n**Moderator:** {ctx.author.mention}\n**Reason:** {reason}",
                    color=WARNING_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error kicking member: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("members_kicked")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """Ban a member from the server"""
    if member == ctx.author:
        await ctx.send("❌ You cannot ban yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot ban someone with a higher or equal role.")
        return
    
    try:
        # Create moderation case
        guild_data = await db.get_guild(ctx.guild.id) or {}
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "action": "ban",
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # DM the user
        try:
            embed = discord.Embed(
                title=f"You were banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Case ID:** {case_count}",
                color=ERROR_COLOR
            )
            await member.send(embed=embed)
        except:
            pass  # Member might have DMs disabled
        
        # Ban the member
        await ctx.guild.ban(member, reason=f"{reason} - By {ctx.author}")
        
        # Send confirmation
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{member.mention} has been banned from the server.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Member Banned | Case #{case_count}",
                    description=f"**Member:** {member} ({member.id})\n**Moderator:** {ctx.author.mention}\n**Reason:** {reason}",
                    color=ERROR_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error banning member: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("members_banned")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int, *, reason="No reason provided"):
    """Unban a user by their ID"""
    try:
        # Check if user is banned
        ban_entry = None
        async for entry in ctx.guild.bans():
            if entry.user.id == user_id:
                ban_entry = entry
                break
        
        if not ban_entry:
            await ctx.send("❌ This user is not banned.")
            return
        
        # Create moderation case
        guild_data = await db.get_guild(ctx.guild.id) or {}
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": user_id,
            "moderator_id": ctx.author.id,
            "action": "unban",
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # Unban the user
        await ctx.guild.unban(ban_entry.user, reason=f"{reason} - By {ctx.author}")
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ User Unbanned",
            description=f"{ban_entry.user.mention} ({ban_entry.user.id}) has been unbanned from the server.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"User Unbanned | Case #{case_count}",
                    description=f"**User:** {ban_entry.user} ({ban_entry.user.id})\n**Moderator:** {ctx.author.mention}\n**Reason:** {reason}",
                    color=SUCCESS_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error unbanning user: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    """Warn a member"""
    if member == ctx.author:
        await ctx.send("❌ You cannot warn yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot warn someone with a higher or equal role.")
        return
    
    try:
        # Create moderation case
        guild_data = await db.get_guild(ctx.guild.id) or {}
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "action": "warn",
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # DM the user
        try:
            embed = discord.Embed(
                title=f"You were warned in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Case ID:** {case_count}",
                color=WARNING_COLOR
            )
            await member.send(embed=embed)
        except:
            pass  # Member might have DMs disabled
        
        # Send confirmation
        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=f"{member.mention} has been warned.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=WARNING_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Member Warned | Case #{case_count}",
                    description=f"**Member:** {member} ({member.id})\n**Moderator:** {ctx.author.mention}\n**Reason:** {reason}",
                    color=WARNING_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error warning member: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("members_warned")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: str = None, *, reason="No reason provided"):
    """Mute a member (timeout)"""
    if member == ctx.author:
        await ctx.send("❌ You cannot mute yourself.")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot mute someone with a higher or equal role.")
        return
    
    # Parse duration
    duration_seconds = 0
    if duration:
        time_units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800
        }
        
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            
            if unit in time_units:
                duration_seconds = value * time_units[unit]
            else:
                duration_seconds = int(duration)
        except:
            await ctx.send("❌ Invalid duration format. Use a number followed by s, m, h, d, or w.")
            return
    
    if duration_seconds > 2419200:  # 28 days (Discord limit)
        await ctx.send("❌ Timeout duration cannot exceed 28 days.")
        return
    
    if duration_seconds <= 0:
        await ctx.send("❌ Duration must be positive.")
        return
    
    try:
        # Get mute role from guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        
        # Create moderation case
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "action": "mute",
            "reason": reason,
            "duration": duration_seconds,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # Apply timeout
        until = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)
        await member.timeout(until, reason=f"{reason} - By {ctx.author}")
        
        # Format duration for display
        if duration_seconds < 60:
            duration_text = f"{duration_seconds} seconds"
        elif duration_seconds < 3600:
            duration_text = f"{duration_seconds // 60} minutes"
        elif duration_seconds < 86400:
            duration_text = f"{duration_seconds // 3600} hours"
        else:
            duration_text = f"{duration_seconds // 86400} days"
        
        # DM the user
        try:
            embed = discord.Embed(
                title=f"You were muted in {ctx.guild.name}",
                description=f"**Duration:** {duration_text}\n**Reason:** {reason}\n**Case ID:** {case_count}",
                color=WARNING_COLOR
            )
            await member.send(embed=embed)
        except:
            pass  # Member might have DMs disabled
        
        # Send confirmation
        embed = discord.Embed(
            title="🔇 Member Muted",
            description=f"{member.mention} has been muted for {duration_text}.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Member Muted | Case #{case_count}",
                    description=f"**Member:** {member} ({member.id})\n**Moderator:** {ctx.author.mention}\n**Duration:** {duration_text}\n**Reason:** {reason}",
                    color=WARNING_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error muting member: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("members_muted")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member, *, reason="No reason provided"):
    """Unmute a member (remove timeout)"""
    try:
        # Check if member is actually muted
        if not member.is_timed_out():
            await ctx.send("❌ This member is not muted.")
            return
        
        # Create moderation case
        guild_data = await db.get_guild(ctx.guild.id) or {}
        case_count = guild_data.get("case_count", 0) + 1
        guild_data["case_count"] = case_count
        await db.update_guild(ctx.guild.id, guild_data)
        
        case_data = {
            "case_id": case_count,
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "action": "unmute",
            "reason": reason,
            "timestamp": datetime.datetime.utcnow().timestamp()
        }
        
        await db.create_moderation_case(case_data)
        
        # Remove timeout
        await member.timeout(None, reason=f"Unmuted: {reason} - By {ctx.author}")
        
        # DM the user
        try:
            embed = discord.Embed(
                title=f"You were unmuted in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Case ID:** {case_count}",
                color=SUCCESS_COLOR
            )
            await member.send(embed=embed)
        except:
            pass  # Member might have DMs disabled
        
        # Send confirmation
        embed = discord.Embed(
            title="🔊 Member Unmuted",
            description=f"{member.mention} has been unmuted.\n**Reason:** {reason}\n**Case ID:** {case_count}",
            color=SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
        
        # Log the action
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Member Unmuted | Case #{case_count}",
                    description=f"**Member:** {member} ({member.id})\n**Moderator:** {ctx.author.mention}\n**Reason:** {reason}",
                    color=SUCCESS_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error unmuting member: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int, user: discord.Member = None):
    """Delete a specified number of messages"""
    if amount <= 0 or amount > 100:
        await ctx.send("❌ Please provide a number between 1 and 100.")
        return
    
    try:
        await ctx.message.delete()  # Delete the command message
        
        if user:
            def check(msg):
                return msg.author == user
                
            deleted = await ctx.channel.purge(limit=amount, check=check)
            embed = discord.Embed(
                title="✅ Messages Purged",
                description=f"Deleted {len(deleted)} messages from {user.mention}.",
                color=SUCCESS_COLOR
            )
        else:
            deleted = await ctx.channel.purge(limit=amount)
            embed = discord.Embed(
                title="✅ Messages Purged",
                description=f"Deleted {len(deleted)} messages.",
                color=SUCCESS_COLOR
            )
        
        confirm_msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)  # Show confirmation for 5 seconds
        await confirm_msg.delete()
        
        # Log the action
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if "moderation" in guild_data and guild_data["moderation"].get("log_channel"):
            log_channel = bot.get_channel(guild_data["moderation"]["log_channel"])
            if log_channel:
                log_embed = discord.Embed(
                    title="Messages Purged",
                    description=f"**Moderator:** {ctx.author.mention}\n**Channel:** {ctx.channel.mention}\n**Messages Deleted:** {len(deleted)}\n**Target User:** {user.mention if user else 'None'}",
                    color=WARNING_COLOR,
                    timestamp=datetime.datetime.utcnow()
                )
                await log_channel.send(embed=log_embed)
                
    except Exception as e:
        await ctx.send(f"❌ Error purging messages: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def infractions(ctx, member: discord.Member = None):
    """View a user's infractions"""
    if member is None:
        member = ctx.author
    
    try:
        # Get user cases
        cases = await db.get_user_cases(member.id, ctx.guild.id)
        
        if not cases:
            embed = discord.Embed(
                title=f"Infractions for {member}",
                description="This user has no infractions.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        # Sort cases by timestamp (newest first)
        cases.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Create embed
        embed = discord.Embed(
            title=f"Infractions for {member}",
            description=f"Found {len(cases)} infractions for this user.",
            color=EMBED_COLOR
        )
        
        # Add up to 10 most recent cases
        for case in cases[:10]:
            action = case.get("action", "unknown").upper()
            reason = case.get("reason", "No reason provided")
            case_id = case.get("case_id", 0)
            timestamp = datetime.datetime.fromtimestamp(case.get("timestamp", 0))
            
            # Format action for display
            if action == "BAN":
                action = "🔨 BAN"
            elif action == "KICK":
                action = "👢 KICK"
            elif action == "WARN":
                action = "⚠️ WARN"
            elif action == "MUTE":
                action = "🔇 MUTE"
            elif action == "UNMUTE":
                action = "🔊 UNMUTE"
            elif action == "UNBAN":
                action = "✅ UNBAN"
            
            embed.add_field(
                name=f"Case #{case_id} | {action} | {timestamp.strftime('%Y-%m-%d')}",
                value=f"**Reason:** {reason}",
                inline=False
            )
        
        if len(cases) > 10:
            embed.set_footer(text=f"Showing 10 most recent out of {len(cases)} infractions.")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error retrieving infractions: {e}")
    
    await db.increment_stats("commands_used")

# Economy Commands
@bot.command()
async def balance(ctx, member: discord.Member = None):
    """Check your balance or someone else's"""
    if member is None:
        member = ctx.author
    
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get user economy data
        economy_data = await db.get_economy(member.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": member.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
            await db.update_economy(member.id, economy_data)
        
        # Create embed
        embed = discord.Embed(
            title=f"{member.display_name}'s Balance",
            color=EMBED_COLOR
        )
        
        embed.add_field(
            name="👛 Wallet",
            value=f"{currency_symbol} {economy_data.get('balance', 0):,}",
            inline=True
        )
        
        embed.add_field(
            name="🏦 Bank",
            value=f"{currency_symbol} {economy_data.get('bank', 0):,}",
            inline=True
        )
        
        total = economy_data.get('balance', 0) + economy_data.get('bank', 0)
        embed.add_field(
            name="💰 Total",
            value=f"{currency_symbol} {total:,}",
            inline=True
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error checking balance: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
async def daily(ctx):
    """Claim your daily reward"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get user economy data
        economy_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        # Check cooldown
        last_daily = economy_data.get("last_daily", 0)
        now = time.time()
        
        # 24 hours = 86400 seconds
        if now - last_daily < 86400:
            next_daily = last_daily + 86400
            time_left = next_daily - now
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            
            embed = discord.Embed(
                title="⏰ Daily Reward on Cooldown",
                description=f"You need to wait **{hours}h {minutes}m** before claiming your next daily reward.",
                color=WARNING_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        # Determine daily amount
        is_premium = await db.is_premium(ctx.guild.id)
        daily_amount = 300 if is_premium else 200
        
        # Update user data
        economy_data["balance"] = economy_data.get("balance", 0) + daily_amount
        economy_data["last_daily"] = now
        
        await db.update_economy(ctx.author.id, economy_data)
        
        # Create embed
        embed = discord.Embed(
            title="✅ Daily Reward Claimed",
            description=f"You received **{currency_symbol} {daily_amount:,}** as your daily reward!",
            color=SUCCESS_COLOR
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{currency_symbol} {economy_data['balance']:,}",
            inline=False
        )
        
        if is_premium:
            embed.set_footer(text="Premium server bonus applied!")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error claiming daily reward: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("daily_rewards_claimed")

@bot.command()
async def work(ctx):
    """Work to earn some money"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get user economy data
        economy_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        # Check cooldown
        last_work = economy_data.get("last_work", 0)
        now = time.time()
        
        # 30 minutes = 1800 seconds
        if now - last_work < 1800:
            next_work = last_work + 1800
            time_left = next_work - now
            minutes = int(time_left // 60)
            seconds = int(time_left % 60)
            
            embed = discord.Embed(
                title="⏰ Work on Cooldown",
                description=f"You need to wait **{minutes}m {seconds}s** before working again.",
                color=WARNING_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        # Work jobs and messages
        jobs = [
            {"job": "Software Developer", "min": 50, "max": 200},
            {"job": "Pizza Delivery Driver", "min": 30, "max": 120},
            {"job": "Teacher", "min": 40, "max": 150},
            {"job": "Doctor", "min": 70, "max": 250},
            {"job": "Streamer", "min": 20, "max": 300},
            {"job": "Lawyer", "min": 60, "max": 220},
            {"job": "Chef", "min": 40, "max": 180},
            {"job": "Farmer", "min": 30, "max": 130},
            {"job": "Security Guard", "min": 35, "max": 140},
            {"job": "Freelancer", "min": 25, "max": 280}
        ]
        
        messages = [
            "You worked as a {job} and earned {amount} {currency}!",
            "Your shift as a {job} just ended. You earned {amount} {currency}!",
            "You spent hours as a {job} and received {amount} {currency}!",
            "Being a {job} paid off! You earned {amount} {currency}!",
            "Your work as a {job} earned you {amount} {currency}!"
        ]
        
        # Select random job and calculate earnings
        job = random.choice(jobs)
        is_premium = await db.is_premium(ctx.guild.id)
        
        min_amount = job["min"]
        max_amount = job["max"]
        
        if is_premium:
            # 25% bonus for premium servers
            min_amount = int(min_amount * 1.25)
            max_amount = int(max_amount * 1.25)
        
        amount = random.randint(min_amount, max_amount)
        
        # Update user data
        economy_data["balance"] = economy_data.get("balance", 0) + amount
        economy_data["last_work"] = now
        
        await db.update_economy(ctx.author.id, economy_data)
        
        # Create message
        message = random.choice(messages).format(
            job=job["job"],
            amount=f"{currency_symbol} {amount:,}",
            currency=currency_name
        )
        
        # Create embed
        embed = discord.Embed(
            title="💼 Work Completed",
            description=message,
            color=SUCCESS_COLOR
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{currency_symbol} {economy_data['balance']:,}",
            inline=False
        )
        
        if is_premium:
            embed.set_footer(text="Premium server bonus applied!")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error working: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("work_completed")

@bot.command()
async def deposit(ctx, amount: str):
    """Deposit money into your bank"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get user economy data
        economy_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        current_balance = economy_data.get("balance", 0)
        
        # Handle special amount values
        if amount.lower() == "all":
            deposit_amount = current_balance
        elif amount.lower() == "half":
            deposit_amount = current_balance // 2
        else:
            try:
                deposit_amount = int(amount)
            except:
                await ctx.send("❌ Please provide a valid amount.")
                return
        
        if deposit_amount <= 0:
            await ctx.send("❌ You must deposit a positive amount.")
            return
        
        if deposit_amount > current_balance:
            await ctx.send("❌ You don't have that much money in your wallet.")
            return
        
        # Update balances
        economy_data["balance"] = current_balance - deposit_amount
        economy_data["bank"] = economy_data.get("bank", 0) + deposit_amount
        
        await db.update_economy(ctx.author.id, economy_data)
        
        # Create embed
        embed = discord.Embed(
            title="💳 Money Deposited",
            description=f"You deposited **{currency_symbol} {deposit_amount:,}** into your bank account.",
            color=SUCCESS_COLOR
        )
        
        embed.add_field(
            name="Wallet Balance",
            value=f"{currency_symbol} {economy_data['balance']:,}",
            inline=True
        )
        
        embed.add_field(
            name="Bank Balance",
            value=f"{currency_symbol} {economy_data['bank']:,}",
            inline=True
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error depositing money: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
async def withdraw(ctx, amount: str):
    """Withdraw money from your bank"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get user economy data
        economy_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        current_bank = economy_data.get("bank", 0)
        
        # Handle special amount values
        if amount.lower() == "all":
            withdraw_amount = current_bank
        elif amount.lower() == "half":
            withdraw_amount = current_bank // 2
        else:
            try:
                withdraw_amount = int(amount)
            except:
                await ctx.send("❌ Please provide a valid amount.")
                return
        
        if withdraw_amount <= 0:
            await ctx.send("❌ You must withdraw a positive amount.")
            return
        
        if withdraw_amount > current_bank:
            await ctx.send("❌ You don't have that much money in your bank.")
            return
        
        # Update balances
        economy_data["bank"] = current_bank - withdraw_amount
        economy_data["balance"] = economy_data.get("balance", 0) + withdraw_amount
        
        await db.update_economy(ctx.author.id, economy_data)
        
        # Create embed
        embed = discord.Embed(
            title="💸 Money Withdrawn",
            description=f"You withdrew **{currency_symbol} {withdraw_amount:,}** from your bank account.",
            color=SUCCESS_COLOR
        )
        
        embed.add_field(
            name="Wallet Balance",
            value=f"{currency_symbol} {economy_data['balance']:,}",
            inline=True
        )
        
        embed.add_field(
            name="Bank Balance",
            value=f"{currency_symbol} {economy_data['bank']:,}",
            inline=True
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error withdrawing money: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    """Pay another user from your wallet"""
    if member == ctx.author:
        await ctx.send("❌ You cannot pay yourself.")
        return
    
    if amount <= 0:
        await ctx.send("❌ You must pay a positive amount.")
        return
    
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Get sender's economy data
        sender_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the sender, create it
        if not sender_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            sender_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        # Check if sender has enough money
        if sender_data.get("balance", 0) < amount:
            await ctx.send("❌ You don't have enough money in your wallet.")
            return
        
        # Get recipient's economy data
        recipient_data = await db.get_economy(member.id) or {}
        
        # If no economy data exists for the recipient, create it
        if not recipient_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            recipient_data = {
                "_id": member.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        # Transfer money
        sender_data["balance"] = sender_data.get("balance", 0) - amount
        recipient_data["balance"] = recipient_data.get("balance", 0) + amount
        
        await db.update_economy(ctx.author.id, sender_data)
        await db.update_economy(member.id, recipient_data)
        
        # Create embed
        embed = discord.Embed(
            title="💸 Money Transferred",
            description=f"You paid **{currency_symbol} {amount:,}** to {member.mention}.",
            color=SUCCESS_COLOR
        )
        
        embed.add_field(
            name="Your New Balance",
            value=f"{currency_symbol} {sender_data['balance']:,}",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        # Send notification to recipient
        try:
            recipient_embed = discord.Embed(
                title="💰 Money Received",
                description=f"You received **{currency_symbol} {amount:,}** from {ctx.author.mention}.",
                color=SUCCESS_COLOR
            )
            
            recipient_embed.add_field(
                name="Your New Balance",
                value=f"{currency_symbol} {recipient_data['balance']:,}",
                inline=False
            )
            
            await member.send(embed=recipient_embed)
        except:
            pass  # Recipient might have DMs disabled
        
    except Exception as e:
        await ctx.send(f"❌ Error transferring money: {e}")
    
    await db.increment_stats("commands_used")
    await db.increment_stats("money_transferred")

@bot.command()
async def shop(ctx):
    """View the server shop"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Default shop items if none defined
        default_shop = [
            {"id": "role_color", "name": "Custom Role Color", "description": "Change your role color", "price": 500, "premium": False},
            {"id": "rename", "name": "Nickname Change", "description": "Change your nickname", "price": 200, "premium": False},
            {"id": "vip_role", "name": "VIP Role", "description": "Get a special VIP role", "price": 2000, "premium": False},
            {"id": "lootbox", "name": "Lootbox", "description": "Get random rewards", "price": 300, "premium": False},
            {"id": "xp_boost", "name": "XP Boost (1 hour)", "description": "Get 2x XP for 1 hour", "price": 1000, "premium": True},
            {"id": "money_boost", "name": "Money Boost (1 hour)", "description": "Get 2x money from work for 1 hour", "price": 1500, "premium": True}
        ]
        
        # Get shop items from guild settings or use default
        shop_items = guild_data.get("shop_items", default_shop)
        is_premium = await db.is_premium(ctx.guild.id)
        
        # Create embed
        embed = discord.Embed(
            title=f"{ctx.guild.name}'s Shop",
            description=f"Use `!buy <item_id>` to purchase an item.",
            color=EMBED_COLOR
        )
        
        # List shop items
        for item in shop_items:
            if item.get("premium", False) and not is_premium:
                continue  # Skip premium items on non-premium servers
            
            embed.add_field(
                name=f"{item['name']} - {currency_symbol} {item['price']:,}",
                value=f"**ID:** `{item['id']}`\n**Description:** {item['description']}" + 
                      (f"\n⭐ **Premium Item**" if item.get("premium", False) else ""),
                inline=False
            )
        
        if not embed.fields:
            embed.description = "No items available in the shop."
        
        # Add premium note if not premium
        if not is_premium:
            embed.set_footer(text="Upgrade to premium to unlock more shop items!")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error displaying shop: {e}")
    
    await db.increment_stats("commands_used")

@bot.command()
async def buy(ctx, item_id: str):
    """Buy an item from the shop"""
    try:
        # Get guild settings
        guild_data = await db.get_guild(ctx.guild.id) or {}
        if not guild_data.get("economy", {}).get("enabled", False):
            await ctx.send("❌ Economy system is not enabled on this server.")
            return
        
        currency_name = guild_data["economy"]["currency_name"]
        currency_symbol = guild_data["economy"]["currency_symbol"]
        
        # Default shop items if none defined
        default_shop = [
            {"id": "role_color", "name": "Custom Role Color", "description": "Change your role color", "price": 500, "premium": False},
            {"id": "rename", "name": "Nickname Change", "description": "Change your nickname", "price": 200, "premium": False},
            {"id": "vip_role", "name": "VIP Role", "description": "Get a special VIP role", "price": 2000, "premium": False},
            {"id": "lootbox", "name": "Lootbox", "description": "Get random rewards", "price": 300, "premium": False},
            {"id": "xp_boost", "name": "XP Boost (1 hour)", "description": "Get 2x XP for 1 hour", "price": 1000, "premium": True},
            {"id": "money_boost", "name": "Money Boost (1 hour)", "description": "Get 2x money from work for 1 hour", "price": 1500, "premium": True}
        ]
        
        # Get shop items from guild settings or use default
        shop_items = guild_data.get("shop_items", default_shop)
        is_premium = await db.is_premium(ctx.guild.id)
        
        # Find the item
        item = None
        for shop_item in shop_items:
            if shop_item["id"] == item_id:
                item = shop_item
                break
        
        if not item:
            await ctx.send("❌ Item not found in shop. Use `!shop` to see available items.")
            return
        
        # Check if premium item on non-premium server
        if item.get("premium", False) and not is_premium:
            await ctx.send("⭐ This is a premium item and is only available on premium servers.")
            return
        
        # Get user economy data
        economy_data = await db.get_economy(ctx.author.id) or {}
        
        # If no economy data exists for the user, create it
        if not economy_data:
            starting_balance = guild_data["economy"]["starting_balance"]
            economy_data = {
                "_id": ctx.author.id,
                "balance": starting_balance,
                "bank": 0,
                "last_daily": 0,
                "last_work": 0,
                "inventory": {}
            }
        
        # Check if user has enough money
        if economy_data.get("balance", 0) < item["price"]:
            await ctx.send(f"❌ You don't have enough {currency_name}. You need {currency_symbol} {item['price']:,}.")
            return
        
        # Process purchase based on item type
        if item["id"] == "role_color":
            embed = discord.Embed(
                title="Role Color Purchase",
                description="Please enter a hex color code (e.g., #FF0000 for red):",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            
            try:
                msg = await bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                
                color_hex = msg.content.strip()
                if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color_hex):
                    await ctx.send("❌ Invalid hex color code. Purchase cancelled.")
                    return
                
                # Convert hex to discord.Color
                color = discord.Color(int(color_hex[1:], 16))
                
                # Check if user already has a colored role
                colored_role = None
                for role in ctx.author.roles:
                    if role.name == f"{ctx.author.name}'s Color":
                        colored_role = role
                        break
                
                if colored_role:
                    await colored_role.edit(color=color)
                else:
                    # Create new role
                    colored_role = await ctx.guild.create_role(
                        name=f"{ctx.author.name}'s Color",
                        color=color,
                        reason=f"Color role purchase by {ctx.author}"
                    )
                    
                    # Add role to user
                    await ctx.author.add_roles(colored_role)
                    
                    # Move role position to just above the user's highest role
                    highest_role_pos = max([role.position for role in ctx.author.roles if role.id != colored_role.id])
                    await colored_role.edit(position=highest_role_pos + 1)
                
                success_message = f"Changed your role color to {color_hex}!"
                
            except asyncio.TimeoutError:
                await ctx.send("❌ You took too long to respond. Purchase cancelled.")
                return
                
        elif item["id"] == "rename":
            embed = discord.Embed(
                title="Nickname Purchase",
                description="Please enter your new nickname:",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            
            try:
                msg = await bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                    timeout=60.0
                )
                
                new_nick = msg.content.strip()
                if len(new_nick) > 32:
                    await ctx.send("❌ Nickname cannot be longer than 32 characters. Purchase cancelled.")
                    return
                
                await ctx.author.edit(nick=new_nick)
                success_message = f"Changed your nickname to {new_nick}!"
                
            except asyncio.TimeoutError:
                await ctx.send("❌ You took too long to respond. Purchase cancelled.")
                return
                
        elif item["id"] == "vip_role":
            # Check if VIP role exists
            vip_role = discord.utils.get(ctx.guild.roles, name="VIP")
            
            if not vip_role:
                # Create VIP role
                vip_role = await ctx.guild.create_role(
