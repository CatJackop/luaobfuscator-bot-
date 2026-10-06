import os
import io
import asyncio
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("LUAOBFUSCATOR_API_KEY")
API_URL = os.getenv("LUAOBFUSCATOR_API_URL")
PREFIX = os.getenv("PREFIX", ".")
OBFUSCATOR_CHANNEL_ID = os.getenv("OBFUSCATOR_CHANNEL_ID")

MAX_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = (".lua", ".luau", ".txt")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

def is_allowed_name(name: str) -> bool:
    return name.lower().endswith(ALLOWED_EXTENSIONS)

async def read_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS links are allowed.")

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as r:
            if r.status != 200:
                raise ValueError(f"Link returned HTTP {r.status}.")
            data = await r.read()
            if len(data) > MAX_BYTES:
                raise ValueError("The source file is larger than 5 MB.")
            content_type = r.headers.get("content-type", "")
            name = os.path.basename(urlparse(str(r.url)).path) or "source.lua"
            if not is_allowed_name(name) and "text" not in content_type.lower():
                name = "source.lua"
            return name, data

async def call_obfuscator(source: str) -> str:
    if not API_KEY:
        raise RuntimeError("LUAOBFUSCATOR_API_KEY is not configured.")
    if not API_URL:
        raise RuntimeError(
            "LUAOBFUSCATOR_API_URL is not configured. "
            "Set it to the API endpoint from your LuaObfuscator API Docs."
        )

    # The exact request schema is intentionally configurable because the
    # service's API documentation is required for the endpoint/payload format.
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "CAT-JACK-Lua-Obfuscator/1.0",
    }
    payload = {"script": source}

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(API_URL, json=payload, headers=headers) as r:
            body = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"Obfuscator API returned HTTP {r.status}: {body[:500]}")
            try:
                data = await r.json(content_type=None)
                for key in ("obfuscated", "code", "script", "result", "output"):
                    if isinstance(data.get(key), str):
                        return data[key]
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    for key in ("obfuscated", "code", "script", "result", "output"):
                        if isinstance(data["data"].get(key), str):
                            return data["data"][key]
                raise RuntimeError("API response did not contain obfuscated source code.")
            except ValueError:
                if body.strip():
                    return body
                raise RuntimeError("The obfuscator returned an empty response.")

def channel_allowed(channel_id: int) -> bool:
    if not OBFUSCATOR_CHANNEL_ID:
        return True
    try:
        return channel_id == int(OBFUSCATOR_CHANNEL_ID)
    except ValueError:
        return False

def channel_denied_embed():
    return make_embed(
        "Wrong channel",
        "🔒 The Lua obfuscator can only be used in the configured obfuscator channel.",
        False
    )

def make_embed(title, description, ok=True):
    return discord.Embed(
        title=("🐱 " if ok else "⚠️ ") + title,
        description=description,
        color=discord.Color.gold() if ok else discord.Color.red()
    )

async def process_source(ctx, filename, raw):
    if len(raw) > MAX_BYTES:
        await ctx.send(embed=make_embed("File too large", "Maximum size is 5 MB.", False))
        return
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.send(embed=make_embed("Invalid file", "The source must be UTF-8 text.", False))
        return

    msg = await ctx.send(embed=make_embed("Obfuscating", "🔄 Sending your Lua source to the obfuscation API..."))
    try:
        result = await call_obfuscator(source)
        out_name = os.path.splitext(os.path.basename(filename))[0] + "_obfuscated.lua"
        data = result.encode("utf-8")
        await msg.edit(embed=make_embed("Obfuscation complete", "✅ Your obfuscated file is ready."))
        await ctx.send(file=discord.File(io.BytesIO(data), filename=out_name))
    except Exception as e:
        await msg.edit(embed=make_embed("Obfuscation failed", str(e)[:1500], False))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command(name="obfuscate")
async def obfuscate(ctx, url: str | None = None):
    if not channel_allowed(ctx.channel.id):
        await ctx.send(embed=channel_denied_embed())
        return

    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if not is_allowed_name(attachment.filename):
            await ctx.send(embed=make_embed("Unsupported file", "Use a .lua, .luau, or .txt file.", False))
            return
        if attachment.size > MAX_BYTES:
            await ctx.send(embed=make_embed("File too large", "Maximum size is 5 MB.", False))
            return
        data = await attachment.read()
        await process_source(ctx, attachment.filename, data)
        return

    if url:
        try:
            name, data = await read_url(url)
            await process_source(ctx, name, data)
        except Exception as e:
            await ctx.send(embed=make_embed("Link error", str(e)[:1500], False))
        return

    await ctx.send(embed=make_embed(
        "Lua Obfuscator",
        f"Upload a `.lua`, `.luau`, or `.txt` file with `{PREFIX}obfuscate`, "
        f"or use `{PREFIX}obfuscate <direct URL>`."
    ))

@bot.tree.command(name="obfuscate", description="Obfuscate a Lua/Luau/TXT file or direct source URL.")
async def slash_obfuscate(interaction: discord.Interaction, url: str | None = None):
    if not channel_allowed(interaction.channel_id):
        await interaction.response.send_message(embed=channel_denied_embed(), ephemeral=True)
        return

    await interaction.response.defer()
    if url:
        try:
            name, data = await read_url(url)
            await process_interaction(interaction, name, data)
        except Exception as e:
            await interaction.followup.send(embed=make_embed("Link error", str(e)[:1500], False))
    else:
        await interaction.followup.send(
            embed=make_embed("Lua Obfuscator", "Attach a file to a message and use the prefix command, "
                                              "or provide a direct URL to the slash command.")
        )

async def process_interaction(interaction, filename, raw):
    if len(raw) > MAX_BYTES:
        await interaction.followup.send(embed=make_embed("File too large", "Maximum size is 5 MB.", False))
        return
    try:
        source = raw.decode("utf-8")
        result = await call_obfuscator(source)
        out_name = os.path.splitext(os.path.basename(filename))[0] + "_obfuscated.lua"
        await interaction.followup.send(
            embed=make_embed("Obfuscation complete", "✅ Your obfuscated file is ready."),
            file=discord.File(io.BytesIO(result.encode("utf-8")), filename=out_name)
        )
    except Exception as e:
        await interaction.followup.send(embed=make_embed("Obfuscation failed", str(e)[:1500], False))

@bot.command(name="help")
async def help_command(ctx):
    if not channel_allowed(ctx.channel.id):
        await ctx.send(embed=channel_denied_embed())
        return
    e = make_embed(
        "CAT JACK Lua Obfuscator",
        f"**{PREFIX}obfuscate** + upload a `.lua`, `.luau`, or `.txt`\n"
        f"**{PREFIX}obfuscate <URL>** for a direct/raw source link\n"
        f"**/obfuscate** for the slash-command URL mode\n\n"
        "No database is required."
    )
    await ctx.send(embed=e)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not configured.")

bot.run(TOKEN)
