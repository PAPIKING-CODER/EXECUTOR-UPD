import { Router } from "express";
import { exchangeCode, fetchDiscordUser, getRedirectUri, isOwner } from "../lib/discord";

const router = Router();

declare module "express-session" {
  interface SessionData {
    userId: string;
    username: string;
    discriminator: string;
    avatar: string | null;
    isOwner: boolean;
  }
}

router.get("/auth/me", (req, res): void => {
  const s = req.session;
  if (!s.userId) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  res.json({
    id: s.userId,
    username: s.username,
    discriminator: s.discriminator,
    avatar: s.avatar ?? null,
    isOwner: s.isOwner,
  });
});

router.get("/auth/discord", (req, res): void => {
  const clientId = process.env["DISCORD_CLIENT_ID"];
  if (!clientId) {
    res.status(503).json({ error: "Discord OAuth2 not configured. Set DISCORD_CLIENT_ID." });
    return;
  }
  const redirectUri = getRedirectUri(req);
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "identify",
  });
  res.redirect(`https://discord.com/api/oauth2/authorize?${params.toString()}`);
});

router.get("/auth/discord/callback", async (req, res): Promise<void> => {
  const code = typeof req.query["code"] === "string" ? req.query["code"] : null;
  if (!code) {
    res.redirect("/?error=no_code");
    return;
  }
  try {
    const redirectUri = getRedirectUri(req);
    const tokens = await exchangeCode(code, redirectUri);
    const user = await fetchDiscordUser(tokens.access_token);
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.discriminator = user.discriminator;
    req.session.avatar = user.avatar;
    req.session.isOwner = isOwner(user.id);
    req.log.info({ userId: user.id }, "User logged in via Discord");
    res.redirect("/dashboard");
  } catch (err) {
    req.log.error({ err }, "Discord OAuth2 callback error");
    res.redirect("/?error=auth_failed");
  }
});

router.post("/auth/logout", (req, res): void => {
  req.session.destroy((err) => {
    if (err) req.log.error({ err }, "Session destroy error");
    res.json({ success: true, message: "Logged out" });
  });
});

export default router;
