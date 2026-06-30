import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadCronStore, resolveCronStorePath } from "/app/dist/plugin-sdk/cron-store-runtime.js";

const storePath = resolveCronStorePath(process.argv[2]);
const outputPath = process.argv[3] || "/home/node/.openclaw/cron/jobs.editable.json";

const store = await loadCronStore(storePath);
await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });

console.log(`Exported ${store.jobs.length} cron job(s) to ${outputPath}`);
