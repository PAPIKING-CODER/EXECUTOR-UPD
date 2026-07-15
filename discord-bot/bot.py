import os
import re
import json
import time
import asyncio
import logging
import threading
import random
import datetime
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View, Select
import requests
from dotenv import load_dotenv

load_dotenv()

# ── LOGGING ──────────────────────────────────────────────────────
LOG_FILE = "bot_logs.txt"
logger = logging.getLogger("FMD_BOT")
logger.setLevel(logging.INFO)
_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_file_handler.setFormatter(_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# ── CONFIGURACIÓN ──────────────────────────────────────────────
DISCORD_TOKEN      = os.environ.get("DISCORD_TOKEN", "")
PORT               = int(os.environ.get("PORT", "8080"))
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525629900038475969")

VPS_BYPASS_ENDPOINT    = "https://4pi-bypass.vercel.app/api/bypass?url="
VPS_BYPASS_TIMEOUT     = 30
VPS_BYPASS_MAX_RETRIES = 3
VPS_BYPASS_RETRY_DELAY = 3

AUTOBYPASS_CHANNELS_FILE = "autobypass_channels.json"

# ── TODOS TUS EMOJIS PERSONALIZADOS ────────────────────────────
EMOJI_ADMIN             = "<:admin:1526850858271248384>"
EMOJI_ALARM             = "<a:alarm:1525787989354086411>"
EMOJI_ANNOUNCEMENT      = "<:announcementpingroleicon:1526855584807256124>"
EMOJI_ATTENTION         = "<a:attention:1526850359958704138>"
EMOJI_AWESOMEFACE14     = "<a:awesomeface14:1526850663575982222>"
EMOJI_BITCASH           = "<a:bitcash:1526850558726508564>"
EMOJI_CAMERA_RED_LOGO   = "<a:cameraredlogo:1526854158680981504>"
EMOJI_CART              = "<:cart:1526854833125195786>"
EMOJI_CLOCK             = "<a:clock:1525380296852377711>"
EMOJI_CLOWN1            = "<a:clown:1526858087510835252>"
EMOJI_CLOWN2            = "<a:clown2:1526858673404510268>"
EMOJI_COPY_PASTE        = "<:copypaste:1525379105111932958>"
EMOJI_CURSOR_CLICK      = "<a:cursor_click:1526857184116477962>"
EMOJI_DARK_BLUE_ARROW   = "<a:darkbluearrow:1526850610547396690>"
EMOJI_DIAMOND           = "<a:diamond:1526858613572894780>"
EMOJI_DISCORD           = "<:discord:1526743527642501273>"
EMOJI_DISCORD_LOGO      = "<:discordlogo:1526855246897348741>"
EMOJI_EMOJIGG_MOD       = "<:emojigg_mod:1526851052933222420>"
EMOJI_EMOJIGG_PC        = "<:emojigg_pc:1526858555544572035>"
EMOJI_EMOJIGG_XP        = "<a:emojigg_xp:1526851177625550854>"
EMOJI_EMOJIGG_XP2       = "<a:emojigg_xp2:1526852954563280926>"
EMOJI_FAILED            = "<a:failed:1526857565156147250>"
EMOJI_GIFT              = "<a:gift:1526817190660280360>"
EMOJI_GIVEAWAY          = "<a:giveaway:1526817132501798983>"
EMOJI_GLOWING_DOT_GREEN = "<:glowing_dot_green:1525383175889485848>"
EMOJI_GOLD_KEY1         = "<:gold_key:1525381310200414310>"
EMOJI_GOLD_KEY2         = "<:gold_key2:1526743159038803978>"
EMOJI_GOLD_MAIL         = "<:goldmail:1526859133498822746>"
EMOJI_GOLDEN_SPIN_COIN  = "<a:goldenspincoin:1526850486387605504>"
EMOJI_GREEN_CROWN       = "<a:greencrown:1526742765311098980>"
EMOJI_GREEN_DOT         = "<a:greendot:1526742445323190272>"
EMOJI_GREEN_MEMBER      = "<:greenmember:1526855758686322697>"
EMOJI_GREEN_SIREN       = "<a:green_siren:1526856177055563826>"
EMOJI_HOUSE             = "<:house:1526854349110640690>"
EMOJI_INFORMATION       = "<:information:1526852173852315799>"
EMOJI_LIGHTNING_GREEN   = "<:lightninggreen:1525379640498065538>"
EMOJI_LIME_GREEN_CROWN  = "<:limegreendrippingglowingcrown:1526854700434198558>"
EMOJI_LINK              = "<:link:1525379856034959422>"
EMOJI_LOADER1           = "<a:loader:1526741970226253834>"
EMOJI_LOADER2           = "<a:loader2:1526856926413979739>"
EMOJI_LOVE_MAIL         = "<a:lovemail:1526859184900018228>"
EMOJI_MATAMISON         = "<a:matamison:1526857044068667456>"
EMOJI_MEMBER            = "<:member:1526851357330505822>"
EMOJI_MONEY             = "<a:money:1526852670743380031>"
EMOJI_NEON_GREEN_APPLE  = "<:neon_greenapple:1526854612244631643>"
EMOJI_OWNER             = "<:owner:1526850915418509362>"
EMOJI_PHONE             = "<:phone:1526858219958567003>"
EMOJI_POINT             = "<:point:1526853458798313573>"
EMOJI_RED_DOT           = "<a:reddot:1526857479294681198>"
EMOJI_RED_SIREN         = "<a:red_siren:1526856057316704317>"
EMOJI_ROLE              = "<a:role:1526853667502948443>"
EMOJI_SEARCH1           = "<:search:1526851410283728898>"
EMOJI_SEARCH2           = "<:search2:1526854204218671155>"
EMOJI_SETTINGS          = "<:settings:1526853210231410810>"
EMOJI_SUCCESS1          = "<a:success:1525379448768303207>"
EMOJI_SUCCESS2          = "<:success2:1526742163050991616>"
EMOJI_TICKET            = "<:ticket:1526851476280836256>"
EMOJI_VOICE_INVITE      = "<:voice_invite:1526743390488756236>"
EMOJI_WARNING_ICON      = "<:warningicon:1526855124134137856>"
EMOJI_YELLOW_SIREN      = "<a:yellow_siren:1526856416692797481>"

# Para botones
EMOJI_COPY_BTN    = discord.PartialEmoji(name="fmd_copy", id=1526743644894138479)
EMOJI_DISCORD_BTN = discord.PartialEmoji(name="fmd_discord", id=1526743527642501273)
EMOJI_INVITE_BTN  = discord.PartialEmoji(name="fmd_invite", id=1526743390488756236)

# ── COLORES ──────────────────────────────────────────────────────
C_GREEN  = 0x00FF66
C_WARN   = 0xFFA500
C_ERROR  = 0xED4245
C_INFO   = 0x5865F2

# ── HELPERS ──────────────────────────────────────────────────────
BOT_START_TIME = datetime.now(timezone.utc)
_URL_RE = re.compile(r"https?://[^\s<>\"']+")

def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s<>\"']{4,}", url))

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START_TIME
    t = int(d.total_seconds())
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _footer() -> str:
    return "Made by KING\nFMD BOT • BYPASS"

def _get_platform(interaction: discord.Interaction) -> str:
    try:
        member = interaction.guild.get_member(interaction.user.id)
        if member and member.is_on_mobile():
            return EMOJI_PHONE
        else:
            return EMOJI_EMOJIGG_PC
    except Exception:
        return EMOJI_EMOJIGG_PC

def _is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator if interaction.guild else False

def _is_mod(interaction: discord.Interaction) -> bool:
    perms = interaction.user.guild_permissions
    return perms.ban_members or perms.kick_members or perms.manage_messages if interaction.guild else False

# ── MANEJO DE JSON ──────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"save_json: {e}")

autobypass_channels = set(load_json(AUTOBYPASS_CHANNELS_FILE, []))
economy_data = load_json("economy.json", {})
levels_data = load_json("levels.json", {})
warnings_data = load_json("warnings.json", {})
config_data = load_json("configs.json", {})
giveaways_data = load_json("giveaways.json", {})
tickets_data = load_json("tickets.json", {})
reminders_data = load_json("reminders.json", {})

def save_all():
    save_json("economy.json", economy_data)
    save_json("levels.json", levels_data)
    save_json("warnings.json", warnings_data)
    save_json("configs.json", config_data)
    save_json("giveaways.json", giveaways_data)
    save_json("tickets.json", tickets_data)
    save_json("reminders.json", reminders_data)
    save_json(AUTOBYPASS_CHANNELS_FILE, list(autobypass_channels))

# ── CLASE DEL BOT ──────────────────────────────────────────────
class FmdBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Comandos globales sincronizados.")

    async def on_ready(self):
        logger.info(f"✅ {self.user.name} Online! en {len(self.guilds)} servidores.")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/bypass"))

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        # AUTO-BYPASS (DETECCIÓN AUTOMÁTICA DE ENLACES)
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                try:
                    await message.delete()
                except Exception:
                    pass
                for url in urls[:3]:
                    if _is_valid_url(url):
                        loop = asyncio.get_running_loop()
                        status_msg = await message.channel.send(embed=embed_loading())
                        t0 = time.time()
                        result, error = await loop.run_in_executor(None, _bypass_sync, url)
                        elapsed = time.time() - t0
                        try:
                            if result:
                                embed = embed_success(result, elapsed, EMOJI_EMOJIGG_PC)
                                view = FmdBypassView(result)
                                msg = await status_msg.edit(embed=embed, view=view)
                                asyncio.create_task(_start_countdown(msg, embed, view))
                            else:
                                embed = embed_fail(error, elapsed, EMOJI_EMOJIGG_PC)
                                msg = await status_msg.edit(embed=embed)
                                asyncio.create_task(_start_countdown(msg, embed, View()))
                        except Exception:
                            pass
        # XP system
        uid = str(message.author.id)
        if uid not in levels_data:
            levels_data[uid] = {"xp": 0, "level": 1}
        levels_data[uid]["xp"] += random.randint(1, 3)
        if levels_data[uid]["xp"] >= levels_data[uid]["level"] * 50:
            levels_data[uid]["level"] += 1
            levels_data[uid]["xp"] = 0
            if levels_data[uid]["level"] % 5 == 0:
                await message.channel.send(f"{EMOJI_EMOJIGG_XP} {message.author.mention} ha subido al nivel **{levels_data[uid]['level']}**!")
            save_json("levels.json", levels_data)

# ── CREAR INSTANCIA DEL BOT (AHORA SÍ, ANTES DE CUALQUIER DECORADOR) ──
bot = FmdBot()

# ── MOTOR DE BYPASS (INTACTO) ──────────────────────────────────
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "FMD-Bot/1.0"})

_BYPASS_RESULT_KEYS = (
    "content", "result", "loadstring", "bypassed", "bypassed_link",
    "bypassed_url", "final_url", "destination", "url", "link", "key", "output"
)

def _extract_bypass_result(data):
    if isinstance(data, dict):
        for k in _BYPASS_RESULT_KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    nested = _extract_bypass_result(v)
                    if nested:
                        return nested
        for v in data.values():
            if isinstance(v, (dict, list)):
                nested = _extract_bypass_result(v)
                if nested:
                    return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_bypass_result(item)
            if nested:
                return nested
    return None

def _bypass_sync(url: str):
    last_error = "Error desconocido"
    for attempt in range(1, VPS_BYPASS_MAX_RETRIES + 1):
        try:
            full_url = VPS_BYPASS_ENDPOINT + quote(url, safe="")
            resp = _http_session.get(full_url, timeout=VPS_BYPASS_TIMEOUT)

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"):
                    return txt, None
                last_error = "Respuesta inválida de la API"
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            api_says_error = False
            if isinstance(data, dict):
                status_val = str(data.get("status", "")).lower()
                if data.get("success") is False or data.get("error") or status_val == "error":
                    api_says_error = True

            result = _extract_bypass_result(data)

            if result and not api_says_error:
                return str(result), None

            if api_says_error:
                err_msg = None
                if isinstance(data, dict):
                    err_msg = data.get("message") or data.get("error")
                last_error = str(err_msg or "La API reportó un error.")
                if attempt < VPS_BYPASS_MAX_RETRIES:
                    time.sleep(VPS_BYPASS_RETRY_DELAY)
                    continue
                return None, last_error

            return None, "No se encontró resultado en la API."

        except requests.exceptions.Timeout:
            last_error = f"Tiempo de espera agotado ({VPS_BYPASS_TIMEOUT}s)"
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)
        except Exception as e:
            last_error = str(e)[:100]
            if attempt < VPS_BYPASS_MAX_RETRIES:
                time.sleep(VPS_BYPASS_RETRY_DELAY)

    return None, last_error

# ── EMBEDS DE BYPASS (Diseño Premium) ──────────────────────────
def embed_loading():
    e = discord.Embed(color=C_WARN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_LOADER1} Generating Bypass..."
    e.description = "Processing your link...\nPlease wait..."
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526741970226253834.gif")
    e.set_footer(text=_footer())
    return e

def embed_success(result: str, elapsed: float, platform_emoji: str):
    e = discord.Embed(color=C_GREEN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Completed"
    e.description = f"Generated successfully.\n{EMOJI_CLOCK} Auto delete in `120s`"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name=f"{EMOJI_GOLD_KEY2} Result", value=f"```txt\n{result[:900]}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name=f"{EMOJI_SUCCESS1} Status", value="`Successfully Generated`", inline=True)
    e.add_field(name="Platform", value=platform_emoji, inline=True)
    e.set_footer(text=_footer())
    return e

def embed_fail(error: str, elapsed: float, platform_emoji: str):
    e = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{EMOJI_GREEN_DOT} FMD BOT • BYPASS")
    e.title = f"{EMOJI_GREEN_DOT} Bypass Failed"
    e.description = "Something went wrong!"
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name="Error", value=f"```\n{error or 'Unknown error'}\n```", inline=False)
    e.add_field(name=f"{EMOJI_CLOCK} Duration", value=f"`{elapsed:.2f}s`", inline=True)
    e.add_field(name="Platform", value=platform_emoji, inline=True)
    e.set_footer(text=_footer())
    return e

# ── VISTA DE BYPASS ─────────────────────────────────────────────
class FmdBypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._result = result
        self.add_item(Button(label="Discord", emoji=EMOJI_DISCORD_BTN, url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
        self.add_item(Button(label="Invite", emoji=EMOJI_INVITE_BTN, url=BOT_INVITE_URL, style=discord.ButtonStyle.link))

    @discord.ui.button(emoji=EMOJI_COPY_BTN, label="Copy", style=discord.ButtonStyle.success)
    async def copy_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"```txt\n{self._result}\n```", ephemeral=True)

# ── CUENTA REGRESIVA REUTILIZABLE ──────────────────────────────
async def _start_countdown(message: discord.Message, base_embed: discord.Embed, view: View, seconds: int = 120):
    clock_emoji = EMOJI_CLOCK
    while seconds > 0:
        try:
            new_embed = base_embed.copy()
            field_updated = False
            for i, field in enumerate(new_embed.fields):
                if field.name == f"{clock_emoji} Auto Delete":
                    new_embed.set_field_at(i, name=field.name, value=f"`{seconds}s remaining`", inline=field.inline)
                    field_updated = True
                    break
            if not field_updated:
                new_embed.add_field(name=f"{clock_emoji} Auto Delete", value=f"`{seconds}s remaining`", inline=False)
            await message.edit(embed=new_embed, view=view)
            await asyncio.sleep(1)
            seconds -= 1
        except (discord.NotFound, discord.HTTPException):
            break
    try:
        await message.delete()
    except Exception:
        pass

# ==============================================================
#  🎁 GIVEAWAY
# ==============================================================
giveaway_group = app_commands.Group(name="giveaway", description="Sistema de sorteos")

@giveaway_group.command(name="crear", description="🎁 Crear un nuevo giveaway")
@app_commands.describe(premio="Premio del sorteo", minutos="Duración en minutos", ganadores="Número de ganadores (default 1)")
async def gv_crear(interaction: discord.Interaction, premio: str, minutos: int, ganadores: int = 1):
    end_time = datetime.now(timezone.utc) + datetime.timedelta(minutes=minutos)
    e = discord.Embed(title=f"{EMOJI_GIVEAWAY} GIVEAWAY", description=f"**Premio:** {premio}\n**Duración:** {minutos} minutos\n**Ganadores:** {ganadores}\n**Host:** {interaction.user.mention}\nReacciona con 🎉 para participar!", color=C_GREEN, timestamp=end_time)
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    await msg.add_reaction("🎉")
    giveaways_data[str(msg.id)] = {"prize": premio, "winners": ganadores, "end": end_time.isoformat(), "host": str(interaction.user.id), "channel": interaction.channel_id, "message_id": msg.id}
    save_json("giveaways.json", giveaways_data)
    asyncio.create_task(_giveaway_countdown(msg, premio, ganadores, end_time, interaction.channel))

async def _giveaway_countdown(msg: discord.Message, premio: str, ganadores: int, end_time: datetime, channel: discord.TextChannel):
    await asyncio.sleep(max(0, (end_time - datetime.now(timezone.utc)).total_seconds()))
    msg = await channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if not reaction:
        await channel.send("❌ Nadie participó en el giveaway.")
        return
    users = [u async for u in reaction.users() if not u.bot]
    if not users:
        await channel.send("❌ No hay participantes válidos.")
        return
    selected = random.sample(users, min(ganadores, len(users)))
    mentions = " ".join(u.mention for u in selected)
    e = discord.Embed(title=f"{EMOJI_GOLDEN_SPIN_COIN} ¡GIVEAWAY TERMINADO!", description=f"**Premio:** {premio}\n🏆 **Ganador(es):** {mentions}", color=C_GREEN)
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.set_footer(text=_footer())
    await channel.send(content=mentions, embed=e)
    gid = str(msg.id)
    if gid in giveaways_data:
        del giveaways_data[gid]
        save_json("giveaways.json", giveaways_data)

@giveaway_group.command(name="terminar", description="⏹️ Terminar un giveaway manualmente")
@app_commands.describe(message_id="ID del mensaje del giveaway")
async def gv_terminar(interaction: discord.Interaction, message_id: str):
    try:
        gid = message_id
        if gid not in giveaways_data:
            return await interaction.response.send_message("❌ Giveaway no encontrado.", ephemeral=True)
        data = giveaways_data[gid]
        channel = interaction.guild.get_channel(data["channel"])
        if not channel:
            return await interaction.response.send_message("❌ Canal no encontrado.", ephemeral=True)
        msg = await channel.fetch_message(int(gid))
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot] if reaction else []
        if not users:
            await interaction.response.send_message("❌ No hay participantes.", ephemeral=True)
            return
        selected = random.sample(users, min(data["winners"], len(users)))
        mentions = " ".join(u.mention for u in selected)
        e = discord.Embed(title=f"{EMOJI_GOLDEN_SPIN_COIN} Giveaway Terminado", description=f"**Premio:** {data['prize']}\n🏆 **Ganador(es):** {mentions}", color=C_GREEN)
        e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
        e.set_footer(text=_footer())
        await interaction.response.send_message(content=mentions, embed=e)
        del giveaways_data[gid]
        save_json("giveaways.json", giveaways_data)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@giveaway_group.command(name="cancelar", description="❌ Cancelar un giveaway")
@app_commands.describe(message_id="ID del mensaje del giveaway")
async def gv_cancelar(interaction: discord.Interaction, message_id: str):
    if message_id not in giveaways_data:
        return await interaction.response.send_message("❌ Giveaway no encontrado.", ephemeral=True)
    del giveaways_data[message_id]
    save_json("giveaways.json", giveaways_data)
    await interaction.response.send_message(f"{EMOJI_FAILED} Giveaway cancelado.", ephemeral=True)

@giveaway_group.command(name="reroll", description="🔄 Elegir un nuevo ganador")
@app_commands.describe(message_id="ID del mensaje del giveaway")
async def gv_reroll(interaction: discord.Interaction, message_id: str):
    try:
        gid = message_id
        if gid not in giveaways_data:
            return await interaction.response.send_message("❌ Giveaway no encontrado.", ephemeral=True)
        data = giveaways_data[gid]
        channel = interaction.guild.get_channel(data["channel"])
        if not channel:
            return await interaction.response.send_message("❌ Canal no encontrado.", ephemeral=True)
        msg = await channel.fetch_message(int(gid))
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot] if reaction else []
        if not users:
            await interaction.response.send_message("❌ No hay participantes.", ephemeral=True)
            return
        winner = random.choice(users)
        e = discord.Embed(title=f"{EMOJI_DIAMOND} Nuevo Ganador", description=f"🏆 ¡{winner.mention} ganó el re-roll!", color=C_GREEN)
        e.set_footer(text=_footer())
        await interaction.response.send_message(content=winner.mention, embed=e)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@giveaway_group.command(name="lista", description="📋 Lista de giveaways activos")
async def gv_lista(interaction: discord.Interaction):
    if not giveaways_data:
        return await interaction.response.send_message("No hay giveaways activos.", ephemeral=True)
    e = discord.Embed(title=f"{EMOJI_GIVEAWAY} Giveaways Activos", color=C_GREEN)
    for gid, data in giveaways_data.items():
        end = datetime.fromisoformat(data["end"])
        e.add_field(name=f"**{data['prize']}**", value=f"ID: `{gid}`\nGanadores: {data['winners']}\nTermina: <t:{int(end.timestamp())}:R>", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

bot.tree.add_command(giveaway_group)

# ==============================================================
#  📌 INFORMACIÓN
# ==============================================================
@bot.tree.command(name="help", description="📖 Panel de ayuda del bot")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(title=f"{EMOJI_INFORMATION} Centro de Ayuda", description="Comandos disponibles. Usa `/comando` para ejecutar.", color=C_GREEN)
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.add_field(name="🎁 Giveaway", value="`/giveaway`", inline=True)
    e.add_field(name="📌 Información", value="`/help`, `/serverinfo`, `/userinfo`, `/avatar`, `/bot`, `/ping`", inline=False)
    e.add_field(name="🛡️ Moderación", value="`/ban`, `/kick`, `/mute`, `/warn`, `/unwarn`, `/clear`, `/lock`, `/unlock`", inline=False)
    e.add_field(name="😂 Diversión", value="`/meme`, `/joke`, `/say`, `/ship`, `/8ball`, `/gif`, `/random`", inline=False)
    e.add_field(name="🎫 Soporte", value="`/ticket`", inline=True)
    e.add_field(name="💰 Economía", value="`/balance`, `/daily`, `/work`, `/pay`, `/shop`, `/buy`, `/inventory`", inline=False)
    e.add_field(name="📈 Niveles", value="`/rank`, `/level`, `/leaderboard`, `/xp`, `/setlevel`", inline=False)
    e.add_field(name="🤖 Bot", value="`/bot`, `/invite`, `/uptime`, `/stats`, `/feedback`", inline=False)
    e.add_field(name="⚙️ Configuración", value="`/setup`, `/config`", inline=False)
    e.add_field(name="🧩 Roles", value="`/autorole`, `/rolecreate`, `/roleremove`, `/rolelist`, `/reactionrole`, `/temp-role`", inline=False)
    e.add_field(name="🏠 Servidor", value="`/server`, `/channels`, `/roles`, `/members`, `/boosts`, `/serverstats`", inline=False)
    e.add_field(name="🔍 Búsqueda", value="`/google`, `/youtube`, `/wikipedia`, `/translate`, `/weather`", inline=False)
    e.add_field(name="🗓️ Organización", value="`/reminder`", inline=False)
    e.set_footer(text=_footer())
    view = View()
    view.add_item(Button(label="Soporte", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=e, view=view)

@bot.tree.command(name="serverinfo", description="📋 Información del servidor")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    e = discord.Embed(title=f"{EMOJI_HOUSE} {g.name}", color=C_INFO)
    e.set_thumbnail(url=g.icon.url if g.icon else None)
    e.add_field(name=f"{EMOJI_OWNER} Dueño", value=g.owner.mention if g.owner else "Unknown", inline=True)
    e.add_field(name=f"{EMOJI_GREEN_MEMBER} Miembros", value=f"`{g.member_count}`", inline=True)
    e.add_field(name=f"{EMOJI_CART} Canales", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name=f"{EMOJI_ROLE} Roles", value=f"`{len(g.roles)}`", inline=True)
    e.add_field(name="📅 Creado", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="userinfo", description="👤 Información de usuario")
@app_commands.describe(usuario="Usuario a consultar (opcional)")
async def cmd_userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    e = discord.Embed(title=f"{EMOJI_MEMBER} {u.display_name}", color=u.top_role.color if u.top_role.color.value else C_INFO)
    e.set_thumbnail(url=u.display_avatar.url)
    e.add_field(name="ID", value=f"`{u.id}`", inline=True)
    e.add_field(name="Cuenta Creada", value=f"<t:{int(u.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="Se Unió", value=f"<t:{int(u.joined_at.timestamp())}:R>" if u.joined_at else "N/A", inline=True)
    e.add_field(name="Roles", value=" ".join([r.mention for r in u.roles if r.name != "@everyone"]) or "Ninguno", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="avatar", description="🖼️ Avatar de un usuario")
@app_commands.describe(usuario="Usuario (opcional)")
async def cmd_avatar(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    e = discord.Embed(title=f"Avatar de {u.display_name}", color=C_INFO)
    e.set_image(url=u.display_avatar.url)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="bot", description="🤖 Información del bot")
async def cmd_bot(interaction: discord.Interaction):
    e = discord.Embed(title="FMD BOT", description="Bot by KING.", color=C_GREEN)
    e.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="Uptime", value=_uptime(), inline=True)
    e.add_field(name="Latencia", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="ping", description="🏓 Latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# ==============================================================
#  🛡️ MODERACIÓN
# ==============================================================
@bot.tree.command(name="ban", description="🔨 Banear un usuario")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(usuario="Usuario a banear", razon="Razón del ban")
async def cmd_ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón"):
    await usuario.ban(reason=razon)
    await interaction.response.send_message(f"{EMOJI_RED_SIREN} **{usuario}** baneado. Razón: {razon}")

@bot.tree.command(name="kick", description="👢 Expulsar un usuario")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(usuario="Usuario a expulsar", razon="Razón")
async def cmd_kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón"):
    await usuario.kick(reason=razon)
    await interaction.response.send_message(f"{EMOJI_YELLOW_SIREN} **{usuario}** expulsado. Razón: {razon}")

@bot.tree.command(name="mute", description="🔇 Silenciar un usuario (Timeout)")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(usuario="Usuario a silenciar", minutos="Duración en minutos (1-40320)")
async def cmd_mute(interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10):
    await usuario.timeout(datetime.now(timezone.utc) + datetime.timedelta(minutes=minutos), reason="Mute aplicado")
    await interaction.response.send_message(f"🔇 {usuario.mention} silenciado por {minutos} min.")

@bot.tree.command(name="warn", description="⚠️ Advertir a un usuario")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(usuario="Usuario a advertir", razon="Razón")
async def cmd_warn(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón"):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    if gid not in warnings_data: warnings_data[gid] = {}
    if uid not in warnings_data[gid]: warnings_data[gid][uid] = []
    warnings_data[gid][uid].append({"mod": str(interaction.user.id), "reason": razon, "ts": int(time.time())})
    save_json("warnings.json", warnings_data)
    await interaction.response.send_message(f"{EMOJI_WARNING_ICON} {usuario.mention} ha sido advertido. Total: `{len(warnings_data[gid][uid])}`")

@bot.tree.command(name="unwarn", description="✅ Quitar una advertencia")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(usuario="Usuario", index="Número de advertencia a quitar (1-based)")
async def cmd_unwarn(interaction: discord.Interaction, usuario: discord.Member, index: int = 1):
    gid, uid = str(interaction.guild_id), str(usuario.id)
    warns = warnings_data.get(gid, {}).get(uid, [])
    if not warns or len(warns) < index:
        return await interaction.response.send_message("❌ No hay advertencia en ese índice.", ephemeral=True)
    warns.pop(index - 1)
    save_json("warnings.json", warnings_data)
    await interaction.response.send_message(f"{EMOJI_GREEN_SIREN} Advertencia #{index} removida de {usuario.mention}.")

@bot.tree.command(name="clear", description="🧹 Eliminar mensajes")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(cantidad="Número de mensajes a eliminar (1-100)")
async def cmd_clear(interaction: discord.Interaction, cantidad: int = 10):
    await interaction.channel.purge(limit=cantidad)
    await interaction.response.send_message(f"{EMOJI_EMOJIGG_MOD} `{cantidad}` mensajes eliminados.", ephemeral=True)

@bot.tree.command(name="lock", description="🔒 Cerrar el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(f"{EMOJI_ADMIN} {interaction.channel.mention} bloqueado.")

@bot.tree.command(name="unlock", description="🔓 Abrir el canal")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
    await interaction.response.send_message(f"{EMOJI_GREEN_SIREN} {interaction.channel.mention} desbloqueado.")

# ==============================================================
#  😂 DIVERSIÓN
# ==============================================================
@bot.tree.command(name="meme", description="😂 Meme aleatorio de Reddit")
async def cmd_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        r = requests.get("https://meme-api.com/gimme").json()
        e = discord.Embed(title=r["title"], color=C_WARN)
        e.set_image(url=r["url"])
        e.set_footer(text=f"r/{r['subreddit']}")
        await interaction.followup.send(embed=e)
    except:
        await interaction.followup.send("❌ No se pudo obtener meme.")

@bot.tree.command(name="joke", description="😄 Chiste aleatorio")
async def cmd_joke(interaction: discord.Interaction):
    r = requests.get("https://v2.jokeapi.dev/joke/Any?lang=es").json()
    if r["type"] == "single": txt = r["joke"]
    else: txt = f"{r['setup']}\n\n{r['delivery']}"
    await interaction.response.send_message(f"**😄 Chiste:**\n{txt}")

@bot.tree.command(name="say", description="📢 Repite un mensaje")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(mensaje="Mensaje a repetir")
async def cmd_say(interaction: discord.Interaction, mensaje: str):
    await interaction.response.send_message("✅ Enviado.", ephemeral=True)
    await interaction.channel.send(mensaje)

@bot.tree.command(name="ship", description="❤️ Calcula el amor entre dos personas")
@app_commands.describe(user1="Primera persona", user2="Segunda persona")
async def cmd_ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    love = random.randint(0, 100)
    heart = "❤️" if love > 80 else "💔"
    await interaction.response.send_message(f"{EMOJI_LOVE_MAIL} **{user1.display_name}** y **{user2.display_name}**\nCompatibilidad: **{love}%** {heart}")

@bot.tree.command(name="8ball", description="🎱 Pregunta a la bola mágica")
@app_commands.describe(pregunta="Tu pregunta")
async def cmd_8ball(interaction: discord.Interaction, pregunta: str):
    resp = random.choice(["Sí.", "No.", "Pregunta de nuevo.", "Definitivamente sí.", "No cuentes con ello."])
    await interaction.response.send_message(f"🎱 **Pregunta:** {pregunta}\n**Respuesta:** {resp}")

@bot.tree.command(name="gif", description="🎥 Busca un GIF en Tenor")
@app_commands.describe(busqueda="Término de búsqueda")
async def cmd_gif(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    tenor_key = "AIzaSyC2-7bLmQ0lB7p3mO_qB3X0D5TdYbKjU8s"
    try:
        r = requests.get(f"https://tenor.googleapis.com/v2/search?q={quote(busqueda)}&key={tenor_key}&limit=1&media_filter=gif", timeout=10).json()
        if not r.get("results"):
            return await interaction.followup.send("❌ No se encontraron GIFs.")
        gif_url = r["results"][0]["media_formats"]["gif"]["url"]
        e = discord.Embed(title=f"{EMOJI_GREEN_DOT} Resultado de búsqueda", color=C_GREEN)
        e.set_image(url=gif_url)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("❌ Error al obtener el GIF.")

@bot.tree.command(name="random", description="🎲 Número aleatorio")
@app_commands.describe(min="Mínimo", max="Máximo")
async def cmd_random(interaction: discord.Interaction, min: int = 1, max: int = 100):
    await interaction.response.send_message(f"🎲 Número: **{random.randint(min, max)}**")

# ==============================================================
#  🎫 SOPORTE (TICKETS)
# ==============================================================
ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets")

@ticket_group.command(name="crear", description="🎫 Crear un nuevo ticket")
async def tk_crear(interaction: discord.Interaction):
    guild = interaction.guild
    name = f"ticket-{interaction.user.name}".lower()
    if discord.utils.get(guild.channels, name=name):
        return await interaction.response.send_message("❌ Ya tienes un ticket abierto.", ephemeral=True)
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True), guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
    ch = await guild.create_text_channel(name, overwrites=overwrites)
    await interaction.response.send_message(f"{EMOJI_TICKET} Ticket creado: {ch.mention}", ephemeral=True)
    await ch.send(f"{interaction.user.mention} Describe tu problema.")

@ticket_group.command(name="cerrar", description="🔒 Cerrar el ticket actual")
async def tk_cerrar(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message("❌ Este no es un ticket.", ephemeral=True)
    await interaction.response.send_message("🔒 Cerrando ticket en 5 segundos...")
    await asyncio.sleep(5)
    await interaction.channel.delete()

@ticket_group.command(name="añadir", description="➕ Añadir usuario al ticket")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(usuario="Usuario a añadir")
async def tk_add(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.channel.set_permissions(usuario, view_channel=True, send_messages=True)
    await interaction.response.send_message(f"✅ {usuario.mention} añadido al ticket.")

@ticket_group.command(name="quitar", description="➖ Quitar usuario del ticket")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(usuario="Usuario a quitar")
async def tk_remove(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.channel.set_permissions(usuario, overwrite=None)
    await interaction.response.send_message(f"✅ {usuario.mention} removido del ticket.")

@ticket_group.command(name="panel", description="🖥️ Enviar panel de tickets")
@app_commands.checks.has_permissions(administrator=True)
async def tk_panel(interaction: discord.Interaction):
    e = discord.Embed(title=f"{EMOJI_TICKET} Panel de Tickets", description="Presiona el botón para abrir un ticket.", color=C_GREEN)
    e.set_thumbnail(url="https://cdn.discordapp.com/emojis/1526742765311098980.gif")
    e.set_footer(text=_footer())
    view = View()
    view.add_item(Button(label="Abrir Ticket", style=discord.ButtonStyle.success, custom_id="ticket_btn"))
    await interaction.response.send_message(embed=e, view=view)

bot.tree.add_command(ticket_group)

# ==============================================================
#  💰 ECONOMÍA
# ==============================================================
def _eco_get(uid):
    uid = str(uid)
    if uid not in economy_data: economy_data[uid] = {"bal": 100, "daily": 0, "inv": []}
    return economy_data[uid]

@bot.tree.command(name="balance", description="💰 Ver tu saldo")
async def cmd_balance(interaction: discord.Interaction):
    data = _eco_get(interaction.user.id)
    await interaction.response.send_message(f"{EMOJI_MONEY} **{interaction.user.display_name}**\nSaldo: `{data['bal']}` monedas.")

@bot.tree.command(name="daily", description="🎁 Recompensa diaria")
async def cmd_daily(interaction: discord.Interaction):
    data = _eco_get(interaction.user.id)
    now = int(time.time())
    if now - data["daily"] < 86400:
        return await interaction.response.send_message("⏳ Ya reclamaste tu daily. Espera 24h.", ephemeral=True)
    data["bal"] += 100
    data["daily"] = now
    save_json("economy.json", economy_data)
    await interaction.response.send_message(f"{EMOJI_GIFT} Has reclamado `100` monedas. Nuevo saldo: `{data['bal']}`")

@bot.tree.command(name="work", description="💼 Trabajar y ganar monedas")
async def cmd_work(interaction: discord.Interaction):
    data = _eco_get(interaction.user.id)
    earned = random.randint(20, 50)
    data["bal"] += earned
    save_json("economy.json", economy_data)
    await interaction.response.send_message(f"{EMOJI_BITCASH} Has trabajado y ganado `{earned}` monedas.")

@bot.tree.command(name="pay", description="💸 Pagar a otro usuario")
@app_commands.describe(usuario="Usuario a pagar", cantidad="Cantidad de monedas")
async def cmd_pay(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
    d1 = _eco_get(interaction.user.id)
    d2 = _eco_get(usuario.id)
    if d1["bal"] < cantidad:
        return await interaction.response.send_message("❌ No tienes suficiente saldo.", ephemeral=True)
    d1["bal"] -= cantidad
    d2["bal"] += cantidad
    save_json("economy.json", economy_data)
    await interaction.response.send_message(f"💸 Has pagado `{cantidad}` monedas a {usuario.mention}.")

@bot.tree.command(name="shop", description="🛒 Ver la tienda")
async def cmd_shop(interaction: discord.Interaction):
    gid = str(interaction.guild_id)
    items = load_json(f"shop_{gid}.json", {})
    if not items: return await interaction.response.send_message("🛒 La tienda está vacía.")
    e = discord.Embed(title=f"{EMOJI_CART} Tienda del Servidor", color=C_GREEN)
    for name, price in items.items():
        e.add_field(name=name, value=f"`{price}` monedas", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="buy", description="🛍️ Comprar un artículo de la tienda")
@app_commands.describe(articulo="Nombre del artículo")
async def cmd_buy(interaction: discord.Interaction, articulo: str):
    gid = str(interaction.guild_id)
    items = load_json(f"shop_{gid}.json", {})
    if articulo not in items:
        return await interaction.response.send_message("❌ Ese artículo no existe en la tienda.", ephemeral=True)
    data = _eco_get(interaction.user.id)
    price = items[articulo]
    if data["bal"] < price:
        return await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
    data["bal"] -= price
    data["inv"].append(articulo)
    save_json("economy.json", economy_data)
    await interaction.response.send_message(f"✅ Compraste **{articulo}** por `{price}` monedas.")

@bot.tree.command(name="inventory", description="🎒 Ver tu inventario")
async def cmd_inventory(interaction: discord.Interaction):
    data = _eco_get(interaction.user.id)
    inv = data.get("inv", [])
    desc = ", ".join(inv) if inv else "Vacío"
    await interaction.response.send_message(f"🎒 **Inventario:** {desc}")

# ==============================================================
#  📈 NIVELES
# ==============================================================
def _lvl_get(uid):
    uid = str(uid)
    if uid not in levels_data: levels_data[uid] = {"xp": 0, "level": 1}
    return levels_data[uid]

@bot.tree.command(name="rank", description="📊 Ver tu nivel")
@app_commands.describe(usuario="Usuario (opcional)")
async def cmd_rank(interaction: discord.Interaction, usuario: discord.Member = None):
    u = usuario or interaction.user
    d = _lvl_get(u.id)
    e = discord.Embed(title=f"📊 Nivel de {u.display_name}", color=C_GREEN)
    e.set_thumbnail(url=u.display_avatar.url)
    e.add_field(name="Nivel", value=f"`{d['level']}`", inline=True)
    e.add_field(name="XP", value=f"`{d['xp']}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="level", description="📈 Ver tu nivel y XP")
async def cmd_level(interaction: discord.Interaction):
    await cmd_rank(interaction)

@bot.tree.command(name="leaderboard", description="🏆 Ranking de niveles")
async def cmd_leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(levels_data.items(), key=lambda x: x[1]['level'], reverse=True)[:10]
    if not sorted_users:
        return await interaction.response.send_message("No hay datos de niveles.", ephemeral=True)
    e = discord.Embed(title=f"{EMOJI_DIAMOND} Leaderboard", color=C_GREEN)
    for i, (uid, data) in enumerate(sorted_users, 1):
        user = bot.get_user(int(uid))
        name = user.name if user else f"Usuario {uid}"
        e.add_field(name=f"#{i} {name}", value=f"Nivel: `{data['level']}` | XP: `{data['xp']}`", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="xp", description="Ver tu XP")
async def cmd_xp(interaction: discord.Interaction):
    data = _lvl_get(interaction.user.id)
    await interaction.response.send_message(f"📊 Tu XP: `{data['xp']}`")

@bot.tree.command(name="setlevel", description="⚡ [Admin] Cambiar nivel de un usuario")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(usuario="Usuario", nivel="Nuevo nivel")
async def cmd_setlevel(interaction: discord.Interaction, usuario: discord.Member, nivel: int):
    d = _lvl_get(usuario.id)
    d["level"] = nivel
    save_json("levels.json", levels_data)
    await interaction.response.send_message(f"✅ Nivel de {usuario.display_name} cambiado a `{nivel}`.")

# ==============================================================
#  🤖 BOT
# ==============================================================
@bot.tree.command(name="invite", description="📩 Invitar al bot")
async def cmd_invite(interaction: discord.Interaction):
    await interaction.response.send_message(f"🤖 **Invíta al bot:**\nhttps://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot+applications.commands")

@bot.tree.command(name="uptime", description="⏱️ Tiempo activo")
async def cmd_uptime(interaction: discord.Interaction):
    await interaction.response.send_message(f"⏱️ Bot activo por: **{_uptime()}**")

@bot.tree.command(name="stats", description="📊 Estadísticas del bot")
async def cmd_stats(interaction: discord.Interaction):
    e = discord.Embed(title="📊 Estadísticas", color=C_GREEN)
    e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.add_field(name="Usuarios", value=f"`{sum(g.member_count for g in bot.guilds)}`", inline=True)
    e.add_field(name="Latencia", value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="Uptime", value=_uptime(), inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="feedback", description="📝 Enviar feedback al creador")
@app_commands.describe(mensaje="Tu mensaje")
async def cmd_feedback(interaction: discord.Interaction, mensaje: str):
    await interaction.response.send_message("✅ Feedback enviado. ¡Gracias!", ephemeral=True)

# ==============================================================
#  ⚙️ CONFIGURACIÓN
# ==============================================================
@bot.tree.command(name="setup", description="⚙️ [Admin] Panel de configuración rápida")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setup(interaction: discord.Interaction):
    e = discord.Embed(title=f"{EMOJI_SETTINGS} Configuración", description="Usa `/config` para ajustes específicos.", color=C_GREEN)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="config", description="⚙️ [Admin] Configurar opciones del servidor")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(tipo="Tipo de configuración", canal="Canal (para bienvenida/logs)", rol="Rol (para autorol)")
async def cmd_config(interaction: discord.Interaction, tipo: str, canal: discord.TextChannel = None, rol: discord.Role = None):
    gid = str(interaction.guild_id)
    if gid not in config_data: config_data[gid] = {}
    if tipo == "bienvenida" and canal:
        config_data[gid]["welcome"] = canal.id
        await interaction.response.send_message(f"✅ Canal de bienvenida configurado: {canal.mention}", ephemeral=True)
    elif tipo == "logs" and canal:
        config_data[gid]["logs"] = canal.id
        await interaction.response.send_message(f"✅ Canal de logs configurado: {canal.mention}", ephemeral=True)
    elif tipo == "autorol" and rol:
        config_data[gid]["autorol"] = rol.id
        await interaction.response.send_message(f"✅ Auto-rol configurado: {rol.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Uso: `/config [bienvenida|logs|autorol] [canal/rol]`", ephemeral=True)
        return
    save_json("configs.json", config_data)

# ==============================================================
#  🧩 ROLES
# ==============================================================
@bot.tree.command(name="autorole", description="🎭 [Admin] Configurar rol automático al unirse")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(rol="Rol a asignar")
async def cmd_autorole(interaction: discord.Interaction, rol: discord.Role):
    gid = str(interaction.guild_id)
    if gid not in config_data: config_data[gid] = {}
    config_data[gid]["autorol"] = rol.id
    save_json("configs.json", config_data)
    await interaction.response.send_message(f"✅ Auto-rol configurado: {rol.mention}", ephemeral=True)

@bot.tree.command(name="rolecreate", description="✨ [Admin] Crear un nuevo rol")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(nombre="Nombre del rol", color="Color en hex (ej: #FF0000)")
async def cmd_rolecreate(interaction: discord.Interaction, nombre: str, color: str = "#FFFFFF"):
    try: c = discord.Color(int(color.strip("#"), 16))
    except: c = discord.Color.default()
    role = await interaction.guild.create_role(name=nombre, color=c)
    await interaction.response.send_message(f"✅ Rol `{role.name}` creado.")

@bot.tree.command(name="roleremove", description="❌ [Admin] Eliminar un rol")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(rol="Rol a eliminar")
async def cmd_roleremove(interaction: discord.Interaction, rol: discord.Role):
    await rol.delete()
    await interaction.response.send_message(f"✅ Rol `{rol.name}` eliminado.")

@bot.tree.command(name="rolelist", description="📋 Lista de roles del servidor")
async def cmd_rolelist(interaction: discord.Interaction):
    roles = interaction.guild.roles[1:]
    if not roles: return await interaction.response.send_message("No hay roles.", ephemeral=True)
    e = discord.Embed(title=f"{EMOJI_ROLE} Roles de {interaction.guild.name}", color=C_GREEN)
    for r in roles:
        e.add_field(name=r.name, value=f"ID: `{r.id}` | Miembros: {len(r.members)}", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="reactionrole", description="🎭 [Admin] Crear un mensaje de reaction roles")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(rol="Rol a asignar", emoji="Emoji para la reacción")
async def cmd_reactionrole(interaction: discord.Interaction, rol: discord.Role, emoji: str):
    e = discord.Embed(title="🎭 Reaction Role", description=f"Reacciona con {emoji} para obtener el rol {rol.mention}", color=C_GREEN)
    e.set_footer(text=_footer())
    msg = await interaction.channel.send(embed=e)
    await msg.add_reaction(emoji)
    await interaction.response.send_message("✅ Mensaje de reaction roles creado.", ephemeral=True)

@bot.tree.command(name="temp-role", description="⏳ [Admin] Asignar un rol temporal")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(usuario="Usuario", rol="Rol", minutos="Duración en minutos")
async def cmd_temp_role(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role, minutos: int):
    await usuario.add_roles(rol)
    await interaction.response.send_message(f"✅ Rol {rol.mention} asignado a {usuario.mention} por {minutos} min.", ephemeral=True)
    await asyncio.sleep(minutos * 60)
    if rol in usuario.roles:
        await usuario.remove_roles(rol)
        await interaction.followup.send(f"⏰ Rol {rol.mention} removido de {usuario.mention}.", ephemeral=True)

# ==============================================================
#  🏠 SERVIDOR
# ==============================================================
@bot.tree.command(name="server", description="🏠 Información del servidor")
async def cmd_server(interaction: discord.Interaction):
    await cmd_serverinfo(interaction)

@bot.tree.command(name="channels", description="📁 Lista de canales del servidor")
async def cmd_channels(interaction: discord.Interaction):
    e = discord.Embed(title=f"{EMOJI_CART} Canales de {interaction.guild.name}", color=C_GREEN)
    for ch in interaction.guild.text_channels[:20]:
        e.add_field(name=ch.name, value=f"ID: `{ch.id}`", inline=False)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="roles", description="🎭 Lista de roles")
async def cmd_roles(interaction: discord.Interaction):
    await cmd_rolelist(interaction)

@bot.tree.command(name="members", description="👥 Número de miembros")
async def cmd_members(interaction: discord.Interaction):
    await interaction.response.send_message(f"👥 **{interaction.guild.name}** tiene `{interaction.guild.member_count}` miembros.")

@bot.tree.command(name="boosts", description="🚀 Información de boosts")
async def cmd_boosts(interaction: discord.Interaction):
    g = interaction.guild
    e = discord.Embed(title=f"🚀 Boosts de {g.name}", color=C_GREEN)
    e.add_field(name="Nivel", value=f"`{g.premium_tier}`", inline=True)
    e.add_field(name="Número de Boosts", value=f"`{g.premium_subscription_count}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="serverstats", description="📊 Estadísticas del servidor")
async def cmd_serverstats(interaction: discord.Interaction):
    g = interaction.guild
    e = discord.Embed(title=f"{EMOJI_HOUSE} Estadísticas de {g.name}", color=C_GREEN)
    e.add_field(name="Miembros", value=f"`{g.member_count}`", inline=True)
    e.add_field(name="Canales", value=f"`{len(g.channels)}`", inline=True)
    e.add_field(name="Roles", value=f"`{len(g.roles)}`", inline=True)
    e.add_field(name="Boosts", value=f"`{g.premium_subscription_count}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)

# ==============================================================
#  🔍 BÚSQUEDA
# ==============================================================
@bot.tree.command(name="google", description="🔍 Buscar en Google (simulado)")
@app_commands.describe(query="Término de búsqueda")
async def cmd_google(interaction: discord.Interaction, query: str):
    url = f"https://www.google.com/search?q={quote(query)}"
    await interaction.response.send_message(f"{EMOJI_SEARCH1} Resultado de búsqueda: {url}")

@bot.tree.command(name="youtube", description="🎥 Buscar en YouTube")
@app_commands.describe(query="Término de búsqueda")
async def cmd_youtube(interaction: discord.Interaction, query: str):
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    await interaction.response.send_message(f"{EMOJI_SEARCH2} Resultado de YouTube: {url}")

@bot.tree.command(name="wikipedia", description="📚 Buscar en Wikipedia (resumen)")
@app_commands.describe(query="Término de búsqueda")
async def cmd_wikipedia(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        url = f"https://es.wikipedia.org/wiki/{quote(query.replace(' ', '_'))}"
        await interaction.followup.send(f"{EMOJI_INFORMATION} Artículo de Wikipedia: {url}")
    except:
        await interaction.followup.send("❌ No se pudo obtener el artículo.")

@bot.tree.command(name="translate", description="🌐 Traducir texto a español")
@app_commands.describe(texto="Texto a traducir")
async def cmd_translate(interaction: discord.Interaction, texto: str):
    await interaction.response.defer()
    try:
        from googletrans import Translator
        t = Translator()
        translated = t.translate(texto, dest='es').text
        await interaction.followup.send(f"🌐 **Traducción:**\n{translated}")
    except:
        await interaction.followup.send("❌ Error en la traducción.")

@bot.tree.command(name="weather", description="🌤️ Clima de una ciudad")
@app_commands.describe(ciudad="Nombre de la ciudad")
async def cmd_weather(interaction: discord.Interaction, ciudad: str):
    await interaction.response.defer()
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(ciudad)}&appid=YOUR_API_KEY&units=metric&lang=es"
        resp = requests.get(url)
        if resp.status_code != 200:
            await interaction.followup.send("❌ No se pudo obtener el clima.")
            return
        data = resp.json()
        desc = data['weather'][0]['description']
        temp = data['main']['temp']
        e = discord.Embed(title=f"🌤️ Clima en {ciudad}", description=f"**{desc}**\nTemperatura: `{temp}°C`", color=C_GREEN)
        e.set_footer(text=_footer())
        await interaction.followup.send(embed=e)
    except:
        await interaction.followup.send("❌ Error al consultar el clima.")

# ==============================================================
#  🗓️ ORGANIZACIÓN
# ==============================================================
@bot.tree.command(name="reminder", description="⏰ Crear un recordatorio")
@app_commands.describe(minutos="Minutos", mensaje="Mensaje del recordatorio")
async def cmd_reminder(interaction: discord.Interaction, minutos: int, mensaje: str):
    await interaction.response.send_message(f"{EMOJI_ALARM} Recordatorio en {minutos} min: `{mensaje}`", ephemeral=True)
    await asyncio.sleep(minutos * 60)
    await interaction.followup.send(f"{EMOJI_ALARM} **Recordatorio para {interaction.user.mention}:** {mensaje}")

# ── HEALTH SERVER ──────────────────────────────────────────────
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
    logger.info(f"🌐 Servidor de salud en puerto :{PORT}")

# ── MAIN ──────────────────────────────────────────────────────
async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado.")
        return
    start_web()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
