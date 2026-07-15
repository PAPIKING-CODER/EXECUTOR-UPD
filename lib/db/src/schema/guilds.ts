import { pgTable, text, integer, timestamp, jsonb } from "drizzle-orm/pg-core";

export const guildsTable = pgTable("guilds", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  icon: text("icon"),
  ownerId: text("owner_id").notNull().default(""),
  memberCount: integer("member_count").notNull().default(0),
  joinedAt: timestamp("joined_at"),
  permissions: text("permissions").notNull().default("0"),
  features: jsonb("features").$type<string[]>().notNull().default([]),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export type Guild = typeof guildsTable.$inferSelect;
