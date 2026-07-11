import discord
from discord import app_commands
from discord.ext import tasks
import aiohttp
from aiohttp import web
import json
import os
import asyncio
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

WEAO_API       = "https://api.weao.xyz/v1/exploits"
CHECK_INTERVAL = 90  # segundos
PORT           = int(os.environ.get("PORT", 8080))

EMOJI_GREEN_DOT   = "https://cdn.discordapp.com/emojis/1425942717208199389.webp?size=100&animated=true"
EMOJI_GREEN_ARROW = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"
EMOJI_SUCCESS     = "https://cdn.discordapp.com/emojis/1525379448768303207.webp?size=100&animated=true"
EMOJI_LINK        = "https://cdn.discordapp.com/emojis/1401389059485597836.webp?size=100&animated=true"

GLOBAL_EXPLOITS = [
    "Solara", "Wave", "AWP", "Vega X", "Delta", "Hydrogen", "Fluxus",
    "Electron", "Nihon", "Celestial", "Velocity", "Oxygen U", "Comet",
    "Zypher", "Krnl", "Synapse X", "Script-Ware", "Evon", "JJSploit",
    "Coco", "Zen", "Borealis", "Sirius", "Xeno", "Rise", "Valyse",
    "Elysian", "Novus", "Vynixius", "Seliware", "Exoliner", "Neo",
    "Trigon", "Eclipse", "Oblivion", "Fates", "Arceus X", "Mystic",
    "Aurora", "Nexus", "Quantum", "Phantom", "Infinity", "Legendary",
    "Carbon", "X-Code", "Skrypt", "Vortex", "Horizon", "Genesis",
    "Apex", "Nova", "Stellar", "Pandora", "Zeus", "Hades", "Ares",
    "Atlas", "Eden", "Frost", "Storm", "Blaze", "Shadow", "Light", "Dark",
]

CONFIG_FILE = "config.json"
STATE_FILE  = "estado_anterior.json"

# ─────────────────────────────────────────────
# HELPERS DE PERSISTENCIA
# ─────────────────────────────────────────────

def load_json(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)


# ─────────────────────────────────────────────
# WEAO API
# ─────────────────────────────────────────────

async def fetch_exploits() -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEAO_API, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data  = await resp.json(content_type=None)
                    items = data if isinstance(data, list) else data.get("exploits", data.get("data", []))
                    return {item.get("name", "").lower(): item for item in items if item.get("name")}
    except Exception as e:
        print(f"[WEAO] Error: {e}")
    return {}


def status_emoji(status: str) -> str:
    s = (status or "").lower()
    if s == "online":   return "🟢"
    if s == "patched":  return "🔴"
    return "🟡"


def bypass_emoji(value: bool) -> str:
    return "✅" if value else "❌"


def get_exploit_info(api_data: dict, name: str):
    return api_data.get(name.lower())


# ─────────────────────────────────────────────
# GRUPO: /executors
# ─────────────────────────────────────────────

executors_group = app_commands.Group(name="executors", description="Información sobre exploits de Roblox")


@executors_group.command(name="stat", description="Estado de todos los exploits o de uno específico")
@app_commands.describe(nombre="Nombre del exploit (opcional)")
async def executors_stat(interaction: discord.Interaction, nombre: str = None):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)

    if not nombre:
        lines = []
        for exp_name in guild_exploits:
            info = get_exploit_info(api_data, exp_name)
            if info:
                estado = info.get("status", "Unknown")
                lines.append(f"{status_emoji(estado)} **{exp_name}** — {estado}")
            else:
                lines.append(f"⚪ **{exp_name}** — Sin datos")

        chunks, chunk = [], []
        for line in lines:
            chunk.append(line)
            if len(chunk) == 20:
                chunks.append("\n".join(chunk))
                chunk = []
        if chunk:
            chunks.append("\n".join(chunk))

        embed = discord.Embed(
            title="📋 Estado de todos los Exploits",
            description=chunks[0] if chunks else "No hay exploits registrados.",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Total: {len(guild_exploits)} exploits • Actualizado")
        await interaction.followup.send(embed=embed)
        for extra in chunks[1:]:
            await interaction.followup.send(embed=discord.Embed(description=extra, color=0x5865F2))
        return

    info = get_exploit_info(api_data, nombre)
    if not info:
        await interaction.followup.send(f"❌ No se encontró **{nombre}**.", ephemeral=True)
        return

    estado   = info.get("status", "Unknown")
    version  = info.get("version", "N/A")
    platform = info.get("platform", "N/A")
    updated  = info.get("updated_at", info.get("last_updated", "N/A"))
    dl_link  = info.get("download", info.get("download_link", info.get("link", None)))
    color    = 0x57F287 if estado.lower() == "online" else (0xED4245 if estado.lower() == "patched" else 0xFEE75C)

    embed = discord.Embed(
        title=f"{status_emoji(estado)} {info.get('name', nombre)}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Estado",    value=estado,   inline=True)
    embed.add_field(name="Versión",   value=version,  inline=True)
    embed.add_field(name="Plataforma", value=platform, inline=True)
    embed.add_field(name="Última actualización", value=str(updated), inline=False)
    if dl_link:
        embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl_link})", inline=False)
    embed.set_thumbnail(url=EMOJI_GREEN_DOT if estado.lower() == "online" else EMOJI_GREEN_ARROW)
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)


tree.add_command(executors_group)


# ─────────────────────────────────────────────
# GRUPO: /bypass
# ─────────────────────────────────────────────

bypass_group = app_commands.Group(name="bypass", description="Información sobre bypass de exploits")


@bypass_group.command(name="check", description="Verifica el estado de bypass de un exploit específico")
@app_commands.describe(exploit="Nombre del exploit a verificar")
async def bypass_check(interaction: discord.Interaction, exploit: str):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    info = get_exploit_info(api_data, exploit)

    if not info:
        await interaction.followup.send(f"❌ No se encontró **{exploit}**.", ephemeral=True)
        return

    nombre   = info.get("name", exploit)
    estado   = info.get("status", "Unknown")
    version  = info.get("version", "N/A")
    platform = info.get("platform", "N/A")
    dl_link  = info.get("download", info.get("download_link", info.get("link", None)))

    # Campos de bypass (si la API los incluye, se usan; si no, se infiere del estado)
    brawser_bypass = info.get("byfron_bypass",    info.get("bypass",      estado.lower() == "online"))
    hyperion_bypass= info.get("hyperion_bypass",  info.get("anti_cheat",  estado.lower() == "online"))
    lua_u_support  = info.get("luau_support",     info.get("luau",        True))
    ux_bypass      = info.get("ux_bypass",        info.get("ux",          estado.lower() == "online"))
    is_online      = estado.lower() == "online"

    color = 0x57F287 if is_online else 0xED4245
    thumb = EMOJI_GREEN_DOT if is_online else EMOJI_GREEN_ARROW

    embed = discord.Embed(
        title=f"🛡️ Bypass Info — {nombre}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Estado",           value=f"{status_emoji(estado)} {estado}", inline=True)
    embed.add_field(name="Versión",          value=version,                            inline=True)
    embed.add_field(name="Plataforma",       value=platform,                           inline=True)
    embed.add_field(name="Byfron Bypass",    value=bypass_emoji(brawser_bypass),       inline=True)
    embed.add_field(name="Hyperion Bypass",  value=bypass_emoji(hyperion_bypass),      inline=True)
    embed.add_field(name="LuaU Support",     value=bypass_emoji(lua_u_support),        inline=True)
    embed.add_field(name="UX Bypass",        value=bypass_emoji(ux_bypass),            inline=True)
    if dl_link:
        embed.add_field(name="🔗 Descarga",  value=f"[Descargar aquí]({dl_link})",    inline=False)
    embed.set_thumbnail(url=thumb)
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)


@bypass_group.command(name="list", description="Lista todos los exploits con su estado de bypass")
async def bypass_list(interaction: discord.Interaction):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)

    online, patched, unknown = [], [], []
    for exp_name in guild_exploits:
        info = get_exploit_info(api_data, exp_name)
        if not info:
            unknown.append(f"⚪ {exp_name}")
            continue
        st = info.get("status", "Unknown").lower()
        if st == "online":
            online.append(f"🟢 **{exp_name}** `v{info.get('version','?')}`")
        elif st == "patched":
            patched.append(f"🔴 {exp_name}")
        else:
            unknown.append(f"🟡 {exp_name}")

    embed = discord.Embed(
        title="🛡️ Estado de Bypass — Todos los exploits",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    if online:
        embed.add_field(
            name=f"✅ Con Bypass Activo ({len(online)})",
            value="\n".join(online[:20]) + (f"\n...y {len(online)-20} más" if len(online)>20 else ""),
            inline=False,
        )
    if patched:
        embed.add_field(
            name=f"❌ Patched / Sin Bypass ({len(patched)})",
            value="\n".join(patched[:15]) + (f"\n...y {len(patched)-15} más" if len(patched)>15 else ""),
            inline=False,
        )
    if unknown:
        embed.add_field(
            name=f"⚠️ Estado Desconocido ({len(unknown)})",
            value="\n".join(unknown[:10]),
            inline=False,
        )
    embed.set_footer(text=f"Total vigilados: {len(guild_exploits)}")
    await interaction.followup.send(embed=embed)


@bypass_group.command(name="compare", description="Compara el bypass de dos exploits")
@app_commands.describe(exploit1="Primer exploit", exploit2="Segundo exploit")
async def bypass_compare(interaction: discord.Interaction, exploit1: str, exploit2: str):
    await interaction.response.defer()
    api_data = await fetch_exploits()

    info1 = get_exploit_info(api_data, exploit1)
    info2 = get_exploit_info(api_data, exploit2)

    if not info1 and not info2:
        await interaction.followup.send("❌ No se encontró ninguno de los dos exploits.", ephemeral=True)
        return

    def get_bypass_fields(info, name):
        if not info:
            return {"nombre": name, "estado": "N/A", "version": "N/A", "byfron": False, "hyperion": False, "luau": False}
        st = info.get("status", "Unknown")
        is_on = st.lower() == "online"
        return {
            "nombre":   info.get("name", name),
            "estado":   st,
            "version":  info.get("version", "N/A"),
            "byfron":   info.get("byfron_bypass",   info.get("bypass",   is_on)),
            "hyperion": info.get("hyperion_bypass",  info.get("anti_cheat", is_on)),
            "luau":     info.get("luau_support",     True),
        }

    d1 = get_bypass_fields(info1, exploit1)
    d2 = get_bypass_fields(info2, exploit2)

    embed = discord.Embed(
        title=f"⚔️ Comparación de Bypass",
        color=0x9B59B6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name=f"🔹 {d1['nombre']}",
        value=(
            f"Estado: {status_emoji(d1['estado'])} {d1['estado']}\n"
            f"Versión: `{d1['version']}`\n"
            f"Byfron: {bypass_emoji(d1['byfron'])}\n"
            f"Hyperion: {bypass_emoji(d1['hyperion'])}\n"
            f"LuaU: {bypass_emoji(d1['luau'])}"
        ),
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name=f"🔸 {d2['nombre']}",
        value=(
            f"Estado: {status_emoji(d2['estado'])} {d2['estado']}\n"
            f"Versión: `{d2['version']}`\n"
            f"Byfron: {bypass_emoji(d2['byfron'])}\n"
            f"Hyperion: {bypass_emoji(d2['hyperion'])}\n"
            f"LuaU: {bypass_emoji(d2['luau'])}"
        ),
        inline=True,
    )
    embed.set_footer(text="Datos de api.weao.xyz")
    await interaction.followup.send(embed=embed)


@bypass_group.command(name="working", description="Muestra solo los exploits con bypass activo en este momento")
async def bypass_working(interaction: discord.Interaction):
    await interaction.response.defer()
    api_data = await fetch_exploits()
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)

    working = []
    for exp_name in guild_exploits:
        info = get_exploit_info(api_data, exp_name)
        if info and info.get("status", "").lower() == "online":
            version = info.get("version", "N/A")
            platform = info.get("platform", "N/A")
            working.append(f"🟢 **{info.get('name', exp_name)}** — v`{version}` | {platform}")

    if not working:
        embed = discord.Embed(
            title="🛡️ Exploits con Bypass Activo",
            description="⚠️ Ningún exploit está activo en este momento.",
            color=0xED4245,
            timestamp=datetime.now(timezone.utc),
        )
    else:
        chunks, chunk = [], []
        for line in working:
            chunk.append(line)
            if len(chunk) == 20:
                chunks.append("\n".join(chunk))
                chunk = []
        if chunk:
            chunks.append("\n".join(chunk))

        embed = discord.Embed(
            title=f"🛡️ Exploits con Bypass Activo ({len(working)})",
            description=chunks[0],
            color=0x57F287,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"{len(working)} exploits con bypass activo de {len(guild_exploits)} vigilados")

    await interaction.followup.send(embed=embed)
    if working and len(chunks) > 1:
        for extra in chunks[1:]:
            await interaction.followup.send(embed=discord.Embed(description=extra, color=0x57F287))


tree.add_command(bypass_group)


# ─────────────────────────────────────────────
# COMANDO: /supported
# ─────────────────────────────────────────────

@tree.command(name="supported", description="Lista de exploits vigilados en este servidor")
async def supported(interaction: discord.Interaction):
    config = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    guild_exploits = config.get(guild_id, {}).get("exploits", GLOBAL_EXPLOITS)

    lines = [f"• {e}" for e in guild_exploits]
    chunks, chunk = [], []
    for line in lines:
        chunk.append(line)
        if len(chunk) == 30:
            chunks.append("\n".join(chunk))
            chunk = []
    if chunk:
        chunks.append("\n".join(chunk))

    embed = discord.Embed(
        title="🗂️ Exploits vigilados en este servidor",
        description=chunks[0] if chunks else "No hay exploits configurados.",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"Total: {len(guild_exploits)} exploits")
    await interaction.response.send_message(embed=embed)
    for extra in chunks[1:]:
        await interaction.followup.send(embed=discord.Embed(description=extra, color=0x5865F2))


# ─────────────────────────────────────────────
# COMANDO: /set  — Panel interactivo (Admin)
# ─────────────────────────────────────────────

class SetupView(discord.ui.View):
    def __init__(self, guild: discord.Guild, current_config: dict):
        super().__init__(timeout=120)
        self.guild = guild
        self.cfg   = current_config.copy()
        self._build_selects()

    def _build_selects(self):
        text_channels = [c for c in self.guild.channels if isinstance(c, discord.TextChannel)][:25]
        channel_opts = [
            discord.SelectOption(
                label=f"#{c.name}", value=str(c.id),
                default=(str(c.id) == str(self.cfg.get("channel_id", ""))),
            )
            for c in text_channels
        ]
        ch_sel = discord.ui.Select(
            placeholder="📢 Selecciona el canal de alertas",
            options=channel_opts or [discord.SelectOption(label="Sin canales", value="none")],
            custom_id="channel_select", row=0,
        )
        ch_sel.callback = self.channel_callback
        self.add_item(ch_sel)

        roles = [r for r in self.guild.roles if r.name != "@everyone"][:24]
        role_opts = [discord.SelectOption(label="Ninguno", value="none", default=not self.cfg.get("role_id"))]
        role_opts += [
            discord.SelectOption(
                label=f"@{r.name}", value=str(r.id),
                default=(str(r.id) == str(self.cfg.get("role_id", ""))),
            )
            for r in roles
        ]
        r_sel = discord.ui.Select(
            placeholder="👥 Rol a mencionar (opcional)",
            options=role_opts[:25], custom_id="role_select", row=1,
        )
        r_sel.callback = self.role_callback
        self.add_item(r_sel)

    async def channel_callback(self, interaction: discord.Interaction):
        self.cfg["channel_id"] = interaction.data["values"][0]
        await interaction.response.defer()

    async def role_callback(self, interaction: discord.Interaction):
        val = interaction.data["values"][0]
        self.cfg["role_id"] = None if val == "none" else val
        await interaction.response.defer()

    @discord.ui.button(label="✅ Activar alertas",   style=discord.ButtonStyle.success, row=2)
    async def toggle_on(self, interaction: discord.Interaction, _b):
        self.cfg["enabled"] = True
        await interaction.response.send_message("✅ Alertas **activadas**.", ephemeral=True)

    @discord.ui.button(label="🔕 Desactivar alertas", style=discord.ButtonStyle.danger,  row=2)
    async def toggle_off(self, interaction: discord.Interaction, _b):
        self.cfg["enabled"] = False
        await interaction.response.send_message("🔕 Alertas **desactivadas**.", ephemeral=True)

    @discord.ui.button(label="💾 Guardar configuración", style=discord.ButtonStyle.primary, row=3)
    async def save(self, interaction: discord.Interaction, _b):
        config   = load_json(CONFIG_FILE, {})
        guild_id = str(self.guild.id)
        config.setdefault(guild_id, {}).update(self.cfg)
        config[guild_id].setdefault("exploits", GLOBAL_EXPLOITS)
        save_json(CONFIG_FILE, config)

        ch_id   = self.cfg.get("channel_id")
        role_id = self.cfg.get("role_id")
        enabled = self.cfg.get("enabled", False)
        channel = self.guild.get_channel(int(ch_id)) if ch_id and ch_id != "none" else None
        role    = self.guild.get_role(int(role_id))  if role_id else None

        embed = discord.Embed(title="⚙️ Configuración guardada", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Canal",   value=channel.mention if channel else "No configurado", inline=True)
        embed.add_field(name="Rol",     value=role.mention    if role    else "Sin mención",    inline=True)
        embed.add_field(name="Alertas", value="✅ Activas"    if enabled else "🔕 Desactivadas", inline=True)
        embed.set_thumbnail(url=EMOJI_SUCCESS)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@tree.command(name="set", description="Configura las alertas automáticas de exploits")
@app_commands.default_permissions(manage_guild=True)
async def set_auto(interaction: discord.Interaction):
    config   = load_json(CONFIG_FILE, {})
    guild_id = str(interaction.guild_id)
    current  = config.get(guild_id, {})

    ch_val  = f"<#{current['channel_id']}>" if current.get("channel_id") else "No configurado"
    rol_val = f"<@&{current['role_id']}>"   if current.get("role_id")    else "Sin mención"
    al_val  = "✅ Activas" if current.get("enabled") else "🔕 Desactivadas"

    embed = discord.Embed(
        title="⚙️ Configuración de Alertas Automáticas",
        description="Usa los menús para configurar el canal y el rol, luego guarda.",
        color=0x5865F2,
    )
    embed.add_field(name="Estado actual", value=f"Canal: {ch_val}\nRol: {rol_val}\nAlertas: {al_val}", inline=False)
    await interaction.response.send_message(embed=embed, view=SetupView(interaction.guild, current), ephemeral=True)


# ─────────────────────────────────────────────
# TAREA: VERIFICACIÓN AUTOMÁTICA CADA 90s
# ─────────────────────────────────────────────

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_exploits():
    config   = load_json(CONFIG_FILE, {})
    previous = load_json(STATE_FILE, {})
    api_data = await fetch_exploits()
    if not api_data:
        return

    changed = False
    for guild_id, guild_cfg in config.items():
        if not guild_cfg.get("enabled"):
            continue
        ch_id = guild_cfg.get("channel_id")
        if not ch_id or ch_id == "none":
            continue
        guild = client.get_guild(int(guild_id))
        if not guild:
            continue
        channel = guild.get_channel(int(ch_id))
        if not channel:
            continue

        role_id = guild_cfg.get("role_id")
        exploits_list = guild_cfg.get("exploits", GLOBAL_EXPLOITS)

        for exp_name in exploits_list:
            info = get_exploit_info(api_data, exp_name)
            if not info:
                continue

            real_name   = info.get("name", exp_name)
            key         = f"{guild_id}_{real_name.lower()}"
            cur_status  = info.get("status", "Unknown")
            cur_version = info.get("version", "N/A")
            prev        = previous.get(key, {})
            prev_status  = prev.get("status")
            prev_version = prev.get("version")

            previous[key] = {"status": cur_status, "version": cur_version}
            changed = True

            status_changed  = prev_status  is not None and prev_status  != cur_status
            version_changed = prev_version is not None and prev_version != cur_version
            if not (status_changed or version_changed):
                continue

            platform = info.get("platform", "N/A")
            updated  = info.get("updated_at", info.get("last_updated", "N/A"))
            dl_link  = info.get("download", info.get("download_link", info.get("link", None)))
            is_online = cur_status.lower() == "online"
            color = 0x57F287 if is_online else (0xED4245 if cur_status.lower() == "patched" else 0xFEE75C)

            embed = discord.Embed(
                title=f"🎉 Actualización en {real_name}",
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            if status_changed:
                embed.add_field(name="🔄 Cambio de estado",   value=f"`{prev_status}` → `{cur_status}`",   inline=False)
            if version_changed:
                embed.add_field(name="📦 Cambio de versión",  value=f"`{prev_version}` → `{cur_version}`", inline=False)
            embed.add_field(name="Estado actual",  value=f"{status_emoji(cur_status)} {cur_status}", inline=True)
            embed.add_field(name="Versión actual", value=cur_version, inline=True)
            embed.add_field(name="Plataforma",     value=platform,    inline=True)
            embed.add_field(name="Última actualización", value=str(updated), inline=False)
            if dl_link:
                embed.add_field(name="🔗 Descarga", value=f"[Descargar aquí]({dl_link})", inline=False)
            embed.set_thumbnail(url=EMOJI_GREEN_DOT if is_online else EMOJI_GREEN_ARROW)
            embed.set_footer(text="Datos de api.weao.xyz")

            mention = ""
            if role_id:
                role = guild.get_role(int(role_id))
                mention = role.mention if role else ""
            if not mention:
                mention = "@everyone"

            try:
                await channel.send(content=mention, embed=embed)
            except discord.Forbidden:
                print(f"[ALERT] Sin permisos en #{channel.name} ({guild.name})")
            except Exception as e:
                print(f"[ALERT] Error: {e}")

    if changed:
        save_json(STATE_FILE, previous)


@check_exploits.before_loop
async def before_check():
    await client.wait_until_ready()
    await asyncio.sleep(10)


# ─────────────────────────────────────────────
# EVENTOS
# ─────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"[BOT] Conectado como {client.user} (ID: {client.user.id})")
    try:
        synced = await tree.sync()
        print(f"[BOT] {len(synced)} comandos slash sincronizados.")
    except Exception as e:
        print(f"[BOT] Error sync: {e}")
    check_exploits.start()
    print(f"[BOT] Verificación automática cada {CHECK_INTERVAL}s | Health en puerto {PORT}")


# ─────────────────────────────────────────────
# WEB SERVER — Requerido para Render Web Service
# ─────────────────────────────────────────────

async def health(_request):
    return web.Response(text="OK", status=200)


async def start_web_server():
    app = web.Application()
    app.router.add_get("/",       health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[WEB] Health server corriendo en puerto {PORT}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("Falta la variable de entorno DISCORD_TOKEN.")
    await start_web_server()
    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
