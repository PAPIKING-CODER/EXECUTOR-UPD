import os
import re
import json
import time
import random
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
import requests
from dotenv import load_dotenv

load_dotenv()

# ── LOGGING ──────────────────────────────────────────────────────
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("FMD_BOT")
logger.setLevel(logging.INFO)
_file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ── CONFIGURATION ────────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

BYPASS_API_ENDPOINT = "https://4pi-bypass.vercel.app/api/bypass?url="
AUTOBYPASS_FILE = "autobypass_channels.json"

# ── CUSTOM EMOJIS (FMD BOT DESIGN) ──────────────────────────────
EMOJI_GREEN_DOT = "<a:greendot:1526742445323190272>"
EMOJI_LOADER    = "<a:loader:1526741970226253834>"
EMOJI_CROWN     = "<a:greencrown:1526742765311098980>"
EMOJI_KEY       = "<:gold_key:1526743159038803978>"
EMOJI_CLOCK     = "<:clock:1525380296852377711>"
EMOJI_SUCCESS   = "<:success:1526742163050991616>"
EMOJI_COPY      = "<:copy_text:1526743644894138479>"
EMOJI_DISCORD   = "<:discord:1526743527642501273>"
EMOJI_INVITE    = "<:voice_invite:1526743390488756236>"
EMOJI_WARNING   = "<:Warningicon:1526855124134137856>"
EMOJI_FAILED    = "<:failed:1526857565156147250>"
EMOJI_TICKET    = "<:ticket:1526851476280836256>"
EMOJI_GIVEAWAY  = "<a:giveaway:1526817132501798983>"
EMOJI_GIFT      = "<a:gift:1526817190660280360>"
EMOJI_MONEY     = "<:Money:1526852670743380031>"
EMOJI_ROCKET    = "<:rocket:1527233455451017337>"
EMOJI_ADMIN     = "<:Admin:1526850858271248384>"
EMOJI_OWNER     = "<:Owner:1526850915418509362>"
EMOJI_MEMBER    = "<:Member:1526851357330505822>"
EMOJI_LOCK      = "<:lock:1527233626175963236>"
EMOJI_UNLOCK    = "<:unlock:1527233852215656450>"
EMOJI_EDIT      = "<:edit:1527235794438328372>"
EMOJI_DELETE    = "<:Trash_1:1527235528205009020>"
EMOJI_HOME      = "<:Home:1527235583460773909>"
EMOJI_LINK      = "<:Link:1525379856034959422>"
EMOJI_PC        = "<:pc:1516371549471506435>"
EMOJI_ARROW     = "<a:Arrow:1401389285042684035>"
EMOJI_INFORMATION = "<:Information:1526852173852315799>"
EMOJI_DOCUMENT  = "<:document:1527231734880538724>"

# ── COLORS ───────────────────────────────────────────────────────
C_GREEN = 0x00FF66
C_WARN  = 0xFFA500
C_ERROR = 0xED4245
C_GOLD  = 0xFACC15
C_BLUE  = 0x3B82F6
C_RED   = 0xEF4444
C_INFO  = 0x5865F2
C_PURPLE= 0x8B5CF6

# ── HELPERS ──────────────────────────────────────────────────────
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
BOT_START_TIME = datetime.now(timezone.utc)
AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"
ECONOMY_FILE = "economy.json"
LEVELS_FILE = "levels.json"
WARNINGS_FILE = "warnings.json"
GIVEAWAYS_FILE = "giveaways.json"
TICKETS_FILE = "tickets.json"
IA_CONFIG_FILE = "ia_config.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not save {path}: {e}")

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _footer() -> str:
    return "Made with ❤️ by KING • FMD BOT"

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START_TIME
    total = int(d.total_seconds())
    h, r = divmod(total, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def xp_needed(level: int) -> int:
    return 5 * (level + 1) ** 2

async def _delete_after(msg: discord.Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

# ── BYPASS ENGINE ────────────────────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "FMD-Bot/1.0"})

_BYPASS_RESULT_KEYS = (
    "content", "result", "loadstring", "bypassed", "bypassed_link",
    "bypassed_url", "final_url", "destination", "url", "link", "key", "output"
)

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for key in _BYPASS_RESULT_KEYS:
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, (dict, list)):
                    nested = _extract_bypass_result(value)
                    if nested: return nested
        for value in data.values():
            if isinstance(value, (dict, list)):
                nested = _extract_bypass_result(value)
                if nested: return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_bypass_result(item)
            if nested: return nested
    return None

def bypass_url_vps(url: str):
    for attempt in range(1, 4):
        try:
            resp = _http_session.get(BYPASS_API_ENDPOINT + quote(url, safe=""), timeout=45)
            if resp.status_code != 200:
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, f"HTTP {resp.status_code}"
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"):
                    return txt, None
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, "Invalid API response"
            api_says_error = False
            if isinstance(data, dict):
                if data.get("success") is False or data.get("error") or str(data.get("status", "")).lower() == "error":
                    api_says_error = True
            result = _extract_bypass_result(data)
            if result and not api_says_error:
                return str(result), None
            if api_says_error:
                err_msg = data.get("message") or data.get("error") if isinstance(data, dict) else None
                last_error = str(err_msg or "API reported an error.")
                if attempt < 3:
                    time.sleep(2)
                    continue
                return None, last_error
            return None, "No result found in API."
        except requests.exceptions.Timeout:
            if attempt < 3:
                time.sleep(2)
        except Exception as e:
            if attempt < 3:
                time.sleep(2)
    return None, "Request timed out after retries."

# ── BYPASS EMBEDS ────────────────────────────────────────────────
def embed_loading() -> discord.Embed:
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_LOADER} Generating Bypass..."
    e.description = "Please wait..."
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float) -> discord.Embed:
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.add_field(
        name=f"{EMOJI_KEY} Result",
        value=f"```txt\n{result[:1000]}\n```",
        inline=False
    )
    e.add_field(
        name=f"{EMOJI_CLOCK} Duration",
        value=f"`{elapsed:.2f}s`",
        inline=True
    )
    e.add_field(
        name=f"{EMOJI_SUCCESS} Status",
        value="Successfully Generated",
        inline=True
    )
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")  # Green Crown
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float) -> discord.Embed:
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.title = f"{EMOJI_GREEN_DOT} Bypass Failed"
    e.description = f"```\n{error or 'Unknown error'}\n```"
    e.add_field(
        name=f"{EMOJI_CLOCK} Duration",
        value=f"`{elapsed:.2f}s`",
        inline=True
    )
    e.set_footer(text=_footer())
    return e

# ── BYPASS VIEW ──────────────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(label="Discord", emoji=EMOJI_DISCORD, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Invite", emoji=EMOJI_INVITE, url=BOT_INVITE_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="Copy", emoji=EMOJI_COPY, style=discord.ButtonStyle.secondary, row=0)
    async def copy_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"```txt\n{self._result[:1900]}\n```",
            ephemeral=True
        )

# ── HEALTH SERVER ────────────────────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f'{{"status":"online","bot":"FMD BOT","uptime":"{_uptime()}"}}'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
    def log_message(self, *_): pass

def start_web():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Health server running on port {PORT}")

# ── BOT CLIENT ────────────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Commands synced successfully!")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} ({self.user.id})")
        logger.info(f"Serving {len(self.guilds)} servers")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # AUTO-BYPASS
        if message.channel.id in autobypass_channels:
            try:
                await message.delete()
            except:
                pass
            urls = _URL_PATTERN.findall(message.content)
            if urls:
                await self._auto_bypass(message, urls)

        # XP system
        if not message.author.bot:
            guild_id = str(message.guild.id)
            user_id = str(message.author.id)
            levels = load_json(LEVELS_FILE, {})
            levels.setdefault(guild_id, {}).setdefault(user_id, {"xp": 0, "level": 0})
            entry = levels[guild_id][user_id]
            entry["xp"] += random.randint(5, 15)
            if entry["xp"] >= xp_needed(entry["level"]):
                entry["level"] += 1
                entry["xp"] = 0
                try:
                    msg = await message.channel.send(f"{EMOJI_ROCKET} {message.author.mention} leveled up to **Level {entry['level']}**!")
                    # Auto-delete after 5 seconds
                    asyncio.create_task(_delete_after(msg, 5))
                except:
                    pass
                save_json(LEVELS_FILE, levels)

    async def _auto_bypass(self, message: discord.Message, urls: list):
        loop = asyncio.get_running_loop()
        for url in urls[:1]:
            if not _is_valid_url(url):
                continue
            try:
                status_msg = await message.channel.send(content=message.author.mention, embed=embed_loading())
            except:
                continue
            t0 = time.time()
            result, error = await loop.run_in_executor(None, bypass_url_vps, url)
            elapsed = time.time() - t0
            try:
                if result:
                    embed = embed_success(result, elapsed)
                    view = FmdBypassView(result)
                    msg = await status_msg.edit(content=message.author.mention, embed=embed, view=view)
                    asyncio.create_task(_delete_after(msg, 120))
                else:
                    embed = embed_fail(error, elapsed)
                    msg = await status_msg.edit(content=message.author.mention, embed=embed)
                    asyncio.create_task(_delete_after(msg, 120))
            except:
                pass

bot = FmdBot()
tree = bot.tree

# ==================== ERROR HANDLER ====================
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"{EMOJI_WARNING} An unexpected error occurred."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except:
        pass

# ==================== BYPASS COMMANDS ====================
@tree.command(name="bypass", description="Bypass a link manually")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_valid_url(url):
        e = discord.Embed(description=f"{EMOJI_WARNING} Invalid URL.", color=C_WARN)
        e.set_footer(text=_footer())
        return await interaction.response.send_message(embed=e, ephemeral=True)

    await interaction.response.send_message(embed=embed_loading())

    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, bypass_url_vps, url)
    elapsed = time.time() - t0

    try:
        if result:
            embed = embed_success(result, elapsed)
            view = FmdBypassView(result)
            msg = await interaction.edit_original_response(embed=embed, view=view)
            asyncio.create_task(_delete_after(msg, 120))
        else:
            embed = embed_fail(error, elapsed)
            msg = await interaction.edit_original_response(embed=embed)
            asyncio.create_task(_delete_after(msg, 120))
    except Exception as e:
        logger.error(f"Error editing response: {e}")

@tree.command(name="setautobypass", description="[Admin] Toggle auto-bypass in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    autobypass_channels = load_json(AUTOBYPASS_CHANNELS_FILE, set())
    if cid in autobypass_channels:
        autobypass_channels.discard(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))
        embed = discord.Embed(
            title="Auto-Bypass Disabled",
            color=C_ERROR
        )
    else:
        autobypass_channels.add(cid)
        save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))
        embed = discord.Embed(
            title=f"{EMOJI_GREEN_DOT} Auto-Bypass Enabled",
            color=C_GREEN
        )
        embed.description = f"Every message in {interaction.channel.mention} will be deleted; links will be auto-bypassed."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== TICKETS COMMANDS ====================
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="📩 Create Ticket", style=discord.ButtonStyle.success, custom_id="ticket_create"))

@tree.command(name="setup-ticket", description="[Admin] Send the ticket panel in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI_TICKET} Support Center",
        description="Need help? Click the button below to create a ticket.",
        color=C_BLUE
    )
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, view=TicketPanelView())

class TicketCreateModal(Modal):
    def __init__(self):
        super().__init__(title="Create Ticket")
        self.reason = TextInput(label="Reason / Category", placeholder="e.g. General Support, Billing", max_length=100)
        self.desc = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Describe your issue", max_length=1000)
        self.add_item(self.reason)
        self.add_item(self.desc)

    async def on_submit(self, interaction: discord.Interaction):
        for ch in interaction.guild.channels:
            if ch.name.startswith("ticket-") and ch.name.endswith(interaction.user.name.lower().replace(" ", "-")):
                return await interaction.response.send_message(f"{EMOJI_WARNING} You already have an open ticket.", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}"
        try:
            ch = await interaction.guild.create_text_channel(channel_name, overwrites=overwrites, reason="Ticket created")
        except:
            return await interaction.response.send_message(f"{EMOJI_FAILED} Failed to create ticket channel.", ephemeral=True)
        embed = discord.Embed(title=f"{EMOJI_TICKET} Ticket Created", color=C_BLUE)
        embed.description = "Welcome! Please explain your issue. A staff member will be with you shortly."
        embed.add_field(name="👤 User", value=interaction.user.mention, inline=False)
        embed.add_field(name="📂 Reason", value=self.reason.value, inline=False)
        embed.set_footer(text=_footer())
        view = TicketChannelView(interaction.user.id)
        await ch.send(content=interaction.user.mention, embed=embed, view=view)
        await interaction.response.send_message(f"{EMOJI_SUCCESS} Ticket created: {ch.mention}", ephemeral=True)

class TicketChannelView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.add_item(Button(label=f"{EMOJI_LOCK} Close", style=discord.ButtonStyle.danger, custom_id="ticket_close"))
        self.add_item(Button(label=f"{EMOJI_OWNER} Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim"))
        self.add_item(Button(label=f"{EMOJI_UNLOCK} Unclaim", style=discord.ButtonStyle.secondary, custom_id="ticket_unclaim"))
        self.add_item(Button(label=f"{EMOJI_ADD} Add", style=discord.ButtonStyle.success, custom_id="ticket_add"))
        self.add_item(Button(label=f"{EMOJI_DELETE} Remove", style=discord.ButtonStyle.danger, custom_id="ticket_remove"))
        self.add_item(Button(label=f"{EMOJI_DOCUMENT} Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    custom_id = interaction.data["custom_id"]
    if custom_id == "ticket_create":
        return await interaction.response.send_modal(TicketCreateModal())
    if custom_id.startswith("ticket_"):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(f"{EMOJI_WARNING} Not a ticket channel.", ephemeral=True)
        if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(f"{EMOJI_WARNING} Staff only.", ephemeral=True)
        if custom_id == "ticket_close":
            await interaction.channel.edit(name=f"closed-{interaction.channel.name[7:]}")
            embed = discord.Embed(title=f"{EMOJI_LOCK} Ticket Closed", color=C_RED)
            embed.add_field(name="Closed By", value=interaction.user.mention)
            embed.set_footer(text=_footer())
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("Ticket closed.", ephemeral=True)
        elif custom_id == "ticket_claim":
            embed = discord.Embed(title=f"{EMOJI_OWNER} Ticket Claimed", color=C_GREEN)
            embed.add_field(name="Staff", value=interaction.user.mention)
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("Claimed.", ephemeral=True)
        elif custom_id == "ticket_unclaim":
            embed = discord.Embed(title=f"{EMOJI_UNLOCK} Ticket Unclaimed", color=C_ORANGE)
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("Unclaimed.", ephemeral=True)
        elif custom_id == "ticket_add":
            class AddUserModal(Modal):
                def __init__(self):
                    super().__init__(title="Add User")
                    self.uid = TextInput(label="User ID or Mention")
                    self.add_item(self.uid)
                async def on_submit(self, i: discord.Interaction):
                    match = re.search(r"\d+", self.uid.value)
                    if not match:
                        return await i.response.send_message("Invalid user.", ephemeral=True)
                    member = i.guild.get_member(int(match.group()))
                    if not member:
                        return await i.response.send_message("User not found.", ephemeral=True)
                    await i.channel.set_permissions(member, view_channel=True, send_messages=True)
                    await i.response.send_message(f"{EMOJI_SUCCESS} Added {member.mention}", ephemeral=True)
            await interaction.response.send_modal(AddUserModal())
        elif custom_id == "ticket_remove":
            class RemoveUserModal(Modal):
                def __init__(self):
                    super().__init__(title="Remove User")
                    self.uid = TextInput(label="User ID or Mention")
                    self.add_item(self.uid)
                async def on_submit(self, i: discord.Interaction):
                    match = re.search(r"\d+", self.uid.value)
                    if not match:
                        return await i.response.send_message("Invalid user.", ephemeral=True)
                    member = i.guild.get_member(int(match.group()))
                    if not member:
                        return await i.response.send_message("User not found.", ephemeral=True)
                    await i.channel.set_permissions(member, overwrite=None)
                    await i.response.send_message(f"{EMOJI_SUCCESS} Removed {member.mention}", ephemeral=True)
            await interaction.response.send_modal(RemoveUserModal())
        elif custom_id == "ticket_transcript":
            messages = []
            async for msg in interaction.channel.history(limit=200):
                messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
            txt = "\n".join(messages)
            file = discord.File(io.BytesIO(txt.encode()), filename=f"{interaction.channel.name}_transcript.txt")
            embed = discord.Embed(title=f"{EMOJI_DOCUMENT} Transcript", color=C_DARK_BLUE)
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

@tree.command(name="ticket", description="Create a ticket manually")
async def ticket_cmd(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketCreateModal())

@tree.command(name="close", description="Close the current ticket")
async def close_ticket_cmd(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message(f"{EMOJI_WARNING} Not a ticket channel.", ephemeral=True)
    await interaction.channel.edit(name=f"closed-{interaction.channel.name[7:]}")
    embed = discord.Embed(title=f"{EMOJI_LOCK} Ticket Closed", color=C_RED)
    embed.add_field(name="Closed By", value=interaction.user.mention)
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("Ticket closed.", ephemeral=True)

@tree.command(name="add", description="Add a user to the current ticket")
async def add_ticket_cmd(interaction: discord.Interaction, user: discord.Member):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message(f"{EMOJI_WARNING} Not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
    await interaction.response.send_message(f"{EMOJI_SUCCESS} Added {user.mention}.", ephemeral=True)

@tree.command(name="remove", description="Remove a user from the current ticket")
async def remove_ticket_cmd(interaction: discord.Interaction, user: discord.Member):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message(f"{EMOJI_WARNING} Not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"{EMOJI_SUCCESS} Removed {user.mention}.", ephemeral=True)

@tree.command(name="transcript", description="Generate a transcript of the current ticket")
async def transcript_ticket_cmd(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message(f"{EMOJI_WARNING} Not a ticket channel.", ephemeral=True)
    messages = []
    async for msg in interaction.channel.history(limit=300):
        messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
    txt = "\n".join(messages)
    file = discord.File(io.BytesIO(txt.encode()), filename=f"{interaction.channel.name}_transcript.txt")
    embed = discord.Embed(title=f"{EMOJI_DOCUMENT} Transcript Generated", color=C_DARK_BLUE)
    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

# ==================== GIVEAWAY COMMANDS ====================
giveaway_group = app_commands.Group(name="giveaway", description="Giveaway commands")

@giveaway_group.command(name="start", description="Start a new giveaway")
@app_commands.describe(prize="Prize", duration="Duration (e.g. 10m, 1h, 1d)", winners="Number of winners")
@app_commands.checks.has_permissions(manage_guild=True)
async def gstart(interaction: discord.Interaction, prize: str, duration: str, winners: app_commands.Range[int, 1, 10] = 1):
    seconds = 0
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return await interaction.response.send_message("Invalid duration. Use `10m`, `1h`, `1d`.", ephemeral=True)
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s": seconds = val
    elif unit == "m": seconds = val * 60
    elif unit == "h": seconds = val * 3600
    elif unit == "d": seconds = val * 86400
    if seconds < 10:
        return await interaction.response.send_message("Minimum duration is 10 seconds.", ephemeral=True)
    end_time = time.time() + seconds
    embed = discord.Embed(title=f"{EMOJI_GIVEAWAY} Giveaway Started", color=C_GOLD)
    embed.add_field(name="🎁 Prize", value=prize, inline=False)
    embed.add_field(name="👑 Host", value=interaction.user.mention, inline=True)
    embed.add_field(name="🏆 Winners", value=str(winners), inline=True)
    embed.add_field(name="⏰ Ends", value=f"<t:{int(end_time)}:R>", inline=True)
    embed.add_field(name="👥 Entries", value="0", inline=True)
    embed.set_footer(text=_footer())
    msg = await interaction.response.send_message(embed=embed, wait=True)
    gid = str(msg.id)
    giveaways = load_json(GIVEAWAYS_FILE, {})
    giveaways[gid] = {"prize": prize, "winners": winners, "end_time": end_time, "host": str(interaction.user.id), "channel": interaction.channel_id, "participants": [], "ended": False}
    save_json(GIVEAWAYS_FILE, giveaways)
    view = View()
    view.add_item(Button(label="🎉 Join", style=discord.ButtonStyle.success, custom_id=f"give_join_{gid}"))
    await msg.edit(view=view)
    asyncio.create_task(_giveaway_loop(gid))

async def _giveaway_loop(gid: str):
    await asyncio.sleep(1)
    while True:
        giveaways = load_json(GIVEAWAYS_FILE, {})
        g = giveaways.get(gid)
        if not g or g.get("ended"):
            break
        if time.time() >= g["end_time"]:
            await _end_giveaway(gid)
            break
        await asyncio.sleep(5)

async def _end_giveaway(gid: str):
    giveaways = load_json(GIVEAWAYS_FILE, {})
    g = giveaways.get(gid)
    if not g or g.get("ended"):
        return
    g["ended"] = True
    participants = g.get("participants", [])
    channel = bot.get_channel(g["channel"])
    if channel:
        try:
            msg = await channel.fetch_message(int(gid))
            if not participants:
                embed = discord.Embed(title="🎊 Giveaway Ended", description="No valid participants.", color=C_ERROR)
                await msg.edit(embed=embed, view=None)
            else:
                winners = random.sample(participants, min(g["winners"], len(participants)))
                mentions = " ".join([f"<@{w}>" for w in winners])
                embed = discord.Embed(title="🎊 Giveaway Ended", color=C_GOLD)
                embed.description = f"**Prize:** {g['prize']}\n🏆 **Winner(s):** {mentions}"
                await msg.edit(embed=embed, view=None)
                await channel.send(f"🎉 Congratulations {mentions}! You won **{g['prize']}**!")
        except:
            pass
    save_json(GIVEAWAYS_FILE, giveaways)

@giveaway_group.command(name="end", description="End a giveaway early")
@app_commands.checks.has_permissions(manage_guild=True)
async def gend(interaction: discord.Interaction):
    giveaways = load_json(GIVEAWAYS_FILE, {})
    active = [gid for gid, g in giveaways.items() if not g.get("ended") and g.get("channel") == interaction.channel_id]
    if not active:
        return await interaction.response.send_message("No active giveaways in this channel.", ephemeral=True)
    options = [discord.SelectOption(label=giveaways[gid]["prize"][:80], value=gid) for gid in active[:25]]
    class Sel(discord.ui.Select):
        async def callback(self, i: discord.Interaction):
            gid = self.values[0]
            await _end_giveaway(gid)
            await i.response.send_message("Giveaway ended.", ephemeral=True)
    view = View()
    view.add_item(Sel(placeholder="Select giveaway", options=options))
    await interaction.response.send_message("Select which giveaway to end:", view=view, ephemeral=True)

@giveaway_group.command(name="reroll", description="Reroll a giveaway winner")
@app_commands.checks.has_permissions(manage_guild=True)
async def greroll(interaction: discord.Interaction):
    giveaways = load_json(GIVEAWAYS_FILE, {})
    ended = [gid for gid, g in giveaways.items() if g.get("ended") and g.get("channel") == interaction.channel_id and len(g.get("participants", [])) > 1]
    if not ended:
        return await interaction.response.send_message("No eligible ended giveaways.", ephemeral=True)
    options = [discord.SelectOption(label=giveaways[gid]["prize"][:80], value=gid) for gid in ended[:25]]
    class Sel(discord.ui.Select):
        async def callback(self, i: discord.Interaction):
            gid = self.values[0]
            g = giveaways[gid]
            participants = g.get("participants", [])
            if len(participants) < 2:
                return await i.response.send_message("Not enough participants.", ephemeral=True)
            winner = random.choice(participants)
            await i.channel.send(f"🎉 New winner: <@{winner}>!")
            await i.response.send_message("Rerolled.", ephemeral=True)
    view = View()
    view.add_item(Sel(placeholder="Select giveaway", options=options))
    await interaction.response.send_message("Select which giveaway to reroll:", view=view, ephemeral=True)

@giveaway_group.command(name="list", description="List all giveaways")
async def glist(interaction: discord.Interaction):
    giveaways = load_json(GIVEAWAYS_FILE, {})
    guild_g = {gid: g for gid, g in giveaways.items() if g.get("channel") == interaction.channel_id}
    if not guild_g:
        return await interaction.response.send_message("No giveaways in this channel.", ephemeral=True)
    embed = discord.Embed(title=f"{EMOJI_GIVEAWAY} Giveaway List", color=C_INFO)
    active, ended = [], []
    for gid, g in guild_g.items():
        if g.get("ended"):
            ended.append(f"🎁 {g['prize']} (Ended)")
        else:
            active.append(f"🎁 {g['prize']} - <t:{int(g['end_time'])}:R>")
    if active: embed.add_field(name="🟢 Active", value="\n".join(active[:10]), inline=False)
    if ended: embed.add_field(name="🔴 Ended", value="\n".join(ended[:10]), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

tree.add_command(giveaway_group)

# ==================== MODERATION COMMANDS ====================
@tree.command(name="ban", description="[Mod] Ban a user")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(f"{EMOJI_WARNING} Cannot ban this user.", ephemeral=True)
    try:
        await member.ban(reason=reason, delete_message_days=0)
        embed = discord.Embed(title=f"{EMOJI_ADMIN} User Banned", description=f"**{member}** banned.\nReason: {reason}", color=C_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="kick", description="[Mod] Kick a user")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(f"{EMOJI_WARNING} Cannot kick this user.", ephemeral=True)
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title=f"{EMOJI_ADMIN} User Kicked", description=f"**{member}** kicked.\nReason: {reason}", color=C_ORANGE)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="timeout", description="[Mod] Timeout a user")
@app_commands.describe(member="User", duration="Duration (e.g. 10m, 1h)", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
    seconds = 0
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return await interaction.response.send_message("Invalid duration format.", ephemeral=True)
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s": seconds = val
    elif unit == "m": seconds = val * 60
    elif unit == "h": seconds = val * 3600
    elif unit == "d": seconds = val * 86400
    if seconds < 60:
        return await interaction.response.send_message("Minimum timeout is 1 minute.", ephemeral=True)
    if seconds > 2419200:
        return await interaction.response.send_message("Maximum timeout is 28 days.", ephemeral=True)
    try:
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.timeout(until, reason=reason)
        embed = discord.Embed(title=f"{EMOJI_CLOCK} Timeout Applied", description=f"**{member}** timed out for **{duration}**.\nReason: {reason}", color=C_ORANGE)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"{EMOJI_FAILED} Error: {e}", ephemeral=True)

@tree.command(name="warn", description="[Mod] Warn a user")
@app_commands.checks.has_permissions(kick_members=True)
async def warn_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    gid, uid = str(interaction.guild_id), str(member.id)
    warnings = load_json(WARNINGS_FILE, {})
    warnings.setdefault(gid, {}).setdefault(uid, []).append({"mod": str(interaction.user.id), "reason": reason, "ts": int(time.time())})
    save_json(WARNINGS_FILE, warnings)
    count = len(warnings[gid][uid])
    embed = discord.Embed(title=f"{EMOJI_WARNING} Warning Issued", description=f"**{member}** warned.\nReason: {reason}\nTotal: {count}", color=C_GOLD)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="clear", description="[Mod] Clear messages (max 10000)")
@app_commands.describe(amount="Amount")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_cmd(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 10000]):
    await interaction.response.defer(ephemeral=True)
    deleted = 0
    remaining = amount
    while remaining > 0:
        batch = min(remaining, 100)
        purged = await interaction.channel.purge(limit=batch)
        deleted += len(purged)
        remaining -= len(purged)
        if len(purged) < batch:
            break
    embed = discord.Embed(title=f"{EMOJI_SUCCESS} Messages Cleared", description=f"Deleted **{deleted}** messages.", color=C_GREEN)
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="lock", description="[Mod] Lock the channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock_cmd(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(title=f"{EMOJI_LOCK} Channel Locked", color=C_RED)
    await interaction.response.send_message(embed=embed)

@tree.command(name="unlock", description="[Mod] Unlock the channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock_cmd(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    embed = discord.Embed(title=f"{EMOJI_UNLOCK} Channel Unlocked", color=C_GREEN)
    await interaction.response.send_message(embed=embed)

@tree.command(name="slowmode", description="[Mod] Set slowmode (0 to disable, max 21600s)")
@app_commands.describe(seconds="Seconds")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode_cmd(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        embed = discord.Embed(title=f"{EMOJI_CLOCK} Slowmode Disabled", color=C_GREEN)
    else:
        embed = discord.Embed(title=f"{EMOJI_CLOCK} Slowmode Set", description=f"Slowmode: {seconds}s", color=C_GOLD)
    await interaction.response.send_message(embed=embed)

# ==================== UTILITY COMMANDS ====================
@tree.command(name="ping", description="Check bot latency")
async def ping_cmd(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title=f"{EMOJI_PC} Pong!", description=f"Latency: `{latency}ms`", color=C_GREEN)
    await interaction.response.send_message(embed=embed)

@tree.command(name="help", description="View all commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{EMOJI_GREEN_DOT} Help Center", description=f"Support: [Join Server]({SUPPORT_SERVER_URL})", color=C_BLUE)
    embed.add_field(name="🎫 Tickets", value="`/setup-ticket` `/ticket` `/close` `/add` `/remove` `/transcript`", inline=False)
    embed.add_field(name="🎉 Giveaways", value="`/giveaway start` `/giveaway end` `/giveaway reroll` `/giveaway list`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`/ban` `/kick` `/timeout` `/warn` `/clear` `/lock` `/unlock` `/slowmode`", inline=False)
    embed.add_field(name="📊 Utility", value="`/ping` `/help` `/serverinfo` `/userinfo` `/avatar` `/botinfo`", inline=False)
    embed.add_field(name="🎭 Fun", value="`/8ball` `/coinflip` `/dice` `/meme`", inline=False)
    embed.add_field(name="💰 Economy", value="`/balance` `/daily` `/work` `/pay`", inline=False)
    embed.add_field(name="🤖 IA", value="`/setupia`", inline=False)
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed)

@tree.command(name="serverinfo", description="Server information")
async def serverinfo_cmd(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"{EMOJI_HOME} {g.name}", color=C_INFO)
    embed.add_field(name="👑 Owner", value=g.owner.mention)
    embed.add_field(name="👥 Members", value=str(g.member_count))
    embed.add_field(name="📁 Channels", value=str(len(g.channels)))
    embed.add_field(name="🎭 Roles", value=str(len(g.roles)))
    embed.add_field(name="📅 Created", value=f"<t:{int(g.created_at.timestamp())}:R>")
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="User information")
@app_commands.describe(member="User (optional)")
async def userinfo_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"{EMOJI_MEMBER} {target.display_name}", color=C_INFO)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
    embed.add_field(name="Joined", value=f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "Unknown", inline=True)
    embed.add_field(name="Created", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="avatar", description="Get a user's avatar")
@app_commands.describe(member="User (optional)")
async def avatar_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"{EMOJI_PC} Avatar of {target.display_name}", color=C_PURPLE)
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="botinfo", description="Bot information")
async def botinfo_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{EMOJI_CROWN} Bot Information", color=C_GREEN)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Commands", value=str(len(bot.tree.get_commands())), inline=True)
    embed.add_field(name="Uptime", value=_uptime(), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
    if bot.user: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed)

# ==================== FUN COMMANDS ====================
@tree.command(name="8ball", description="Ask the magic 8-ball")
@app_commands.describe(question="Your question")
async def ball8_cmd(interaction: discord.Interaction, question: str):
    answers = ["Yes", "No", "Maybe", "Definitely", "Don't count on it"]
    embed = discord.Embed(title=f"{EMOJI_8BALL} 8-Ball", color=0x2B2D31)
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(answers), inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="coinflip", description="Flip a coin")
async def coinflip_cmd(interaction: discord.Interaction):
    result = random.choice(["🦅 Heads", "🪙 Tails"])
    embed = discord.Embed(title=f"{EMOJI_COIN} Coin Flip", description=f"Result: **{result}**", color=C_GOLD)
    await interaction.response.send_message(embed=embed)

@tree.command(name="dice", description="Roll a die")
@app_commands.describe(sides="Number of sides (4-100)")
async def dice_cmd(interaction: discord.Interaction, sides: app_commands.Range[int, 4, 100] = 6):
    result = random.randint(1, sides)
    embed = discord.Embed(title=f"{EMOJI_DICE} Dice Roll", description=f"Rolled **{result}** (1-{sides})", color=C_GREEN)
    await interaction.response.send_message(embed=embed)

@tree.command(name="meme", description="Random meme from Reddit")
async def meme_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    sub = random.choice(["memes", "dankmemes", "wholesomememes"])
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://www.reddit.com/r/{sub}/random.json?limit=1"
            async with session.get(url, headers={"User-Agent": "FMD-Bot/2.0"}, timeout=10) as resp:
                data = await resp.json()
                post = data[0]["data"]["children"][0]["data"]
                img = post.get("url", "")
                if not img.lower().endswith((".jpg", ".png", ".gif", ".jpeg")):
                    return await interaction.followup.send("No image found.", ephemeral=True)
                embed = discord.Embed(title=post.get("title", "Meme"), color=C_FUN)
                embed.set_image(url=img)
                await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send("Error fetching meme.", ephemeral=True)

# ==================== ECONOMY COMMANDS ====================
@tree.command(name="balance", description="Check your balance")
@app_commands.describe(member="User (optional)")
async def balance_cmd(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    uid = str(target.id)
    economy = load_json(ECONOMY_FILE, {})
    economy.setdefault(uid, {"cash": 0, "bank": 0})
    data = economy[uid]
    embed = discord.Embed(title=f"{EMOJI_MONEY} Wallet", color=C_GREEN)
    embed.add_field(name="User", value=target.mention, inline=True)
    embed.add_field(name="Cash", value=f"${data['cash']:,}", inline=True)
    embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
    embed.add_field(name="Total", value=f"${data['cash'] + data['bank']:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="daily", description="Claim your daily reward")
async def daily_cmd(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE, {})
    economy.setdefault(uid, {"cash": 0, "bank": 0, "daily": 0})
    now = time.time()
    if now - economy[uid].get("daily", 0) < 86400:
        remaining = 86400 - (now - economy[uid]["daily"])
        return await interaction.response.send_message(f"⏰ Wait {int(remaining//3600)}h {int((remaining%3600)//60)}m.", ephemeral=True)
    reward = random.randint(100, 500)
    economy[uid]["cash"] += reward
    economy[uid]["daily"] = now
    save_json(ECONOMY_FILE, economy)
    embed = discord.Embed(title=f"{EMOJI_GIFT} Daily Reward", description=f"You received **${reward}**!", color=C_GOLD)
    await interaction.response.send_message(embed=embed)

@tree.command(name="work", description="Work to earn cash")
async def work_cmd(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE, {})
    economy.setdefault(uid, {"cash": 0, "bank": 0, "work": 0})
    now = time.time()
    if now - economy[uid].get("work", 0) < 3600:
        remaining = 3600 - (now - economy[uid]["work"])
        return await interaction.response.send_message(f"⏰ Wait {int(remaining//60)}m.", ephemeral=True)
    earnings = random.randint(50, 200)
    economy[uid]["cash"] += earnings
    economy[uid]["work"] = now
    save_json(ECONOMY_FILE, economy)
    embed = discord.Embed(title=f"{EMOJI_BITCASH} Work Complete", description=f"You earned **${earnings}**!", color=C_GREEN)
    await interaction.response.send_message(embed=embed)

@tree.command(name="pay", description="Pay another user")
@app_commands.describe(member="Recipient", amount="Amount")
async def pay_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        return await interaction.response.send_message("Amount must be positive.", ephemeral=True)
    uid = str(interaction.user.id)
    economy = load_json(ECONOMY_FILE, {})
    economy.setdefault(uid, {"cash": 0, "bank": 0})
    if economy[uid]["cash"] < amount:
        return await interaction.response.send_message("Not enough cash.", ephemeral=True)
    economy[uid]["cash"] -= amount
    economy.setdefault(str(member.id), {"cash": 0, "bank": 0})["cash"] += amount
    save_json(ECONOMY_FILE, economy)
    embed = discord.Embed(title=f"{EMOJI_MONEY} Payment Sent", description=f"Paid {member.mention} **${amount}**.", color=C_GREEN)
    await interaction.response.send_message(embed=embed)

# ==================== IA COMMANDS ====================
@tree.command(name="setupia", description="[Admin] Toggle IA auto-reply in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setupia_cmd(interaction: discord.Interaction):
    cid = str(interaction.channel_id)
    ia_config = load_json(IA_CONFIG_FILE, {})
    channels = ia_config.get("channels", [])
    if cid in channels:
        channels.remove(cid)
        ia_config["channels"] = channels
        save_json(IA_CONFIG_FILE, ia_config)
        embed = discord.Embed(title="🤖 IA Disabled", color=C_ERROR)
    else:
        channels.append(cid)
        ia_config["channels"] = channels
        save_json(IA_CONFIG_FILE, ia_config)
        embed = discord.Embed(title=f"{EMOJI_GREEN_DOT} IA Enabled", color=C_GREEN)
    embed.description = f"{interaction.channel.mention} will auto-reply with OpenRouter."
    embed.set_footer(text=_footer())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== START BOT ====================
async def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set!")
        return
    start_web()
    logger.info("Starting FMD BOT...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
