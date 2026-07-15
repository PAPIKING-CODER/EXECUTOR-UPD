# FMD BOT OWNER PANEL

Panel de control privado para el bot de Discord FMD BOT. Permite al owner monitorear, moderar y controlar el bot desde una interfaz web premium con tema oscuro y acentos verde neón.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — API server (port 8080)
- `pnpm --filter @workspace/dashboard run dev` — Frontend panel (port assigned by workflow)
- `pnpm run typecheck` — typecheck completo
- `pnpm --filter @workspace/api-spec run codegen` — regenerar hooks y schemas del OpenAPI
- `pnpm --filter @workspace/db run push` — aplicar cambios de schema a la DB

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React + Vite, Tailwind CSS, Framer Motion, Recharts, Wouter
- API: Express 5 + express-session
- DB: PostgreSQL + Drizzle ORM
- Auth: Discord OAuth2 (sessions)
- Codegen: Orval (OpenAPI → React Query hooks + Zod schemas)

## Where things live

- `artifacts/dashboard/` — Frontend (React + Vite)
- `artifacts/api-server/` — Backend Express API
- `lib/api-spec/openapi.yaml` — Contrato OpenAPI (fuente de verdad)
- `lib/db/src/schema/` — Schema de DB (blacklist, logs, commands, bot-settings, guilds)

## Required Secrets

- `DISCORD_BOT_TOKEN` — Token del bot (para stats reales de Discord)
- `DISCORD_CLIENT_ID` — Client ID de la app de Discord (para OAuth2)
- `DISCORD_CLIENT_SECRET` — Client Secret de la app de Discord (para OAuth2)
- `SESSION_SECRET` — Ya configurado
- `OWNER_IDS` — IDs de Discord separados por coma (ej: `123456,789012`) que tienen acceso al panel. Si está vacío, cualquier usuario autenticado puede entrar.

## Discord OAuth2 Setup

1. Ve a https://discord.com/developers/applications
2. Selecciona tu app → OAuth2
3. Agrega como Redirect URI: `https://TU-DOMINIO/api/auth/discord/callback`
4. Configura `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`

## Bot Integration

El bot Python puede enviar logs al panel via:
```
POST /api/logs
Content-Type: application/json
{"type": "command", "message": "...", "guildId": "...", "userId": "..."}
```

## Pages

- `/` — Login con Discord OAuth2
- `/dashboard` — Stats del bot en tiempo real
- `/servers` — Gestión de servidores
- `/blacklist` — Blacklist de usuarios/servidores/palabras
- `/logs` — Logs de actividad con filtros
- `/commands` — Gestión de comandos
- `/stats` — Estadísticas y gráficas
- `/settings` — Controles del bot

## User preferences

- Proyecto: FMD BOT OWNER PANEL, creado por KING
- Bot en Python alojado en https://github.com/PAPIKING-CODER/EXECUTOR-UPD
