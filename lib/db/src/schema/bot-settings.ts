import { pgTable, serial, text, boolean, jsonb, timestamp } from "drizzle-orm/pg-core";

export const botSettingsTable = pgTable("bot_settings", {
  id: serial("id").primaryKey(),
  maintenanceMode: boolean("maintenance_mode").notNull().default(false),
  statusText: text("status_text").notNull().default("FMD BOT | /help"),
  statusType: text("status_type").notNull().default("playing"),
  disabledCommands: jsonb("disabled_commands").$type<string[]>().notNull().default([]),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export type BotSettings = typeof botSettingsTable.$inferSelect;
