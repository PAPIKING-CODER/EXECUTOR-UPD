import { pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const blacklistEntriesTable = pgTable("blacklist_entries", {
  id: serial("id").primaryKey(),
  type: text("type").notNull(), // user | server | word
  targetId: text("target_id").notNull(),
  targetName: text("target_name"),
  reason: text("reason"),
  addedBy: text("added_by").notNull().default("owner"),
  addedAt: timestamp("added_at").defaultNow().notNull(),
});

export const insertBlacklistSchema = createInsertSchema(blacklistEntriesTable).omit({ id: true, addedAt: true });
export type InsertBlacklist = z.infer<typeof insertBlacklistSchema>;
export type BlacklistEntry = typeof blacklistEntriesTable.$inferSelect;
