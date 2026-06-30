import { copyFile, mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { saveCronStore, resolveCronStorePath } from "/app/dist/plugin-sdk/cron-store-runtime.js";

const inputPath = process.argv[2] || "/home/node/.openclaw/cron/jobs.editable.json";
const storePath = resolveCronStorePath(process.argv[3]);
const dbPath = "/home/node/.openclaw/state/openclaw.sqlite";
const backupDir = "/home/node/.openclaw/cron/backups";

function assertStoreShape(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Cron file must be a JSON object.");
  }
  if (value.version !== 1) {
    throw new Error("Cron file must have version: 1.");
  }
  if (!Array.isArray(value.jobs)) {
    throw new Error("Cron file must have a jobs array.");
  }
  const seen = new Set();
  for (const [index, job] of value.jobs.entries()) {
    if (!job || typeof job !== "object" || Array.isArray(job)) {
      throw new Error(`Job at index ${index} must be an object.`);
    }
    if (typeof job.id !== "string" || job.id.trim() === "") {
      throw new Error(`Job at index ${index} must have a non-empty string id.`);
    }
    if (seen.has(job.id)) {
      throw new Error(`Duplicate job id: ${job.id}`);
    }
    seen.add(job.id);
  }
}

async function backupDatabase() {
  try {
    await stat(dbPath);
  } catch {
    return null;
  }
  await mkdir(backupDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const backupPath = path.join(backupDir, `openclaw.sqlite.before-cron-edit-${stamp}.bak`);
  await copyFile(dbPath, backupPath);
  return backupPath;
}

const raw = await readFile(inputPath, "utf8");
const store = JSON.parse(raw);
assertStoreShape(store);

const backupPath = await backupDatabase();
await saveCronStore(storePath, store);

console.log(`Applied ${store.jobs.length} cron job(s) from ${inputPath}`);
console.log(`Store key: ${storePath}`);
if (backupPath) console.log(`Backup: ${backupPath}`);
