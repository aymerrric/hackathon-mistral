#!/usr/bin/env node
/**
 * CallTree launcher — OS-agnostic (Windows / macOS / Linux), no dependencies.
 *
 *   npm run setup   first-time setup only (env files + installs)
 *   npm run dev     setup if needed, then DB + backend + frontend together
 *
 * Ctrl-C stops backend + frontend; the DB container keeps running
 * (`npm run db:down` stops it, `npm run db:reset` wipes it).
 */

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WIN = process.platform === "win32";
const SETUP_ONLY = process.argv.includes("--setup-only");

const c = (code, s) => `\x1b[${code}m${s}\x1b[0m`;
const log = (s) => console.log(c(36, "[dev] ") + s);
const die = (s) => {
  console.error(c(31, "[dev] ERROR: ") + s);
  process.exit(1);
};

// Run a command to completion, inheriting output. shell:true so npm/poetry
// (.cmd shims on Windows) resolve everywhere.
function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: true, cwd: ROOT, ...opts });
  return r.status === 0;
}

function has(cmd) {
  return spawnSync(cmd, ["--version"], { stdio: "ignore", shell: true }).status === 0;
}

// --- 1. Prerequisites -------------------------------------------------------

for (const cmd of ["docker", "poetry", "npm"]) {
  if (!has(cmd)) die(`'${cmd}' is not installed or not on PATH.`);
}

// --- 2. Env files -----------------------------------------------------------

const backendEnv = path.join(ROOT, "backend", ".env");
if (!existsSync(backendEnv)) {
  copyFileSync(path.join(ROOT, "backend", ".env.example"), backendEnv);
  log("Created backend/.env from the example.");
}
if (/MISTRAL_API_KEY=your-key-here|MISTRAL_API_KEY=\s*$/m.test(readFileSync(backendEnv, "utf8"))) {
  log(c(33, "WARNING: set MISTRAL_API_KEY in backend/.env — AI endpoints will fail without it."));
}
const frontendEnv = path.join(ROOT, "frontend", ".env.local");
if (!existsSync(frontendEnv)) {
  copyFileSync(path.join(ROOT, "frontend", ".env.example"), frontendEnv);
  log("Created frontend/.env.local from the example.");
}

// --- 3. Installs (skipped when already done) --------------------------------

if (!existsSync(path.join(ROOT, "frontend", "node_modules"))) {
  log("Installing frontend dependencies...");
  if (!run("npm", ["install"], { cwd: path.join(ROOT, "frontend") })) die("npm install failed.");
}
log("Syncing backend dependencies (poetry install)...");
if (!run("poetry", ["install", "--quiet"], { cwd: path.join(ROOT, "backend") }))
  die("poetry install failed.");

if (SETUP_ONLY) {
  log(c(32, "Setup complete. Start everything with: npm run dev"));
  process.exit(0);
}

// --- 4. Database ------------------------------------------------------------

log("Starting PostgreSQL...");
if (!run("docker", ["compose", "up", "-d", "db"])) die("docker compose failed — is Docker running?");

process.stdout.write(c(36, "[dev] ") + "Waiting for PostgreSQL to be ready");
for (let i = 0; ; i++) {
  const ready =
    spawnSync("docker", ["compose", "exec", "-T", "db", "pg_isready", "-U", "calltree", "-q"], {
      stdio: "ignore",
      shell: true,
      cwd: ROOT,
    }).status === 0;
  if (ready) break;
  if (i > 60) die("PostgreSQL did not become ready within 60s.");
  process.stdout.write(".");
  await new Promise((r) => setTimeout(r, 1000));
}
console.log(" ok");

// --- 5. Backend + frontend --------------------------------------------------

const children = [];
let shuttingDown = false;

function killTree(child) {
  if (WIN) {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM"); // negative pid = whole process group
    } catch {
      try { child.kill("SIGTERM"); } catch { /* already gone */ }
    }
  }
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  log("Shutting down...");
  for (const child of children) killTree(child);
  log("Done. (DB still running — 'npm run db:down' to stop it.)");
  process.exit(code);
}

// Spawn a service, prefixing each output line with a colored tag.
function service(tag, color, cmd, args, cwd) {
  const child = spawn(cmd, args, {
    cwd,
    shell: true,
    detached: !WIN, // own process group on POSIX so killTree(-pid) gets children
    stdio: ["ignore", "pipe", "pipe"],
  });
  const prefix = c(color, `[${tag}] `);
  for (const stream of [child.stdout, child.stderr]) {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) console.log(prefix + line);
    });
  }
  child.on("exit", (code) => {
    if (!shuttingDown) {
      log(c(31, `${tag} exited (code ${code}) — stopping everything.`));
      shutdown(code ?? 1);
    }
  });
  children.push(child);
}

service("api", 34, "poetry", ["run", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
  path.join(ROOT, "backend"));
service("web", 32, "npm", ["run", "dev"], path.join(ROOT, "frontend"));

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

console.log(`
${c(1, "  CallTree is starting:")}
    Frontend  http://localhost:3000
    API       http://localhost:8000  (docs at /docs)
    Postgres  localhost:5432

  Ctrl-C to stop.
`);
