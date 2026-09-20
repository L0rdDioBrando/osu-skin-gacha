# Shared SkillPush + osu!gacha Worker

This source was synchronized with the live Worker and the supplied SkillPush v13.1 implementation on 2026-09-20. All /app/* routes, CORS, web callback postMessage and GACHA_AUTH storage are retained. Desktop login has an app-specific callback message. Session operations are serialized to avoid parallel refresh/callback overwrites.

Server-only configuration: OSU_CLIENT_ID, OSU_CLIENT_SECRET, PUBLIC_ORIGIN, WEB_ORIGINS. Existing values are preserved by `wrangler deploy --keep-vars`. Never put secret values in this directory, client source or archives. The actual deployed Client ID is 68443, retained from the working server.

Tests: `node --test test/worker.test.mjs`.
Deploy: `wrangler deploy --keep-vars`.
Do not remove or migrate away the GACHA_AUTH binding: it also stores SkillPush data.

The pre-change server source is retained locally in `.server-backup/2026-09-20-live.js`. The SkillPush website archive was only inspected and was not modified.
