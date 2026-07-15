const DISCORD_API = "https://discord.com/api/v10";

export function getBotToken(): string | undefined {
  return process.env["DISCORD_BOT_TOKEN"];
}

export async function discordBotFetch(path: string) {
  const token = getBotToken();
  if (!token) throw new Error("DISCORD_BOT_TOKEN not configured");
  const res = await fetch(`${DISCORD_API}${path}`, {
    headers: { Authorization: `Bot ${token}` },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Discord API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function exchangeCode(code: string, redirectUri: string) {
  const clientId = process.env["DISCORD_CLIENT_ID"] ?? "";
  const clientSecret = process.env["DISCORD_CLIENT_SECRET"] ?? "";
  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
  });
  const res = await fetch(`${DISCORD_API}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Discord token exchange error ${res.status}: ${text}`);
  }
  return res.json() as Promise<{ access_token: string; token_type: string }>;
}

export async function fetchDiscordUser(accessToken: string) {
  const res = await fetch(`${DISCORD_API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("Failed to fetch Discord user");
  return res.json() as Promise<{
    id: string;
    username: string;
    discriminator: string;
    avatar: string | null;
  }>;
}

export function getOwnerIds(): string[] {
  const raw = process.env["OWNER_IDS"] ?? "";
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function isOwner(userId: string): boolean {
  const owners = getOwnerIds();
  if (owners.length === 0) return true; // if not configured, allow all authenticated users
  return owners.includes(userId);
}

export function getRedirectUri(req: { protocol: string; hostname: string }): string {
  if (process.env["DISCORD_REDIRECT_URI"]) return process.env["DISCORD_REDIRECT_URI"];
  const devDomain = process.env["REPLIT_DEV_DOMAIN"];
  if (devDomain) return `https://${devDomain}/api/auth/discord/callback`;
  return `${req.protocol}://${req.hostname}/api/auth/discord/callback`;
}
