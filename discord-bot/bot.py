"""
FMD BOT — Executor Tracker · Bypass Engine · Groq IA
Render Web Service compatible (binds PORT for health check).
"""
import os, re, json, time, asyncio, logging
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ui import Button, View
from discord.ext import tasks
import aiohttp, requests

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

# ──────────────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("FMD")
logger.setLevel(logging.INFO)
for h in (RotatingFileHandler("bot.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
          logging.StreamHandler()):
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(h)

# ──────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN  = os.environ.get("DISCORD_TOKEN", "")
OWNER_ID       = int(os.environ.get("OWNER_ID", "0"))
PORT           = int(os.environ.get("PORT", "8080"))
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL     = "llama3-8b-8192"

BOT_NAME           = "FMD BOT"
BOT_CREDIT         = "BY KING"
SUPPORT_SERVER_URL = os.environ.get("SUPPORT_SERVER_URL", "https://discord.gg/nU9MNnByHH")
BOT_INVITE_URL     = os.environ.get("BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1525040833814855710")

# Bypass
BYPASS_API_URL  = "https://4pi-bypass.vercel.app/api/bypass?url="
BYPASS_TIMEOUT  = 30
BYPASS_RETRIES  = 3
BYPASS_DELAY    = 3

# WEAO
WEAO_API        = "https://api.weao.xyz/v1/exploits"
CHECK_INTERVAL  = 90

# Files
CONFIG_FILE      = "config.json"
STATE_FILE       = "estado_anterior.json"
AUTOBYPASS_FILE  = "autobypass_channels.json"
IA_CHANNELS_FILE = "ia_channels.json"

# Colors
C_MAIN    = 0xB026FF   # FMD purple
C_BYPASS  = 0x00D9FF   # cyan
C_SUCCESS = 0x57F287
C_ERROR   = 0xED4245
C_WARN    = 0xFEE75C
C_INFO    = 0x5865F2
C_GOLD    = 0xFFD700

# Images / GIFs
BANNER_BOT    = "https://i.imgur.com/5v0FMCO.gif"   # animated purple banner
BANNER_BYPASS = "https://media.tenor.com/OsJIz5IHkLkAAAAC/hacker-matrix.gif"
BANNER_EXEC   = "https://media.tenor.com/dqclPMLU8BAAAAAC/roblox.gif"
BANNER_AI     = "https://media.tenor.com/fP1OFjH1DlsAAAAC/ai-artificial-intelligence.gif"
GIF_LOADING   = "https://media.tenor.com/wpSo-8CrXqUAAAAi/loading-loading-forever.gif"
GIF_ERROR     = "https://media.tenor.com/0LF_JKlnPsgAAAAi/error-warning.gif"
DOT_GREEN     = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
DOT_RED       = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"

EMOJI_SUCCESS = "<:greendot:1525383175889485848>"
EMOJI_KEY     = "<:goldenkey:1525381310200414310>"
EMOJI_CLOCK   = "<a:clock:1525380296852377711>"
EMOJI_COPY    = "<:copy:1525379105111932958>"
EMOJI_LINK    = "<:link:1525379856034959422>"

DEFAULT_EXPLOITS = [
    "Solara","Wave","AWP","Vega X","Delta","Hydrogen","Fluxus",
    "Electron","Nihon","Celestial","Velocity","Oxygen U","Comet",
    "Zypher","Krnl","Synapse X","Script-Ware","Evon","JJSploit",
    "Coco","Zen","Borealis","Sirius","Xeno","Rise","Valyse",
    "Elysian","Novus","Vynixius","Seliware","Exoliner","Neo",
    "Trigon","Eclipse","Arceus X","Aurora","Nexus","Carbon",
]

BOT_START = datetime.now(timezone.utc)

# ──────────────────────────────────────────────────────────────────
#  JSON HELPERS
# ──────────────────────────────────────────────────────────────────

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
        logger.warning(f"save_json({path}): {e}")

autobypass_channels: set = set(load_json(AUTOBYPASS_FILE, []))
ia_channels:         set = set(load_json(IA_CHANNELS_FILE, []))

def _save_ab(): save_json(AUTOBYPASS_FILE, list(autobypass_channels))
def _save_ia(): save_json(IA_CHANNELS_FILE, list(ia_channels))

# ──────────────────────────────────────────────────────────────────
#  MISC HELPERS
# ──────────────────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://[^\s<>\"']{6,}")

def _is_url(u: str) -> bool:
    return bool(re.match(r"^https?://\S{6,}", u))

def _footer(extra: str = "") -> str:
    b = f"╔═ {BOT_NAME} ═╗ {BOT_CREDIT}"
    return f"{b}  •  {extra}" if extra else b

def _uptime() -> str:
    d = datetime.now(timezone.utc) - BOT_START
    t = int(d.total_seconds())
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

def _status_emoji(s: str) -> str:
    s = (s or "").lower()
    if s == "online":  return "🟢"
    if s == "patched": return "🔴"
    return "🟡"

def _bypass_emoji(v) -> str:
    return "✅" if v else "❌"

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

# ──────────────────────────────────────────────────────────────────
#  BYPASS ENGINE  (4PI API)
# ──────────────────────────────────────────────────────────────────
_RESULT_KEYS = (
    "content","result","loadstring","bypassed","bypassed_link",
    "bypassed_url","final_url","destination","url","link","key","output"
)
_http = requests.Session()
_http.headers.update({"User-Agent": "FMD-Bot/1.0"})

def _extract(data):
    if isinstance(data, dict):
        for k in _RESULT_KEYS:
            if k in data:
                v = data[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    r = _extract(v)
                    if r: return r
        for v in data.values():
            if isinstance(v, (dict, list)):
                r = _extract(v)
                if r: return r
    elif isinstance(data, list):
        for item in data:
            r = _extract(item)
            if r: return r
    return None

def _bypass_sync(url: str):
    last_err = "Error desconocido"
    for attempt in range(1, BYPASS_RETRIES + 1):
        try:
            full = BYPASS_API_URL + quote(url, safe="")
            resp = _http.get(full, timeout=BYPASS_TIMEOUT)
            if resp.status_code in (502, 503, 504):
                last_err = f"API sobrecargada (HTTP {resp.status_code})"
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            try:
                data = resp.json()
            except Exception:
                txt = resp.text.strip()
                if txt.startswith("http"): return txt, None
                last_err = "Respuesta inválida"
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            api_err = False
            if isinstance(data, dict):
                if (data.get("success") is False or data.get("error")
                        or str(data.get("status","")).lower() == "error"):
                    api_err = True
            result = _extract(data)
            if result and not api_err: return result, None
            if api_err:
                msg = None
                if isinstance(data, dict): msg = data.get("message") or data.get("error")
                last_err = str(msg or "API reportó un error")
                if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY); continue
                return None, last_err
            return None, "Sin resultado en la respuesta"
        except requests.exceptions.Timeout:
            last_err = f"Timeout ({BYPASS_TIMEOUT}s)"
            if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY)
        except requests.exceptions.ConnectionError as ex:
            last_err = f"Conexión fallida: {str(ex)[:80]}"
            if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY)
        except Exception as ex:
            last_err = str(ex)[:120]
            if attempt < BYPASS_RETRIES: time.sleep(BYPASS_DELAY)
    return None, last_err

# ──────────────────────────────────────────────────────────────────
#  BYPASS EMBEDS & VIEWS
# ──────────────────────────────────────────────────────────────────

def _build_bypass_success(result: str, elapsed: float, url: str) -> discord.Embed:
    embed = discord.Embed(color=C_BYPASS, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"╔═ {BOT_NAME} • BYPASS ENGINE ═╗", icon_url=DOT_GREEN)
    embed.description = (
        f"```ansi\n\u001b[0;32m✔  BYPASS EXITOSO\u001b[0m\n```"
    )
    # URL original (truncada)
    embed.add_field(
        name="🔗  URL Original",
        value=f"```\n{url[:180]}\n```",
        inline=False
    )
    # Resultado (lo que el usuario quiere copiar)
    embed.add_field(
        name=f"{EMOJI_KEY}  RESURTADO",
        value=f"```txt\n{result[:900]}\n```",
        inline=False
    )
    embed.add_field(name=f"{EMOJI_CLOCK}  Velocidad", value=f"`{elapsed:.2f}s`", inline=True)
    embed.add_field(name="⚡  Motor",     value="`4PI API`",                     inline=True)
    embed.add_field(name="📅  Fecha",     value=f"`{_ts()}`",                    inline=True)
    embed.set_image(url=BANNER_BYPASS)
    embed.set_footer(text=_footer())
    return embed

def _build_bypass_error(error: str, url: str, elapsed: float) -> discord.Embed:
    embed = discord.Embed(color=C_ERROR, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"╔═ {BOT_NAME} • BYPASS FALLIDO ═╗", icon_url=DOT_RED)
    embed.description = "```ansi\n\u001b[0;31m✘  No se pudo bypasear el enlace\u001b[0m\n```"
    embed.add_field(name="🔗  URL",      value=f"```\n{url[:200]}\n```",         inline=False)
    embed.add_field(name="❌  Error",    value=f"```\n{error or '?'}\n```",       inline=False)
    embed.add_field(name="⏱️  Tiempo",   value=f"`{int(elapsed*1000)}ms`",       inline=True)
    embed.set_thumbnail(url=GIF_ERROR)
    embed.set_footer(text=_footer())
    return embed

class BypassView(View):
    def __init__(self, result: str):
        super().__init__(timeout=None)
        self._r = result
        self.add_item(Button(label="Invitar Bot",  emoji="🤖",  url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, row=0))
        self.add_item(Button(label="Soporte",      emoji="💬",  url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, row=0))

    @discord.ui.button(label="📋  Copiar RESURTADO", style=discord.ButtonStyle.success, row=1)
    async def copy_btn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            content=f"```txt\n{self._r[:1800]}\n```",
            ephemeral=True
        )

class ErrorBypassView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Soporte", emoji="💬", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link))

# ──────────────────────────────────────────────────────────────────
#  GROQ AI
# ──────────────────────────────────────────────────────────────────
_groq = AsyncGroq(api_key=GROQ_API_KEY) if (AsyncGroq and GROQ_API_KEY) else None

async def ask_groq(prompt: str, system: str = f"Eres {BOT_NAME}, un asistente de Discord amigable. Responde siempre en español de forma clara y concisa.") -> str:
    if not _groq:
        return "❌ **GROQ_API_KEY** no configurada. Agrégala en variables de entorno."
    try:
        resp = await _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt[:4000]}],
            max_tokens=800, temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as ex:
        logger.error(f"[Groq] {ex}")
        return f"❌ Error Groq: `{str(ex)[:200]}`"

# ──────────────────────────────────────────────────────────────────
#  WEAO  (executor data)
# ──────────────────────────────────────────────────────────────────

async def fetch_exploits() -> dict:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(WEAO_API, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    raw = await r.json(content_type=None)
                    lst = raw if isinstance(raw, list) else raw.get("exploits", raw.get("data",[]))
                    return {item.get("name","").lower(): item for item in lst if item.get("name")}
    except Exception as ex:
        logger.warning(f"[WEAO] {ex}")
    return {}

def get_exploit(data: dict, name: str):
    return data.get(name.lower())

# ──────────────────────────────────────────────────────────────────
#  BOT CLIENT
# ──────────────────────────────────────────────────────────────────

class FMDBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("✅ Slash commands sincronizados")

    async def on_ready(self):
        logger.info(f"✅ {BOT_NAME} online como {self.user} | {len(self.guilds)} servidor(es)")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"/help • {BOT_NAME}"))
        if not exploit_check.is_running():
            exploit_check.start()

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.channel.id in autobypass_channels:
            urls = _URL_RE.findall(message.content)
            if urls:
                asyncio.create_task(_auto_bypass(message, urls)); return
        if message.channel.id in ia_channels and message.content.strip():
            asyncio.create_task(_auto_ia(message))

bot = FMDBot()

# ──────────────────────────────────────────────────────────────────
#  AUTO-BYPASS
# ──────────────────────────────────────────────────────────────────

async def _auto_bypass(message: discord.Message, urls: list):
    try: await message.delete()
    except Exception: pass
    loop = asyncio.get_running_loop()
    for url in urls[:3]:
        if not _is_url(url): continue
        loading = discord.Embed(
            title=f"⏳  {BOT_NAME} • Procesando Bypass...",
            description="```fix\nConectando con el motor de bypass...\nEspera unos segundos.\n```",
            color=C_WARN, timestamp=datetime.now(timezone.utc))
        loading.set_thumbnail(url=GIF_LOADING)
        loading.set_footer(text=_footer())
        msg = None
        try: msg = await message.channel.send(content=message.author.mention, embed=loading)
        except Exception: continue
        t0 = time.time()
        result, error = await loop.run_in_executor(None, _bypass_sync, url)
        elapsed = time.time() - t0
        try:
            if result:
                await msg.edit(content=message.author.mention,
                               embed=_build_bypass_success(result, elapsed, url),
                               view=BypassView(result))
            else:
                await msg.edit(content=message.author.mention,
                               embed=_build_bypass_error(error, url, elapsed),
                               view=ErrorBypassView())
        except Exception: pass

# ──────────────────────────────────────────────────────────────────
#  AUTO-IA
# ──────────────────────────────────────────────────────────────────

async def _auto_ia(message: discord.Message):
    async with message.channel.typing():
        reply = await ask_groq(message.content)
    e = discord.Embed(description=reply[:2000], color=C_MAIN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} • IA", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.set_footer(text=_footer("Groq • llama3-8b"))
    try: await message.reply(embed=e, mention_author=False)
    except Exception as ex: logger.error(f"[auto_ia] {ex}")

# ──────────────────────────────────────────────────────────────────
#  EXPLOIT CHECK TASK
# ──────────────────────────────────────────────────────────────────

@tasks.loop(seconds=CHECK_INTERVAL)
async def exploit_check():
    config   = load_json(CONFIG_FILE, {})
    previous = load_json(STATE_FILE, {})
    api_data = await fetch_exploits()
    if not api_data: return
    changed = False
    for guild_id, gcfg in config.items():
        if not gcfg.get("enabled"): continue
        ch_id = gcfg.get("channel_id")
        if not ch_id or ch_id == "none": continue
        guild = bot.get_guild(int(guild_id))
        if not guild: continue
        channel = guild.get_channel(int(ch_id))
        if not channel: continue
        role_id = gcfg.get("role_id")
        for exp_name in gcfg.get("exploits", DEFAULT_EXPLOITS):
            info = get_exploit(api_data, exp_name)
            if not info: continue
            real    = info.get("name", exp_name)
            key     = f"{guild_id}_{real.lower()}"
            cur_st  = info.get("status", "Unknown")
            cur_ver = info.get("version", "N/A")
            prev    = previous.get(key, {})
            previous[key] = {"status": cur_st, "version": cur_ver}
            changed = True
            if prev.get("status") == cur_st and prev.get("version") == cur_ver: continue
            # Build alert
            is_on   = cur_st.lower() == "online"
            color   = C_SUCCESS if is_on else (C_ERROR if cur_st.lower()=="patched" else C_WARN)
            dl      = info.get("download", info.get("download_link", info.get("link", None)))
            embed = discord.Embed(
                title=f"🔔  Actualización Detectada — {real}",
                color=color, timestamp=datetime.now(timezone.utc))
            embed.set_author(name=f"{BOT_NAME} • Executor Tracker", icon_url=DOT_GREEN if is_on else DOT_RED)
            if prev.get("status") and prev["status"] != cur_st:
                embed.add_field(name="🔄 Estado",  value=f"`{prev['status']}` → `{cur_st}`",   inline=True)
            if prev.get("version") and prev["version"] != cur_ver:
                embed.add_field(name="📦 Versión", value=f"`{prev['version']}` → `{cur_ver}`", inline=True)
            embed.add_field(name="Estado actual", value=f"{_status_emoji(cur_st)} **{cur_st}**", inline=True)
            embed.add_field(name="Versión",       value=f"`{cur_ver}`",                          inline=True)
            embed.add_field(name="Plataforma",    value=info.get("platform","N/A"),              inline=True)
            embed.add_field(name="Actualizado",   value=str(info.get("updated_at", info.get("last_updated","N/A"))), inline=False)
            if dl:
                embed.add_field(name="🔗 Descarga", value=f"[⬇️ Descargar aquí]({dl})", inline=False)
            embed.set_image(url=BANNER_EXEC)
            embed.set_footer(text=_footer("api.weao.xyz"))
            mention = "@everyone"
            if role_id:
                role = guild.get_role(int(role_id))
                if role: mention = role.mention
            try:
                await channel.send(content=mention, embed=embed)
                logger.info(f"[alert] {real}: {prev.get('status','?')}→{cur_st} @ {guild.name}")
            except discord.Forbidden:
                logger.warning(f"[alert] Sin permisos en {guild.name}#{channel.name}")
            except Exception as ex:
                logger.error(f"[alert] {ex}")
    if changed: save_json(STATE_FILE, previous)

@exploit_check.before_loop
async def _before(): await bot.wait_until_ready(); await asyncio.sleep(15)

# ──────────────────────────────────────────────────────────────────
#  SETUP VIEW
# ──────────────────────────────────────────────────────────────────

class SetupView(discord.ui.View):
    def __init__(self, guild: discord.Guild, cfg: dict):
        super().__init__(timeout=180)
        self.guild = guild; self.cfg = cfg.copy()
        txt_chs = [c for c in guild.channels if isinstance(c, discord.TextChannel)][:25]
        ch_opts = [discord.SelectOption(label=f"#{c.name}", value=str(c.id),
                    default=(str(c.id)==str(cfg.get("channel_id","")))) for c in txt_chs] \
                  or [discord.SelectOption(label="Sin canales", value="none")]
        chs = discord.ui.Select(placeholder="📢 Canal de alertas", options=ch_opts, row=0)
        chs.callback = self._ch; self.add_item(chs)
        roles = [r for r in guild.roles if r.name != "@everyone"][:24]
        r_opts = [discord.SelectOption(label="@everyone", value="none", default=not cfg.get("role_id"))]
        r_opts += [discord.SelectOption(label=f"@{r.name}", value=str(r.id),
                    default=(str(r.id)==str(cfg.get("role_id","")))) for r in roles]
        rs = discord.ui.Select(placeholder="👥 Rol a mencionar", options=r_opts[:25], row=1)
        rs.callback = self._role; self.add_item(rs)

    async def _ch(self, i): self.cfg["channel_id"] = i.data["values"][0]; await i.response.defer()
    async def _role(self, i):
        v = i.data["values"][0]; self.cfg["role_id"] = None if v=="none" else v; await i.response.defer()

    @discord.ui.button(label="✅ Activar",    style=discord.ButtonStyle.success, row=2)
    async def _on(self, i, _): self.cfg["enabled"]=True;  await i.response.send_message("✅ Activadas.",    ephemeral=True)

    @discord.ui.button(label="🔕 Desactivar", style=discord.ButtonStyle.danger,  row=2)
    async def _off(self, i, _): self.cfg["enabled"]=False; await i.response.send_message("🔕 Desactivadas.", ephemeral=True)

    @discord.ui.button(label="💾 Guardar", style=discord.ButtonStyle.primary, row=3)
    async def _save(self, i, _):
        cfg = load_json(CONFIG_FILE, {}); gid = str(self.guild.id)
        cfg.setdefault(gid,{}).update(self.cfg); cfg[gid].setdefault("exploits", DEFAULT_EXPLOITS)
        save_json(CONFIG_FILE, cfg)
        ch   = self.guild.get_channel(int(self.cfg["channel_id"])) if self.cfg.get("channel_id","")!="none" and self.cfg.get("channel_id") else None
        role = self.guild.get_role(int(self.cfg["role_id"]))        if self.cfg.get("role_id") else None
        embed = discord.Embed(title="✅ Configuración Guardada", color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"{BOT_NAME} • Setup", icon_url=DOT_GREEN)
        embed.add_field(name="📢 Canal",    value=ch.mention   if ch   else "No config", inline=True)
        embed.add_field(name="👥 Rol",     value=role.mention if role else "@everyone",  inline=True)
        embed.add_field(name="🔔 Alertas", value="✅ Activas" if self.cfg.get("enabled") else "🔕 Off", inline=True)
        await i.response.edit_message(embed=embed, view=None); self.stop()

# ──────────────────────────────────────────────────────────────────
#  SLASH — BYPASS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="bypass", description="🔓 Bypassea un enlace y obtén el resultado real")
@app_commands.describe(url="Enlace a bypassear")
async def cmd_bypass(interaction: discord.Interaction, url: str):
    if not _is_url(url):
        return await interaction.response.send_message(
            embed=discord.Embed(description="⚠️ URL inválida.", color=C_WARN), ephemeral=True)
    loading = discord.Embed(
        title=f"⏳  {BOT_NAME} • Procesando Bypass...",
        description="```fix\nConectando con el motor de bypass...\nEspera unos segundos.\n```",
        color=C_WARN, timestamp=datetime.now(timezone.utc))
    loading.set_author(name=f"{BOT_NAME} • BYPASS ENGINE", icon_url=bot.user.display_avatar.url if bot.user else None)
    loading.set_thumbnail(url=GIF_LOADING)
    loading.set_footer(text=_footer(f"Usuario: {interaction.user.name}"))
    await interaction.response.send_message(embed=loading)
    t0 = time.time()
    result, error = await asyncio.get_running_loop().run_in_executor(None, _bypass_sync, url)
    elapsed = time.time() - t0
    if result:
        await interaction.edit_original_response(embed=_build_bypass_success(result, elapsed, url), view=BypassView(result))
        logger.info(f"[bypass] ✅ {interaction.user} url={url[:60]}")
    else:
        await interaction.edit_original_response(embed=_build_bypass_error(error, url, elapsed), view=ErrorBypassView())
        logger.info(f"[bypass] ❌ {interaction.user} err={error}")


@bot.tree.command(name="setautobypass", description="⚙️ [Admin] Toggle auto-bypass en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautobypass(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in autobypass_channels:
        autobypass_channels.discard(cid); _save_ab()
        e = discord.Embed(title="🔴 Auto-Bypass DESACTIVADO",
                          description=f"{interaction.channel.mention} ya no processará enlaces automáticamente.", color=C_ERROR)
    else:
        autobypass_channels.add(cid); _save_ab()
        e = discord.Embed(title="🟢 Auto-Bypass ACTIVADO",
                          description=f"Los enlaces en {interaction.channel.mention} se bypasearán automáticamente.\nEl mensaje original se **elimina** y se devuelve el resultado.", color=C_SUCCESS)
    e.set_author(name=f"{BOT_NAME} • Auto-Bypass", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.set_footer(text=_footer(f"Canales activos: {len(autobypass_channels)}"))
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_setautobypass.error
async def _ae(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Administrador**.", ephemeral=True)

# ── bypass-info group ───────────────────────────────────────────
bp_group = app_commands.Group(name="bypass-info", description="Info de bypass de exploits (WEAO API)")

@bp_group.command(name="check", description="Estado de bypass de un exploit específico")
@app_commands.describe(exploit="Nombre del exploit")
async def bi_check(interaction: discord.Interaction, exploit: str):
    await interaction.response.defer()
    data = await fetch_exploits()
    info = get_exploit(data, exploit)
    if not info:
        return await interaction.followup.send(f"❌ No se encontró **{exploit}**.", ephemeral=True)
    nombre = info.get("name", exploit); estado = info.get("status","Unknown")
    ver = info.get("version","N/A"); plat = info.get("platform","N/A")
    dl  = info.get("download", info.get("download_link", info.get("link",None)))
    is_on = estado.lower()=="online"
    byfron = info.get("byfron_bypass", info.get("bypass", is_on))
    hyp    = info.get("hyperion_bypass", info.get("anti_cheat", is_on))
    luau   = info.get("luau_support", True)
    embed = discord.Embed(title=f"🛡️  {nombre} — Bypass Info",
                          color=C_SUCCESS if is_on else C_ERROR, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Bypass Info", icon_url=DOT_GREEN if is_on else DOT_RED)
    embed.add_field(name="Estado",          value=f"{_status_emoji(estado)} **{estado}**", inline=True)
    embed.add_field(name="Versión",         value=f"`{ver}`",                               inline=True)
    embed.add_field(name="Plataforma",      value=plat,                                     inline=True)
    embed.add_field(name="Byfron Bypass",   value=_bypass_emoji(byfron),                    inline=True)
    embed.add_field(name="Hyperion Bypass", value=_bypass_emoji(hyp),                       inline=True)
    embed.add_field(name="LuaU Support",    value=_bypass_emoji(luau),                      inline=True)
    if dl: embed.add_field(name="🔗 Descarga", value=f"[⬇️ Descargar]({dl})", inline=False)
    embed.set_image(url=BANNER_EXEC)
    embed.set_footer(text=_footer("api.weao.xyz"))
    await interaction.followup.send(embed=embed)

@bp_group.command(name="working", description="Lista todos los exploits online en este momento")
async def bi_working(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await fetch_exploits()
    cfg  = load_json(CONFIG_FILE,{})
    lst  = cfg.get(str(interaction.guild_id),{}).get("exploits", DEFAULT_EXPLOITS)
    working = []
    for name in lst:
        info = get_exploit(data, name)
        if info and info.get("status","").lower()=="online":
            working.append(f"🟢 **{info.get('name',name)}** — v`{info.get('version','N/A')}` | {info.get('platform','N/A')}")
    if not working:
        embed = discord.Embed(title="🛡️  Exploits Working",
                              description="⚠️ Ningún exploit está **online** en este momento.", color=C_ERROR, timestamp=datetime.now(timezone.utc))
    else:
        embed = discord.Embed(title=f"🛡️  Exploits Working — {len(working)} activos",
                              description="\n".join(working)[:4000], color=C_SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=_footer(f"{len(working)}/{len(lst)} online • api.weao.xyz"))
    embed.set_author(name=f"{BOT_NAME} • Bypass Working", icon_url=DOT_GREEN)
    await interaction.followup.send(embed=embed)

@bp_group.command(name="compare", description="Compara bypass de dos exploits")
@app_commands.describe(exploit1="Primer exploit", exploit2="Segundo exploit")
async def bi_compare(interaction: discord.Interaction, exploit1: str, exploit2: str):
    await interaction.response.defer()
    data = await fetch_exploits()
    def _f(info, name):
        if not info: return {"name":name,"estado":"N/A","ver":"N/A","byfron":False,"hyp":False,"luau":False}
        st=info.get("status","?"); on=st.lower()=="online"
        return {"name":info.get("name",name),"estado":st,"ver":info.get("version","N/A"),
                "byfron":info.get("byfron_bypass",on),"hyp":info.get("hyperion_bypass",on),"luau":info.get("luau_support",True)}
    d1=_f(get_exploit(data,exploit1),exploit1); d2=_f(get_exploit(data,exploit2),exploit2)
    embed = discord.Embed(title="⚔️  Comparación de Bypass", color=C_MAIN, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Bypass Compare", icon_url=bot.user.display_avatar.url if bot.user else None)
    for d, icon in [(d1,"🔷"),(d2,"🔶")]:
        embed.add_field(name=f"{icon} {d['name']}",
                        value=(f"{_status_emoji(d['estado'])} {d['estado']}\n"
                               f"Ver: `{d['ver']}`\n"
                               f"Byfron: {_bypass_emoji(d['byfron'])}\n"
                               f"Hyperion: {_bypass_emoji(d['hyp'])}\n"
                               f"LuaU: {_bypass_emoji(d['luau'])}"), inline=True)
    embed.set_footer(text=_footer("api.weao.xyz"))
    await interaction.followup.send(embed=embed)

bot.tree.add_command(bp_group)

# ──────────────────────────────────────────────────────────────────
#  SLASH — EXECUTOR TRACKER
# ──────────────────────────────────────────────────────────────────

ex_group = app_commands.Group(name="executors", description="Estado de exploits de Roblox — WEAO API")

@ex_group.command(name="stat", description="Estado de un exploit o de todos")
@app_commands.describe(nombre="Nombre del exploit (vacío = todos)")
async def ex_stat(interaction: discord.Interaction, nombre: str = None):
    await interaction.response.defer()
    data = await fetch_exploits()
    cfg  = load_json(CONFIG_FILE,{})
    lst  = cfg.get(str(interaction.guild_id),{}).get("exploits", DEFAULT_EXPLOITS)
    if not nombre:
        lines = []
        for n in lst:
            info = get_exploit(data,n)
            if info: st=info.get("status","?"); lines.append(f"{_status_emoji(st)} **{info.get('name',n)}** — {st}")
            else:    lines.append(f"⚪ **{n}** — Sin datos")
        chunk,chunks=[],[]
        for line in lines:
            chunk.append(line)
            if len("\n".join(chunk))>3500: chunks.append("\n".join(chunk[:-1])); chunk=[line]
        chunks.append("\n".join(chunk))
        embed = discord.Embed(title=f"📋  Estado de Exploits — {len(lst)} tracked",
                              description=chunks[0] or "Sin datos.", color=C_INFO, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"{BOT_NAME} • Executor Tracker", icon_url=bot.user.display_avatar.url if bot.user else None)
        embed.set_footer(text=_footer("api.weao.xyz"))
        await interaction.followup.send(embed=embed)
        for extra in chunks[1:]:
            await interaction.followup.send(embed=discord.Embed(description=extra, color=C_INFO))
        return
    info = get_exploit(data, nombre)
    if not info:
        return await interaction.followup.send(f"❌ No se encontró **{nombre}**. Comprueba el nombre exacto.", ephemeral=True)
    estado=info.get("status","Unknown"); ver=info.get("version","N/A")
    plat=info.get("platform","N/A"); upd=info.get("updated_at",info.get("last_updated","N/A"))
    dl=info.get("download",info.get("download_link",info.get("link",None)))
    is_on=estado.lower()=="online"
    color=C_SUCCESS if is_on else (C_ERROR if estado.lower()=="patched" else C_WARN)
    embed=discord.Embed(title=f"{_status_emoji(estado)}  {info.get('name',nombre)}", color=color, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Executor Tracker", icon_url=DOT_GREEN if is_on else DOT_RED)
    embed.add_field(name="Estado",     value=f"**{estado}**", inline=True)
    embed.add_field(name="Versión",    value=f"`{ver}`",       inline=True)
    embed.add_field(name="Plataforma", value=plat,             inline=True)
    embed.add_field(name="Actualizado",value=str(upd),         inline=False)
    if dl: embed.add_field(name="🔗 Descarga", value=f"[⬇️ Descargar aquí]({dl})", inline=False)
    embed.set_image(url=BANNER_EXEC)
    embed.set_thumbnail(url=DOT_GREEN if is_on else DOT_RED)
    embed.set_footer(text=_footer("api.weao.xyz"))
    await interaction.followup.send(embed=embed)

bot.tree.add_command(ex_group)


@bot.tree.command(name="supported", description="Lista de exploits vigilados en este servidor")
async def cmd_supported(interaction: discord.Interaction):
    cfg = load_json(CONFIG_FILE,{}); lst = cfg.get(str(interaction.guild_id),{}).get("exploits", DEFAULT_EXPLOITS)
    text = "\n".join(f"• {e}" for e in lst)
    embed = discord.Embed(title="📋  Exploits Vigilados",
                          description=text[:4000] or "Sin exploits.", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Executor Tracker", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.set_footer(text=_footer(f"Total: {len(lst)}"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="set", description="⚙️ Configura las alertas automáticas de exploits")
@app_commands.default_permissions(manage_guild=True)
async def cmd_set(interaction: discord.Interaction):
    cfg = load_json(CONFIG_FILE,{}); gcfg = cfg.get(str(interaction.guild_id),{})
    ch_v = f"<#{gcfg['channel_id']}>" if gcfg.get("channel_id") else "No configurado"
    rl_v = f"<@&{gcfg['role_id']}>"   if gcfg.get("role_id")    else "@everyone"
    en_v = "✅ Activas" if gcfg.get("enabled") else "🔕 Desactivadas"
    embed = discord.Embed(title=f"⚙️  {BOT_NAME} — Configurar Alertas",
                          description="Selecciona el canal y el rol, activa las alertas y guarda.", color=C_MAIN)
    embed.set_author(name=f"{BOT_NAME} • Setup", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.add_field(name="Configuración actual",
                    value=f"📢 Canal: {ch_v}\n👥 Rol: {rl_v}\n🔔 Alertas: {en_v}", inline=False)
    embed.set_image(url=BANNER_BOT)
    await interaction.response.send_message(embed=embed, view=SetupView(interaction.guild, gcfg), ephemeral=True)

# ──────────────────────────────────────────────────────────────────
#  SLASH — IA
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ai-chat", description="🤖 Chatea con la IA Groq")
@app_commands.describe(mensaje="Tu mensaje")
async def cmd_ai_chat(interaction: discord.Interaction, mensaje: str):
    await interaction.response.defer()
    reply = await ask_groq(mensaje)
    embed = discord.Embed(color=C_MAIN, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • IA Chat", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.add_field(name="💬 Tu mensaje", value=f"```{mensaje[:500]}```", inline=False)
    embed.add_field(name="🤖 Respuesta",  value=reply[:1000],             inline=False)
    embed.set_thumbnail(url=BANNER_AI)
    embed.set_footer(text=_footer("Groq • llama3-8b"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="ask-ai", description="❓ Pregúntale algo a la IA")
@app_commands.describe(pregunta="Tu pregunta")
async def cmd_ask_ai(interaction: discord.Interaction, pregunta: str):
    await interaction.response.defer()
    reply = await ask_groq(pregunta, system="Eres un asistente experto. Responde de forma precisa y concisa en español.")
    embed = discord.Embed(title="〔 ❓ 〕 Respuesta IA", description=reply[:2000],
                          color=C_MAIN, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Ask AI", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.set_thumbnail(url=BANNER_AI)
    embed.set_footer(text=_footer(f"Pregunta de {interaction.user.name}"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="translate-text", description="🌐 Traduce texto a cualquier idioma")
@app_commands.describe(texto="Texto a traducir", idioma="Idioma destino (ej: inglés, francés, japonés)")
async def cmd_translate(interaction: discord.Interaction, texto: str, idioma: str = "inglés"):
    await interaction.response.defer()
    result = await ask_groq(texto, system=f"Eres un traductor experto. Traduce exactamente al {idioma} sin comentarios.")
    embed = discord.Embed(title="🌐  Traducción", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Traductor", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.add_field(name="📝 Original",          value=f"```{texto[:400]}```",  inline=False)
    embed.add_field(name=f"🌐 {idioma.title()}", value=f"```{result[:400]}```", inline=False)
    embed.set_footer(text=_footer("Groq • llama3-8b"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="summarize-text", description="📋 Resume un texto largo")
@app_commands.describe(texto="Texto a resumir")
async def cmd_summarize(interaction: discord.Interaction, texto: str):
    await interaction.response.defer()
    result = await ask_groq(texto, system="Eres un experto en resúmenes. Resume en bullet points claros en español.")
    embed = discord.Embed(title="📋  Resumen IA", color=C_INFO, timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{BOT_NAME} • Resumen", icon_url=bot.user.display_avatar.url if bot.user else None)
    embed.add_field(name="📝 Resumen", value=result[:1900], inline=False)
    embed.set_footer(text=_footer(f"Original: {len(texto)} chars"))
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="set-ia-channel", description="🤖 [Admin] Toggle IA automática en este canal")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_set_ia(interaction: discord.Interaction):
    cid = interaction.channel_id
    if cid in ia_channels:
        ia_channels.discard(cid); _save_ia()
        e = discord.Embed(title="🔴 Canal IA Desactivado",
                          description=f"{interaction.channel.mention} ya no responderá con IA.", color=C_ERROR)
    else:
        ia_channels.add(cid); _save_ia()
        e = discord.Embed(title="🟢 Canal IA Activado",
                          description=f"{interaction.channel.mention} responderá con IA a todos los mensajes.\n"
                                      f"```yaml\nModelo  : llama3-8b-8192\nActivos : {len(ia_channels)} canal(es)\n```",
                          color=C_SUCCESS)
    e.set_author(name=f"{BOT_NAME} • IA Config", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e, ephemeral=True)

@cmd_set_ia.error
async def _sia_err(i, e):
    if isinstance(e, app_commands.MissingPermissions):
        await i.response.send_message("🚫 Necesitas **Administrador**.", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
#  SLASH — UTILIDAD
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ping", description="🏓 Latencia del bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    color = C_SUCCESS if ms<100 else (C_WARN if ms<200 else C_ERROR)
    e = discord.Embed(title="🏓 Pong!", color=color)
    e.add_field(name="📡 Latencia",   value=f"**`{ms}ms`**",    inline=True)
    e.add_field(name="⏱️ Uptime",     value=f"`{_uptime()}`",   inline=True)
    e.add_field(name="🌐 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    e.set_footer(text=_footer())
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="info", description="🤖 Información del bot")
async def cmd_info(interaction: discord.Interaction):
    e = discord.Embed(title=f"🤖  {BOT_NAME}", color=C_MAIN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} — Info", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.description = f"```yaml\nNombre  : {BOT_NAME}\nCredito : {BOT_CREDIT}\nLibrería: discord.py 2.3\n```"
    e.add_field(name="🌐 Servidores",       value=f"`{len(bot.guilds)}`",        inline=True)
    e.add_field(name="📡 Latencia",         value=f"`{round(bot.latency*1000)}ms`", inline=True)
    e.add_field(name="⏱️ Uptime",           value=f"`{_uptime()}`",               inline=True)
    e.add_field(name="🔄 Executor Check",   value=f"Cada `{CHECK_INTERVAL}s`",    inline=True)
    e.add_field(name="🔓 Bypass Engine",    value="`4PI API`",                     inline=True)
    e.add_field(name="🤖 IA Modelo",        value=f"`{GROQ_MODEL}`",              inline=True)
    e.set_image(url=BANNER_BOT)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="Soporte",     url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, emoji="💬"))
    v.add_item(Button(label="Invitar Bot", url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, emoji="🤖"))
    await interaction.response.send_message(embed=e, view=v)


@bot.tree.command(name="help", description="📖 Lista completa de comandos")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(title=f"📖  {BOT_NAME} — Comandos", color=C_MAIN, timestamp=datetime.now(timezone.utc))
    e.set_author(name=f"{BOT_NAME} {BOT_CREDIT}", icon_url=bot.user.display_avatar.url if bot.user else None)
    e.add_field(name="🔓 __BYPASS__",
                value=("`/bypass <url>` — Bypassear enlace\n"
                       "`/setautobypass` — Toggle auto-bypass en canal *(Admin)*\n"
                       "`/bypass-info check <exploit>` — Info bypass\n"
                       "`/bypass-info working` — Exploits online\n"
                       "`/bypass-info compare <e1> <e2>` — Comparar 2 exploits"),
                inline=False)
    e.add_field(name="🎮 __EXECUTOR TRACKER__",
                value=("`/executors stat [nombre]` — Estado de exploit(s)\n"
                       "`/supported` — Exploits vigilados\n"
                       "`/set` — Configurar alertas automáticas *(Manage Server)*"),
                inline=False)
    e.add_field(name="🤖 __IA (Groq llama3)__",
                value=("`/ai-chat <mensaje>` — Chat con IA\n"
                       "`/ask-ai <pregunta>` — Pregunta a la IA\n"
                       "`/translate-text <texto> <idioma>` — Traducir\n"
                       "`/summarize-text <texto>` — Resumir\n"
                       "`/set-ia-channel` — Toggle IA en canal *(Admin)*"),
                inline=False)
    e.add_field(name="📊 __UTILIDAD__",
                value="`/ping` `/info` `/help`",
                inline=False)
    e.set_image(url=BANNER_BOT)
    e.set_footer(text=_footer())
    v = View()
    v.add_item(Button(label="Soporte",     url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link, emoji="💬"))
    v.add_item(Button(label="Invitar Bot", url=BOT_INVITE_URL,     style=discord.ButtonStyle.link, emoji="🤖"))
    await interaction.response.send_message(embed=e, view=v)

# ──────────────────────────────────────────────────────────────────
#  HEALTH SERVER (Render keepalive)
# ──────────────────────────────────────────────────────────────────

async def _health(_): 
    return aiohttp.web.Response(
        text=f'{{"status":"online","bot":"{BOT_NAME}","uptime":"{_uptime()}"}}',
        content_type="application/json", status=200)

async def start_web():
    app = aiohttp.web.Application()
    app.router.add_get("/",       _health)
    app.router.add_get("/health", _health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Health server en :{PORT}")

# ──────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────────

async def main():
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN no encontrado.")
        return
    if not GROQ_API_KEY:
        logger.warning("⚠️  GROQ_API_KEY no encontrado — comandos IA deshabilitados.")
    await start_web()
    logger.info(f"🚀 Iniciando {BOT_NAME}...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
