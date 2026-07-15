import { Router } from "express";
import { requireAuth } from "../middlewares/auth";
import { db } from "@workspace/db";
import { guildsTable } from "@workspace/db";
import { eq, like, desc } from "drizzle-orm";
import { ListGuildsQueryParams, GetGuildParams, LeaveGuildParams } from "@workspace/api-zod";

const router = Router();

const SEED_GUILDS = [
  { id: "123456789012345678", name: "FMD Gaming Community", icon: null, ownerId: "111111111111111111", memberCount: 4521, joinedAt: new Date("2024-01-15"), permissions: "8", features: ["COMMUNITY"] },
  { id: "234567890123456789", name: "Anime Central", icon: null, ownerId: "222222222222222222", memberCount: 12043, joinedAt: new Date("2024-02-20"), permissions: "8", features: ["COMMUNITY", "NEWS"] },
  { id: "345678901234567890", name: "Tech Talk", icon: null, ownerId: "333333333333333333", memberCount: 2891, joinedAt: new Date("2024-03-10"), permissions: "8", features: [] },
  { id: "456789012345678901", name: "Music Lounge", icon: null, ownerId: "444444444444444444", memberCount: 7654, joinedAt: new Date("2024-04-05"), permissions: "8", features: [] },
  { id: "567890123456789012", name: "Gaming Hub", icon: null, ownerId: "555555555555555555", memberCount: 3210, joinedAt: new Date("2024-05-18"), permissions: "8", features: ["COMMUNITY"] },
];

async function ensureSeeded() {
  const count = await db.$count(guildsTable);
  if (count === 0) {
    await db.insert(guildsTable).values(SEED_GUILDS).onConflictDoNothing();
  }
}

router.get("/guilds", requireAuth, async (req, res): Promise<void> => {
  const parsed = ListGuildsQueryParams.safeParse(req.query);
  const params = parsed.success ? parsed.data : { page: 1, limit: 20 };
  const page = params.page ?? 1;
  const limit = params.limit ?? 20;
  const search = params.search;

  await ensureSeeded();

  const allGuilds = await db.select().from(guildsTable).orderBy(desc(guildsTable.memberCount));
  const filtered = search
    ? allGuilds.filter((g) => g.name.toLowerCase().includes(search.toLowerCase()))
    : allGuilds;

  const total = filtered.length;
  const offset = (page - 1) * limit;
  const guilds = filtered.slice(offset, offset + limit).map((g) => ({
    id: g.id,
    name: g.name,
    icon: g.icon,
    ownerId: g.ownerId,
    memberCount: g.memberCount,
    joinedAt: g.joinedAt?.toISOString() ?? null,
    permissions: g.permissions,
    features: g.features ?? [],
  }));

  res.json({ guilds, total, page, limit });
});

router.get("/guilds/:guildId", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params["guildId"]) ? req.params["guildId"][0] : req.params["guildId"];
  const parsed = GetGuildParams.safeParse({ guildId: raw });
  if (!parsed.success) { res.status(400).json({ error: "Invalid guild ID" }); return; }

  await ensureSeeded();
  const [guild] = await db.select().from(guildsTable).where(eq(guildsTable.id, parsed.data.guildId));
  if (!guild) { res.status(404).json({ error: "Guild not found" }); return; }

  res.json({
    id: guild.id,
    name: guild.name,
    icon: guild.icon,
    ownerId: guild.ownerId,
    memberCount: guild.memberCount,
    joinedAt: guild.joinedAt?.toISOString() ?? null,
    permissions: guild.permissions,
    features: guild.features ?? [],
  });
});

router.delete("/guilds/:guildId", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params["guildId"]) ? req.params["guildId"][0] : req.params["guildId"];
  const parsed = LeaveGuildParams.safeParse({ guildId: raw });
  if (!parsed.success) { res.status(400).json({ error: "Invalid guild ID" }); return; }

  await db.delete(guildsTable).where(eq(guildsTable.id, parsed.data.guildId));
  req.log.info({ guildId: parsed.data.guildId }, "Left guild");
  res.json({ success: true, message: "Left guild successfully" });
});

export default router;
