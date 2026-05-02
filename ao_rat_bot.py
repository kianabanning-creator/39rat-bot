import discord
from discord.ext import commands
import os

TOKEN = os.environ.get("TOKEN") 

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ AO RAT Bot is online! Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="!info | AO Software"))

@bot.command()
async def info(ctx):
    await ctx.send("🤖 AO RAT Bot is online. Full features coming soon.")

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")

bot.run(TOKEN)
