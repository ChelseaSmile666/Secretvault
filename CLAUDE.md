# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is "Claude Code UI" (CloudCLI) — a full-stack web UI for Claude Code CLI, Cursor CLI, and OpenAI Codex, published as `@siteboon/claude-code-ui`.

The `integrations/` directory contains independent sub-projects (ComfyUI, obsidian plugins, MCP servers) with their own tooling and are not part of the main build.

## Development Commands

```bash
npm install           # Install dependencies
cp .env.example .env  # First-time setup

npm run dev           # Start frontend (Vite, port 5173) + backend (Express, port 3001) concurrently
npm run server        # Backend only
npm run client        # Frontend only (Vite dev server)
npm run build         # Production build (outputs to dist/)
npm run typecheck     # TypeScript type checking (no emit)
npm run start         # Build then start production server
npm run release       # Interactive release (bumps version, updates CHANGELOG, tags, publishes to npm)
```

In dev mode, Vite proxies `/api`, `/ws`, and `/shell` to the Express backend on `PORT` (default 3001). The frontend runs on `VITE_PORT` (default 5173).

## Architecture

### Frontend (`src/`)
React 18 + Vite + Tailwind CSS, served from Express in production (from `dist/`) or via Vite proxy in dev.

- `src/App.tsx` — Root with provider stack: i18n → Theme → Auth → WebSocket → TasksSettings → TaskMaster → Router
- `src/components/app/AppContent.tsx` — Main layout shell
- `src/components/chat/` — Chat interface (view, hooks, utils, tools, types, constants)
- `src/components/sidebar/` — Project/session sidebar (view, hooks, utils, types)
- `src/components/code-editor/` — CodeMirror-based file editor
- `src/components/git-panel/` — Git explorer (stage, commit, branch switching)
- `src/components/shell/` — Embedded terminal (xterm.js + node-pty)
- `src/contexts/` — AuthContext, ThemeContext, WebSocketContext, TaskMasterContext, TasksSettingsContext
- `src/hooks/` — useProjectsState, useDeviceSettings, useUiPreferences, useVersionCheck, useSessionProtection
- `src/i18n/` — i18next configuration and translation files

### Backend (`server/`)
Node.js ESM + Express + `ws` WebSocket server. Entry point: `server/index.js`.

- `server/claude-sdk.js` — `@anthropic-ai/claude-agent-sdk` integration (spawn/abort/query sessions)
- `server/cursor-cli.js` — Cursor CLI process management
- `server/openai-codex.js` — OpenAI Codex SDK integration
- `server/projects.js` — Discovery of Claude/Cursor/Codex sessions from `~/.claude/projects/`, `~/.cursor/chats/`, `~/.codex/sessions/`
- `server/routes/` — Express routers: `auth`, `git`, `mcp`, `mcp-utils`, `projects`, `settings`, `taskmaster`, `cursor`, `codex`, `agent`, `commands`, `user`, `cli-auth`
- `server/middleware/auth.js` — JWT + API key authentication middleware
- `server/database/db.js` — SQLite (better-sqlite3) with schema in `database/init.sql`; database path defaults to `server/database/auth.db` or `DATABASE_PATH` env var

### WebSocket Protocol
The server multiplexes chat streaming, project-list refresh, and shell (PTY) over three WebSocket paths: `/ws` (chat + events), `/shell` (PTY terminal via node-pty).

### Shared (`shared/`)
Code consumed by both frontend and server (included in `tsconfig.json`).

## Environment Variables

Key variables from `.env.example`:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `3001` | Express/WebSocket port |
| `VITE_PORT` | `5173` | Vite dev server port |
| `HOST` | `0.0.0.0` | Bind address |
| `DATABASE_PATH` | `server/database/auth.db` | SQLite database location |
| `CONTEXT_WINDOW` / `VITE_CONTEXT_WINDOW` | `160000` | Max tokens per session |
| `CLAUDE_CLI_PATH` | `claude` | Override Claude CLI binary path |

## Commit Convention

Follow [Conventional Commits](https://conventionalcommits.org/): `<type>(scope): <description>` in present tense.

Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `style`, `chore`, `ci`, `test`, `build`. Breaking changes: append `!` (e.g. `feat!: redesign settings`).
