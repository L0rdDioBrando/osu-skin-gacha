const OSU = "https://osu.ppy.sh";

const HEADERS = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};

const encoder = new TextEncoder();

function randomHex() {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), (n) =>
    n.toString(16).padStart(2, "0"),
  ).join("");
}

async function sha256(value) {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", encoder.encode(value)),
    ),
    (n) => n.toString(16).padStart(2, "0"),
  ).join("");
}

function validHex64(value) {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

const ADMIN_OSU_IDS = new Set([18086030]);

const wait = (ms) =>
  new Promise((resolve) =>
    setTimeout(resolve, Math.max(0, ms)),
  );

const isAdminUser = (user) =>
  Boolean(
    user &&
      ADMIN_OSU_IDS.has(Number(user.id)),
  );

function sharedStub(env) {
  return env.GACHA_AUTH.get(
    env.GACHA_AUTH.idFromName(
      "skillpush-shared-v1",
    ),
  );
}

async function authenticatedUser(
  request,
  env,
) {
  const token = (
    request.headers.get(
      "Authorization",
    ) || ""
  ).replace(/^Bearer /, "");

  const id =
    token.split(".")[0];

  if (
    !validHex64(id) ||
    !env.GACHA_AUTH
  ) {
    return null;
  }

  const stub =
    env.GACHA_AUTH.get(
      env.GACHA_AUTH.idFromName(
        id,
      ),
    );

  const response =
    await stub.fetch(
      new Request(
        (
          env.PUBLIC_ORIGIN ||
          "https://skillpush.invalid"
        ) + "/session",
        {
          method: "GET",
          headers: {
            Authorization:
              "Bearer " +
              token,
          },
        },
      ),
    );

  if (!response.ok) {
    return null;
  }

  const data =
    await response
      .json()
      .catch(() => ({}));

  return data.user || null;
}

function json(
  data,
  status = 200,
  extraHeaders = {},
) {
  return new Response(
    JSON.stringify(data),
    {
      status,
      headers: {
        ...HEADERS,
        "Content-Type":
          "application/json; charset=utf-8",
        ...extraHeaders,
      },
    },
  );
}

function error(
  status,
  code,
  extra = {},
) {
  return json(
    {
      error: code,
      ...extra,
    },
    status,
  );
}

function safeMessage(err) {
  const text =
    String(
      err?.message ||
        err ||
        "unknown_error",
    );

  return text
    .replace(
      /[\r\n]+/g,
      " ",
    )
    .slice(0, 240);
}

function callbackPage(
  message,
  ok = false,
  targetOrigin = "*",
  errorCode = "",
  appName = "SkillPush",
) {
  const payload =
    JSON.stringify({
      type:
        "skillpush-oauth",
      ok,
      success: ok,
      error:
        errorCode || "",
    });

  const safeTargetOrigin =
    JSON.stringify(
      targetOrigin || "*",
    );

  return new Response(
    `<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${appName}</title>

<style>
  :root {
    color-scheme: dark;
  }

  body {
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: #091426;
    color: #eef4ff;
    font: 16px system-ui, sans-serif;
  }

  main {
    width: min(560px, calc(100% - 40px));
    padding: 28px;
    border: 1px solid #263a5d;
    border-radius: 18px;
    background: #101f38;
    box-shadow: 0 24px 80px #0008;
  }

  h1 {
    margin: 0 0 10px;
    color: #ff4fa7;
  }

  p {
    margin: 0;
    line-height: 1.6;
    color: #b9c8e4;
  }
</style>

<main>
  <h1>${appName}</h1>
  <p>${String(
    message,
  ).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  )}</p>
</main>

<script>
  try {
    if (window.opener) {
      window.opener.postMessage(
        ${payload},
        ${safeTargetOrigin}
      );
    }
  } catch (_) {}

  ${
    ok
      ? `
  setTimeout(() => {
    try {
      window.close();
    } catch (_) {}
  }, 900);
  `
      : ""
  }
</script>`,
    {
      headers: {
        ...HEADERS,
        "Content-Type":
          "text/html; charset=utf-8",
        "Content-Security-Policy":
          "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'",
      },
    },
  );
}

// Keep the website callback message/protocol unchanged; desktop gets its own wording.
function loginPage(login, message, ok = false, targetOrigin = "*", errorCode = "") {
  if (login.webOrigin) return callbackPage(message, ok, targetOrigin, errorCode);
  return callbackPage(ok
    ? "Вход выполнен! Вернитесь в osu!gacha. / Signed in! Return to osu!gacha."
    : "Вход не завершён. Вернитесь в osu!gacha и повторите попытку. / Return to osu!gacha and retry.",
    ok, targetOrigin, errorCode, "osu!gacha");
}

async function readBody(
  request,
) {
  if (
    Number(
      request.headers.get(
        "content-length",
      ) || 0,
    ) > 4096
  ) {
    throw new Error(
      "body_too_large",
    );
  }

  const raw =
    await request.text();

  if (
    raw.length > 4096
  ) {
    throw new Error(
      "body_too_large",
    );
  }

  return JSON.parse(raw);
}

async function readJSON(
  request,
  maxBytes = 262144,
) {
  if (
    Number(
      request.headers.get(
        "content-length",
      ) || 0,
    ) > maxBytes
  ) {
    throw new Error(
      "body_too_large",
    );
  }

  const raw =
    await request.text();

  if (
    raw.length > maxBytes
  ) {
    throw new Error(
      "body_too_large",
    );
  }

  return raw
    ? JSON.parse(raw)
    : {};
}

function browserCookie(
  request,
) {
  return (
    /(?:^|;\s*)__Host-skillpush-login=([a-f0-9]{64})(?:;|$)/.exec(
      request.headers.get(
        "cookie",
      ) || "",
    )?.[1] || ""
  );
}

function publicUser(
  user,
) {
  return {
    id: user.id,

    username:
      user.username,

    avatar_url:
      user.avatar_url,

    pp:
      user.statistics?.pp ||
      0,

    global_rank:
      user.statistics
        ?.global_rank ||
      null,

    country_rank:
      user.statistics
        ?.country_rank ||
      null,

    accuracy:
      user.statistics
        ?.hit_accuracy ||
      0,

    play_count:
      user.statistics
        ?.play_count ||
      0,
  };
}

function allowedAPI(
  path,
  method,
  user,
) {
  if (
    method === "GET" &&
    (
      path ===
        `users/${user}/osu` ||
      path ===
        `users/${user}/scores/best` ||
      path ===
        `users/${user}/scores/recent`
    )
  ) {
    return true;
  }

  if (
    method === "GET" &&
    /^beatmaps\/[1-9]\d*$/.test(
      path,
    )
  ) {
    return true;
  }

  if (
    method === "GET" &&
    /^beatmaps\/[1-9]\d*\/scores$/.test(
      path,
    )
  ) {
    return true;
  }

  if (
    method === "GET" &&
    new RegExp(
      `^beatmaps/[1-9]\\d*/scores/users/${user}/all$`,
    ).test(path)
  ) {
    return true;
  }

  if (
    method === "GET" &&
    /^beatmapsets\/[1-9]\d*\/download$/.test(
      path,
    )
  ) {
    return true;
  }

  return (
    method === "POST" &&
    /^beatmaps\/[1-9]\d*\/attributes$/.test(
      path,
    )
  );
}

function allowedOrigins(
  env,
) {
  const defaults = [
    "https://skillpush.therealdimedrol.workers.dev",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
  ];

  const configured =
    String(
      env.WEB_ORIGINS ||
        "",
    )
      .split(",")
      .map((x) =>
        x
          .trim()
          .replace(
            /\/$/,
            "",
          ),
      )
      .filter(Boolean);

  return [
    ...new Set([
      ...defaults,
      ...configured,
    ]),
  ];
}

function corsHeaders(
  request,
  env,
) {
  const origin =
    (
      request.headers.get(
        "Origin",
      ) || ""
    ).replace(
      /\/$/,
      "",
    );

  if (
    !origin ||
    !allowedOrigins(
      env,
    ).includes(origin)
  ) {
    return {};
  }

  return {
    "Access-Control-Allow-Origin":
      origin,

    "Access-Control-Allow-Methods":
      "GET, POST, OPTIONS",

    "Access-Control-Allow-Headers":
      "Content-Type, Authorization",

    "Access-Control-Max-Age":
      "86400",

    Vary: "Origin",
  };
}

function withCors(
  response,
  request,
  env,
) {
  const headers =
    new Headers(
      response.headers,
    );

  for (
    const [
      key,
      value,
    ] of Object.entries(
      corsHeaders(
        request,
        env,
      ),
    )
  ) {
    headers.set(
      key,
      value,
    );
  }

  return new Response(
    response.body,
    {
      status:
        response.status,

      statusText:
        response.statusText,

      headers,
    },
  );
}

async function readErrorText(
  response,
) {
  try {
    const text =
      await response.text();

    return text
      .replace(
        /[\r\n]+/g,
        " ",
      )
      .slice(
        0,
        300,
      );
  } catch {
    return "";
  }
}

function normalizeActivityPlay(
  raw,
) {
  if (
    !raw ||
    typeof raw !== "object"
  ) {
    return null;
  }

  const beatmapId =
    String(
      raw.beatmapId || "",
    ).trim();

  const key =
    String(
      raw.key ||
        raw.scoreId ||
        "",
    ).trim();

  if (
    !beatmapId ||
    !key
  ) {
    return null;
  }

  const minutes =
    Math.max(
      0,
      Math.min(
        120,
        Number(
          raw.minutes,
        ) || 0,
      ),
    );

  return {
    key:
      key.slice(
        0,
        180,
      ),

    scoreId:
      String(
        raw.scoreId || "",
      ).slice(
        0,
        64,
      ),

    beatmapId:
      beatmapId.slice(
        0,
        32,
      ),

    beatmapsetId:
      String(
        raw.beatmapsetId ||
          "",
      ).slice(
        0,
        32,
      ),

    mapId:
      String(
        raw.mapId || "",
      ).slice(
        0,
        120,
      ),

    skill:
      String(
        raw.skill || "",
      ).slice(
        0,
        40,
      ),

    title:
      String(
        raw.title || "",
      ).slice(
        0,
        220,
      ),

    artist:
      String(
        raw.artist || "",
      ).slice(
        0,
        180,
      ),

    creator:
      String(
        raw.creator || "",
      ).slice(
        0,
        120,
      ),

    version:
      String(
        raw.version || "",
      ).slice(
        0,
        180,
      ),

    stars:
      Number(
        raw.stars || 0,
      ),

    status:
      String(
        raw.status || "",
      ).slice(
        0,
        32,
      ),

    cover:
      String(
        raw.cover || "",
      ).slice(
        0,
        800,
      ),

    playedAt:
      String(
        raw.playedAt ||
          "",
      ).slice(
        0,
        80,
      ),

    minutes,

    passed:
      raw.passed !== false,

    rank:
      String(
        raw.rank || "",
      ).slice(
        0,
        12,
      ),

    accuracy:
      Number(
        raw.accuracy ||
          0,
      ),
  };
}

export class GachaAuth {
  constructor(
    ctx,
    env,
  ) {
    this.ctx = ctx;
    this.env = env;
    this.cache =
      new Map();
    this.lastAPI = 0;
    this.pending = Promise.resolve();
  }

  async fetch(
    request,
  ) {
    try {
      return await this.serial(request);
    } catch (err) {
      const path =
        (() => {
          try {
            return new URL(
              request.url,
            ).pathname;
          } catch {
            return "unknown";
          }
        })();

      const detail =
        safeMessage(err);

      console.error(
        "SkillPush Durable Object error",
        {
          path,
          detail,
          stack:
            err?.stack,
        },
      );

      if (
        path ===
        "/oauth/callback"
      ) {
        try {
          const login =
            await this.ctx.storage.get(
              "login",
            );

          if (login) {
            login.failure = {
              code:
                "callback_exception",

              detail,

              at:
                Date.now(),
            };

            await this.ctx.storage.put(
              "login",
              login,
            );
          }
        } catch (_) {}
      }

      return error(
        500,
        "auth_callback_exception",
        {
          detail,
        },
      );
    }
  }

  // Serialize token refresh/callback writes without Durable Object's 30s block limit.
  serial(request) {
    const task = this.pending.then(() => this.handle(request));
    this.pending = task.catch(() => {});
    return task;
  }

  async alarm() {
    await this.ctx.storage.deleteAll();
  }

  async osu(
    path,
    options = {},
  ) {
    return fetch(
      OSU + path,
      options,
    );
  }

  async setFailure(
    login,
    code,
    detail = "",
  ) {
    login.failure = {
      code,

      detail:
        String(
          detail || "",
        ).slice(
          0,
          300,
        ),

      at:
        Date.now(),
    };

    await this.ctx.storage.put(
      "login",
      login,
    );
  }

  async handle(
    request,
  ) {
    const url =
      new URL(
        request.url,
      );

    const path =
      url.pathname;

    const store =
      this.ctx.storage;

    const now =
      Date.now();

    if (
      path ===
        "/internal/start" &&
      request.method ===
        "POST"
    ) {
      const {
        id,
        challenge,
        webOrigin = "",
      } =
        await readBody(
          request,
        );

      if (
        !validHex64(id) ||
        !validHex64(
          challenge,
        )
      ) {
        return error(
          400,
          "invalid_start_payload",
        );
      }

      await store.put(
        "login",
        {
          id,
          challenge,

          webOrigin:
            String(
              webOrigin ||
                "",
            ),

          expires:
            now +
            10 *
              60 *
              1000,
        },
      );

      await store.setAlarm(
        now +
          10 *
            60 *
            1000,
      );

      return json({
        id,

        login_url:
          this.env
            .PUBLIC_ORIGIN +
          "/login?desktop=" +
          id,

        expires_in:
          600,

        interval:
          3,
      });
    }

    if (
      path ===
        "/shared/maps" &&
      request.method ===
        "GET"
    ) {
      const index =
        (await store.get(
          "map_index",
        )) || [];

      const maps = [];

      for (
        const key of index
      ) {
        const value =
          await store.get(
            "map:" + key,
          );

        if (value) {
          maps.push(
            value,
          );
        }
      }

      return json({
        maps,
      });
    }

    if (
      path ===
        "/shared/maps/upsert" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readJSON(
          request,
        );

      const incoming =
        Array.isArray(
          data.maps,
        )
          ? data.maps.slice(
              0,
              100,
            )
          : [];

      const index =
        (await store.get(
          "map_index",
        )) || [];

      const seen =
        new Set(
          index.map(String),
        );

      let changed = 0;

      for (
        const raw of incoming
      ) {
        if (
          !raw ||
          typeof raw !==
            "object"
        ) {
          continue;
        }

        const key =
          String(
            raw.beatmapId ||
              raw.id ||
              "",
          ).trim();

        if (!key) {
          continue;
        }

        const map = {
          ...raw,

          id:
            raw.id ||
            "map-" + key,

          beatmapId:
            raw.beatmapId
              ? String(
                  raw.beatmapId,
                )
              : "",

          updatedAt:
            Date.now(),
        };

        await store.put(
          "map:" + key,
          map,
        );

        if (
          !seen.has(key)
        ) {
          index.push(key);
          seen.add(key);
        }

        changed++;
      }

      await store.put(
        "map_index",
        index,
      );

      return json({
        ok: true,
        changed,
      });
    }

    if (
      path ===
        "/shared/maps/delete" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readJSON(
          request,
        );

      const target =
        String(
          data.beatmapId ||
            data.id ||
            "",
        ).trim();

      const index =
        (await store.get(
          "map_index",
        )) || [];

      let key =
        target;

      if (
        target &&
        !index.includes(
          target,
        )
      ) {
        for (
          const candidate of
            index
        ) {
          const value =
            await store.get(
              "map:" +
                candidate,
            );

          if (
            value &&
            String(
              value.id,
            ) === target
          ) {
            key =
              candidate;

            break;
          }
        }
      }

      await store.delete(
        "map:" + key,
      );

      await store.put(
        "map_index",
        index.filter(
          (x) =>
            String(x) !==
            String(key),
        ),
      );

      return json({
        ok: true,
      });
    }

    if (
      path ===
        "/shared/maps/clear" &&
      request.method ===
        "POST"
    ) {
      const index =
        (await store.get(
          "map_index",
        )) || [];

      for (
        const key of index
      ) {
        await store.delete(
          "map:" + key,
        );
      }

      await store.put(
        "map_index",
        [],
      );

      return json({
        ok: true,
      });
    }

    if (
      path ===
        "/shared/users" &&
      request.method ===
        "GET"
    ) {
      const index =
        (await store.get(
          "user_index",
        )) || [];

      const users = [];

      for (
        const key of index
      ) {
        const value =
          await store.get(
            "user:" + key,
          );

        if (value) {
          users.push(
            value,
          );
        }
      }

      users.sort(
        (a, b) =>
          Number(
            b.last_seen ||
              0,
          ) -
          Number(
            a.last_seen ||
              0,
          ),
      );

      return json({
        users,
      });
    }

    if (
      path ===
        "/shared/users/touch" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readJSON(
          request,
        );

      const user =
        data.user &&
        typeof data.user ===
          "object"
          ? data.user
          : null;

      if (
        !user ||
        user.id == null
      ) {
        return error(
          400,
          "invalid_user",
        );
      }

      const key =
        String(user.id);

      const previous =
        (await store.get(
          "user:" + key,
        )) || {};

      const record = {
        ...previous,

        id:
          user.id,

        username:
          user.username ||
          previous.username ||
          "osu! " + key,

        avatar_url:
          user.avatar_url ||
          previous.avatar_url ||
          "",

        pp:
          Number(
            user.pp ||
              previous.pp ||
              0,
          ),

        source:
          "osu",

        role:
          isAdminUser(user)
            ? "admin"
            : previous.role ||
              "user",

        blocked:
          Boolean(
            previous.blocked,
          ),

        first_seen:
          previous.first_seen ||
          Date.now(),

        last_seen:
          Date.now(),
      };

      await store.put(
        "user:" + key,
        record,
      );

      const index =
        (await store.get(
          "user_index",
        )) || [];

      if (
        !index
          .map(String)
          .includes(key)
      ) {
        index.push(key);

        await store.put(
          "user_index",
          index,
        );
      }

      return json({
        user: record,
      });
    }

    const activityMatch =
      /^\/shared\/users\/activity\/([^/]+)$/.exec(
        path,
      );

    if (
      activityMatch &&
      request.method ===
        "GET"
    ) {
      const key =
        decodeURIComponent(
          activityMatch[1],
        );

      const record =
        (await store.get(
          "user:" + key,
        )) || null;

      if (!record) {
        return error(
          404,
          "user_not_found",
        );
      }

      return json({
        tracked_plays:
          Number(
            record.tracked_plays ||
              0,
          ),

        tracked_minutes:
          Number(
            record.tracked_minutes ||
              0,
          ),

        recent_plays:
          Array.isArray(
            record.recent_plays,
          )
            ? record.recent_plays.slice(
                0,
                60,
              )
            : [],
      });
    }

    if (
      activityMatch &&
      request.method ===
        "POST"
    ) {
      const key =
        decodeURIComponent(
          activityMatch[1],
        );

      const data =
        await readJSON(
          request,
          262144,
        );

      const incoming =
        (
          Array.isArray(
            data.plays,
          )
            ? data.plays
            : []
        )
          .slice(
            0,
            160,
          )
          .map(
            normalizeActivityPlay,
          )
          .filter(Boolean);

      const record =
        (await store.get(
          "user:" + key,
        )) || {
          id: key,

          username:
            "osu! " + key,

          avatar_url:
            "",

          source:
            "osu",

          role:
            ADMIN_OSU_IDS.has(
              Number(key),
            )
              ? "admin"
              : "user",

          blocked:
            false,

          first_seen:
            Date.now(),

          last_seen:
            Date.now(),
        };

      const known =
        new Set(
          Array.isArray(
            record.tracked_play_keys,
          )
            ? record.tracked_play_keys.map(
                String,
              )
            : [],
        );

      const recentMap =
        new Map(
          (
            Array.isArray(
              record.recent_plays,
            )
              ? record.recent_plays
              : []
          ).map(
            (p) => [
              String(
                p.key,
              ),
              p,
            ],
          ),
        );

      let added = 0;
      let minutesAdded = 0;

      for (
        const play of incoming
      ) {
        recentMap.set(
          String(
            play.key,
          ),
          play,
        );

        if (
          known.has(
            String(
              play.key,
            ),
          )
        ) {
          continue;
        }

        known.add(
          String(
            play.key,
          ),
        );

        added++;

        minutesAdded +=
          Number(
            play.minutes ||
              0,
          );
      }

      const recent =
        [
          ...recentMap.values(),
        ]
          .sort(
            (a, b) =>
              String(
                b.playedAt ||
                  "",
              ).localeCompare(
                String(
                  a.playedAt ||
                    "",
                ),
              ),
          )
          .slice(
            0,
            60,
          );

      record.tracked_plays =
        Number(
          record.tracked_plays ||
            0,
        ) + added;

      record.tracked_minutes =
        Number(
          record.tracked_minutes ||
            0,
        ) +
        minutesAdded;

      record.tracked_play_keys =
        [...known].slice(
          -800,
        );

      record.recent_plays =
        recent;

      record.last_activity_sync =
        Date.now();

      record.last_seen =
        Date.now();

      await store.put(
        "user:" + key,
        record,
      );

      const index =
        (await store.get(
          "user_index",
        )) || [];

      if (
        !index
          .map(String)
          .includes(
            String(key),
          )
      ) {
        index.push(
          String(key),
        );

        await store.put(
          "user_index",
          index,
        );
      }

      return json({
        ok: true,

        added,

        tracked_plays:
          record.tracked_plays,

        tracked_minutes:
          record.tracked_minutes,

        recent_plays:
          recent,
      });
    }

    if (
      path ===
        "/shared/users/block" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readJSON(
          request,
        );

      const key =
        String(
          data.id || "",
        );

      const record =
        await store.get(
          "user:" + key,
        );

      if (!record) {
        return error(
          404,
          "user_not_found",
        );
      }

      record.blocked =
        Boolean(
          data.blocked,
        );

      await store.put(
        "user:" + key,
        record,
      );

      return json({
        user: record,
      });
    }

    if (
      path ===
        "/shared/skills" &&
      request.method ===
        "GET"
    ) {
      return json({
        skills:
          (await store.get(
            "skills",
          )) || [],
      });
    }

    if (
      path ===
        "/shared/skills" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readJSON(
          request,
        );

      const skills =
        Array.isArray(
          data.skills,
        )
          ? data.skills.slice(
              0,
              32,
            )
          : [];

      await store.put(
        "skills",
        skills,
      );

      return json({
        ok: true,
        skills,
      });
    }

    let login =
      await store.get(
        "login",
      );

    if (!login) {
      return error(
        401,
        "session_expired",
      );
    }

    if (
      path === "/login" &&
      request.method ===
        "GET"
    ) {
      if (
        login.expires <
          now ||
        login.active ||
        login.tokens
      ) {
        return error(
          410,
          "login_expired",
        );
      }

      const cookie =
        randomHex();

      const state =
        login.id +
        "." +
        randomHex();

      login.state =
        await sha256(
          state,
        );

      login.browser =
        await sha256(
          cookie,
        );

      delete login.failure;

      await store.put(
        "login",
        login,
      );

      const target =
        new URL(
          OSU +
            "/oauth/authorize",
        );

      target.search =
        new URLSearchParams(
          {
            client_id:
              String(
                this.env
                  .OSU_CLIENT_ID,
              ),

            redirect_uri:
              this.env
                .PUBLIC_ORIGIN +
              "/oauth/callback",

            response_type:
              "code",

            scope:
              "public identify",

            state,
          },
        );

      return new Response(
        null,
        {
          status: 302,

          headers: {
            ...HEADERS,

            Location:
              target.href,

            "Set-Cookie":
              `__Host-skillpush-login=${cookie}; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=600`,
          },
        },
      );
    }

    if (
      path ===
        "/oauth/callback" &&
      request.method ===
        "GET"
    ) {
      const incomingState =
        url.searchParams.get(
          "state",
        ) || "";

      const cookie =
        browserCookie(
          request,
        );

      if (
        login.expires <
          now ||
        !login.state ||
        !cookie ||
        (
          await sha256(
            incomingState,
          )
        ) !==
          login.state ||
        (
          await sha256(
            cookie,
          )
        ) !==
          login.browser
      ) {

        return error(
          400,
          "invalid_state",
        );
      }

      if (
        url.searchParams.get(
          "error",
        )
      ) {
        await this.setFailure(
          login,
          "login_denied",
          url.searchParams.get(
            "error_description",
          ) ||
            "Access denied",
        );

        return loginPage(login,
          "Вход отменён. Можно закрыть это окно и вернуться в SkillPush.",
          false,
          login.webOrigin ||
            "*",
          "login_denied",
        );
      }

      const code =
        url.searchParams.get(
          "code",
        );

      if (!code) {
        await this.setFailure(
          login,
          "missing_code",
          "OAuth callback did not contain code",
        );

        return error(
          400,
          "missing_code",
        );
      }

      let tokenResponse;

      try {
        const tokenBody =
          new URLSearchParams(
            {
              client_id:
                String(
                  this.env
                    .OSU_CLIENT_ID,
                ),

              client_secret:
                String(
                  this.env
                    .OSU_CLIENT_SECRET ||
                    "",
                ),

              grant_type:
                "authorization_code",

              code,

              redirect_uri:
                this.env
                  .PUBLIC_ORIGIN +
                "/oauth/callback",
            },
          );

        tokenResponse =
          await this.osu(
            "/oauth/token",
            {
              method:
                "POST",

              headers: {
                Accept:
                  "application/json",

                "Content-Type":
                  "application/x-www-form-urlencoded",
              },

              body:
                tokenBody.toString(),
            },
          );
      } catch (err) {
        const detail =
          safeMessage(
            err,
          );

        await this.setFailure(
          login,
          "osu_token_request_exception",
          detail,
        );

        return error(
          502,
          "osu_token_request_exception",
          {
            detail,
          },
        );
      }

      if (
        !tokenResponse.ok
      ) {
        const detail =
          await readErrorText(
            tokenResponse,
          );

        await this.setFailure(
          login,
          "osu_token_exchange_failed",
          `HTTP ${tokenResponse.status}: ${detail}`,
        );

        return error(
          502,
          "osu_token_exchange_failed",
          {
            upstream_status:
              tokenResponse.status,

            detail,
          },
        );
      }

      let tokens;

      try {
        tokens =
          await tokenResponse.json();
      } catch (err) {
        const detail =
          safeMessage(
            err,
          );

        await this.setFailure(
          login,
          "invalid_osu_token_response",
          detail,
        );

        return error(
          502,
          "invalid_osu_token_response",
          {
            detail,
          },
        );
      }

      if (
        !tokens.access_token
      ) {
        await this.setFailure(
          login,
          "invalid_osu_token_response",
          "Missing access_token",
        );

        return error(
          502,
          "invalid_osu_token_response",
        );
      }

      let profileResponse;

      try {
        profileResponse =
          await this.osu(
            "/api/v2/me/osu",
            {
              headers: {
                Authorization:
                  "Bearer " +
                  tokens.access_token,

                Accept:
                  "application/json",
              },
            },
          );
      } catch (err) {
        const detail =
          safeMessage(
            err,
          );

        await this.setFailure(
          login,
          "osu_profile_request_exception",
          detail,
        );

        return error(
          502,
          "osu_profile_request_exception",
          {
            detail,
          },
        );
      }

      if (
        !profileResponse.ok
      ) {
        const detail =
          await readErrorText(
            profileResponse,
          );

        await this.setFailure(
          login,
          "osu_profile_failed",
          `HTTP ${profileResponse.status}: ${detail}`,
        );

        return error(
          502,
          "osu_profile_failed",
          {
            upstream_status:
              profileResponse.status,

            detail,
          },
        );
      }

      let profile;

      try {
        profile =
          await profileResponse.json();
      } catch (err) {
        const detail =
          safeMessage(
            err,
          );

        await this.setFailure(
          login,
          "invalid_osu_profile_response",
          detail,
        );

        return error(
          502,
          "invalid_osu_profile_response",
          {
            detail,
          },
        );
      }

      login.user =
        publicUser(
          profile,
        );

      login.tokens = {
        access_token:
          tokens.access_token,

        refresh_token:
          tokens.refresh_token ||
          null,

        expires:
          now +
          Number(
            tokens.expires_in ||
              86400,
          ) *
            1000,
      };

      delete login.state;
      delete login.browser;
      delete login.failure;

      await store.put(
        "login",
        login,
      );

      const result =
        loginPage(login,
          "Вход выполнен. Окно закроется автоматически, а SkillPush продолжит вход.",
          true,
          login.webOrigin ||
            "*",
        );

      result.headers.set(
        "Set-Cookie",
        "__Host-skillpush-login=; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=0",
      );

      return result;
    }

    if (
      path ===
        "/desktop/poll" &&
      request.method ===
        "POST"
    ) {
      const data =
        await readBody(
          request,
        );

      if (
        !validHex64(
          data.verifier,
        ) ||
        (
          await sha256(
            data.verifier,
          )
        ) !==
          login.challenge
      ) {
        return error(
          401,
          "invalid_proof",
        );
      }

      if (
        login.expires <
        now
      ) {
        return error(
          410,
          "login_expired",
        );
      }

      if (
        login.failure
      ) {
        return error(
          502,
          login.failure.code ||
            "oauth_failed",
          {
            detail:
              login.failure
                .detail ||
              "",
          },
        );
      }

      if (
        !login.tokens
      ) {
        return json(
          {
            status:
              "pending",
          },
          202,
        );
      }

      if (
        !login.active
      ) {
        login.active =
          true;

        login.created =
          now;

        login.sessionExpires =
          now +
          30 *
            864e5;

        await store.put(
          "login",
          login,
        );

        await store.setAlarm(
          login.sessionExpires,
        );
      }

      return json({
        status:
          "complete",

        session:
          login.id +
          "." +
          data.verifier,

        user:
          login.user,

        expires_at:
          login.sessionExpires /
          1000,
      });
    }

    const token =
      (
        request.headers.get(
          "Authorization",
        ) || ""
      ).replace(
        /^Bearer /,
        "",
      );

    const parts =
      token.split(".");

    if (
      parts.length !== 2 ||
      parts[0] !==
        login.id ||
      !validHex64(
        parts[1],
      ) ||
      !login.active ||
      (
        await sha256(
          parts[1],
        )
      ) !==
        login.challenge ||
      now >
        login.sessionExpires
    ) {
      return error(
        401,
        "session_expired",
      );
    }

    if (
      path === "/logout" &&
      request.method ===
        "POST"
    ) {
      await store.deleteAll();

      this.cache.clear();

      return json({
        ok: true,
      });
    }

    if (
      now >
      login.created +
        90 *
          864e5
    ) {
      return error(
        401,
        "session_expired",
      );
    }

    if (
      login.sessionExpires -
        now <
      7 *
        864e5
    ) {
      login.sessionExpires =
        Math.min(
          now +
            30 *
              864e5,

          login.created +
            90 *
              864e5,
        );

      await store.put(
        "login",
        login,
      );

      await store.setAlarm(
        login.sessionExpires,
      );
    }

    if (
      path ===
        "/session" &&
      request.method ===
        "GET"
    ) {
      return json({
        user:
          login.user,

        expires_at:
          login.sessionExpires /
          1000,
      });
    }

    const apiPath =
      path.slice(
        "/api/v2/".length,
      );

    if (
      !path.startsWith(
        "/api/v2/",
      ) ||
      !allowedAPI(
        apiPath,
        request.method,
        String(
          login.user.id,
        ),
      )
    ) {
      return error(
        403,
        "endpoint_not_allowed",
      );
    }

    const isBeatmapDownload =
      request.method ===
        "GET" &&
      /^beatmapsets\/[1-9]\d*\/download$/.test(
        apiPath,
      );

    const params =
      new URLSearchParams();

    let payload;

    if (
      request.method ===
      "POST"
    ) {
      const data =
        await readBody(
          request,
        );

      if (
        !Number.isInteger(
          data.mods,
        ) ||
        data.mods < 0 ||
        data.mods >
          2147483647
      ) {
        return error(
          400,
          "invalid_mods",
        );
      }

      payload =
        JSON.stringify({
          mods:
            data.mods,

          ruleset:
            "osu",
        });
    } else if (
      apiPath.includes(
        "/scores",
      )
    ) {
      params.set(
        apiPath.endsWith(
          "/all",
        )
          ? "ruleset"
          : "mode",

        "osu",
      );

      params.set(
        "legacy_only",
        "1",
      );

      if (
        !apiPath.endsWith(
          "/all",
        )
      ) {
        params.set(
          "limit",
          String(
            Math.min(
              100,
              Math.max(
                1,
                Number(
                  url.searchParams.get(
                    "limit",
                  ),
                ) ||
                  100,
              ),
            ),
          ),
        );
      }

      if (
        apiPath.endsWith(
          "/recent",
        )
      ) {
        params.set(
          "include_fails",
          "1",
        );
      }
    }

    const key =
      apiPath +
      "?" +
      params +
      "|" +
      (payload || "");

    const cached =
      isBeatmapDownload
        ? null
        : this.cache.get(
            key,
          );

    if (
      cached &&
      cached.expires >
        now
    ) {
      return json(
        cached.data,
      );
    }

    const elapsed =
      Date.now() -
      this.lastAPI;

    if (
      elapsed < 1200
    ) {
      await wait(
        1200 -
          elapsed,
      );
    }

    this.lastAPI =
      Date.now();

    let response;

    for (
      let attempt = 0;
      attempt < 2;
      attempt++
    ) {
      if (
        login.tokens.expires <
          Date.now() +
            60_000 ||
        attempt
      ) {
        const refreshBody =
          new URLSearchParams(
            {
              client_id:
                String(
                  this.env
                    .OSU_CLIENT_ID,
                ),

              client_secret:
                String(
                  this.env
                    .OSU_CLIENT_SECRET ||
                    "",
                ),

              grant_type:
                "refresh_token",

              refresh_token:
                login.tokens
                  .refresh_token,

              scope:
                "public identify",
            },
          );

        let refreshed;

        try {
          refreshed =
            await this.osu(
              "/oauth/token",
              {
                method:
                  "POST",

                headers: {
                  Accept:
                    "application/json",

                  "Content-Type":
                    "application/x-www-form-urlencoded",
                },

                body:
                  refreshBody.toString(),
              },
            );
        } catch (err) {
          return error(
            503,
            "refresh_request_exception",
            {
              detail:
                safeMessage(
                  err,
                ),
            },
          );
        }

        if (
          !refreshed.ok
        ) {
          if (
            refreshed.status ===
              400 ||
            refreshed.status ===
              401
          ) {
            await store.deleteAll();

            return error(
              401,
              "session_expired",
            );
          }

          return error(
            503,
            "refresh_unavailable",
            {
              upstream_status:
                refreshed.status,
            },
          );
        }

        const newTokens =
          await refreshed.json();

        if (
          !newTokens.access_token
        ) {
          return error(
            502,
            "invalid_osu_response",
          );
        }

        login.tokens = {
          access_token:
            newTokens.access_token,

          refresh_token:
            newTokens.refresh_token ||
            login.tokens
              .refresh_token,

          expires:
            Date.now() +
            Number(
              newTokens.expires_in ||
                86400,
            ) *
              1000,
        };

        await store.put(
          "login",
          login,
        );
      }

      response =
        await this.osu(
          "/api/v2/" +
            apiPath +
            (
              params.size
                ? "?" +
                  params
                : ""
            ),
          {
            method:
              request.method,

            headers: {
              Authorization:
                "Bearer " +
                login.tokens
                  .access_token,

              Accept:
                isBeatmapDownload
                  ? "application/octet-stream"
                  : "application/json",

              ...(
                isBeatmapDownload
                  ? {}
                  : {
                      "Content-Type":
                        "application/json",

                      "x-api-version":
                        "20220705",
                    }
              ),
            },

            ...(
              payload
                ? {
                    body:
                      payload,
                  }
                : {}
            ),
          },
        );

      if (
        response.status !==
        401
      ) {
        break;
      }
    }

    if (!response.ok) {
      const detail =
        await readErrorText(
          response,
        );

      return error(
        response.status,
        "osu_api_error",
        {
          detail,
        },
      );
    }

    if (
      isBeatmapDownload
    ) {
      const beatmapsetId =
        apiPath.split(
          "/",
        )[1];

      const headers =
        new Headers(
          HEADERS,
        );

      headers.set(
        "Content-Type",
        response.headers.get(
          "Content-Type",
        ) ||
          "application/octet-stream",
      );

      headers.set(
        "Content-Disposition",
        response.headers.get(
          "Content-Disposition",
        ) ||
          `attachment; filename="${beatmapsetId}.osz"`,
      );

      const length =
        response.headers.get(
          "Content-Length",
        );

      if (length) {
        headers.set(
          "Content-Length",
          length,
        );
      }

      headers.set(
        "Cache-Control",
        "no-store",
      );

      return new Response(
        response.body,
        {
          status: 200,
          headers,
        },
      );
    }

    const data =
      await response.json();

    if (
      this.cache.size >
      128
    ) {
      this.cache.clear();
    }

    this.cache.set(
      key,
      {
        expires:
          Date.now() +
          (
            apiPath.includes(
              "scores",
            ) ||
            apiPath.startsWith(
              "users/",
            )
              ? 61e3
              : 36e5
          ),

        data,
      },
    );

    return json(data);
  }
}

const worker = {
  async fetch(
    request,
    env,
  ) {
    const originalRequest =
      request;

    try {
      if (
        request.method ===
        "OPTIONS"
      ) {
        const cors =
          corsHeaders(
            request,
            env,
          );

        if (
          !cors[
            "Access-Control-Allow-Origin"
          ]
        ) {
          return new Response(
            null,
            {
              status:
                403,

              headers:
                HEADERS,
            },
          );
        }

        return new Response(
          null,
          {
            status:
              204,

            headers: {
              ...HEADERS,
              ...cors,
            },
          },
        );
      }

      const respond =
        (response) =>
          withCors(
            response,
            originalRequest,
            env,
          );

      const url =
        new URL(
          request.url,
        );

      const path =
        url.pathname;

      if (
        request.method ===
          "GET" &&
        (
          path === "/" ||
          path ===
            "/health"
        )
      ) {
        return respond(
          json({
            service:
              "SkillPush + osu!gacha Auth",

            ok:
              true,

            client_id_configured:
              Boolean(
                env.OSU_CLIENT_ID,
              ),

            client_secret_configured:
              Boolean(
                env.OSU_CLIENT_SECRET,
              ),

            public_origin:
              env.PUBLIC_ORIGIN ||
              null,

            web_origins:
              allowedOrigins(
                env,
              ),

            oauth_scopes: [
              "public",
              "identify",
              "lazer",
            ],

            direct_beatmap_download:
              true,
          }),
        );
      }

      if (
        path.startsWith(
          "/app/",
        )
      ) {
        if (
          !env.GACHA_AUTH
        ) {
          return respond(
            error(
              500,
              "durable_object_binding_missing",
            ),
          );
        }

        const store =
          sharedStub(env);

        if (
          request.method ===
            "GET" &&
          path ===
            "/app/maps"
        ) {
          return respond(
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/maps",
                {
                  method:
                    "GET",
                },
              ),
            ),
          );
        }

        if (
          request.method ===
            "GET" &&
          path ===
            "/app/skills"
        ) {
          return respond(
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/skills",
                {
                  method:
                    "GET",
                },
              ),
            ),
          );
        }

        const user =
          await authenticatedUser(
            request,
            env,
          );

        if (!user) {
          return respond(
            error(
              401,
              "session_expired",
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/me/touch"
        ) {
          const r =
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/users/touch",
                {
                  method:
                    "POST",

                  headers: {
                    "Content-Type":
                      "application/json",
                  },

                  body:
                    JSON.stringify(
                      {
                        user,
                      },
                    ),
                },
              ),
            );

          const data =
            await r
              .clone()
              .json()
              .catch(
                () => ({}),
              );

          if (
            data?.user
              ?.blocked
          ) {
            return respond(
              error(
                403,
                "account_blocked",
              ),
            );
          }

          return respond(r);
        }

        if (
          request.method ===
            "GET" &&
          path ===
            "/app/me/activity"
        ) {
          return respond(
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/users/activity/" +
                  encodeURIComponent(
                    String(
                      user.id,
                    ),
                  ),
                {
                  method:
                    "GET",
                },
              ),
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/me/activity"
        ) {
          const body =
            await request.text();

          return respond(
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/users/activity/" +
                  encodeURIComponent(
                    String(
                      user.id,
                    ),
                  ),
                {
                  method:
                    "POST",

                  headers: {
                    "Content-Type":
                      "application/json",
                  },

                  body,
                },
              ),
            ),
          );
        }

        if (
          !isAdminUser(
            user,
          )
        ) {
          return respond(
            error(
              403,
              "admin_required",
            ),
          );
        }

        const forwardJSON =
          async (
            sharedPath,
          ) => {
            const body =
              await request.text();

            return store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  sharedPath,
                {
                  method:
                    request.method,

                  headers: {
                    "Content-Type":
                      "application/json",
                  },

                  body:
                    request.method ===
                    "GET"
                      ? undefined
                      : body,
                },
              ),
            );
          };

        if (
          request.method ===
            "GET" &&
          path ===
            "/app/users"
        ) {
          return respond(
            await store.fetch(
              new Request(
                env.PUBLIC_ORIGIN +
                  "/shared/users",
                {
                  method:
                    "GET",
                },
              ),
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/users/block"
        ) {
          return respond(
            await forwardJSON(
              "/shared/users/block",
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/maps/upsert"
        ) {
          return respond(
            await forwardJSON(
              "/shared/maps/upsert",
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/maps/delete"
        ) {
          return respond(
            await forwardJSON(
              "/shared/maps/delete",
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/maps/clear"
        ) {
          return respond(
            await forwardJSON(
              "/shared/maps/clear",
            ),
          );
        }

        if (
          request.method ===
            "POST" &&
          path ===
            "/app/skills"
        ) {
          return respond(
            await forwardJSON(
              "/shared/skills",
            ),
          );
        }

        return respond(
          error(
            404,
            "not_found",
          ),
        );
      }

      if (
        request.method ===
          "POST" &&
        path ===
          "/desktop/start"
      ) {
        const data =
          await readBody(
            request,
          );

        if (
          !validHex64(
            data.challenge,
          )
        ) {
          return respond(
            error(
              400,
              "invalid_challenge",
            ),
          );
        }

        if (
          !env.GACHA_AUTH
        ) {
          return respond(
            error(
              500,
              "durable_object_binding_missing",
            ),
          );
        }

        const webOrigin =
          (
            request.headers.get(
              "Origin",
            ) || ""
          ).replace(
            /\/$/,
            "",
          );

        if (
          webOrigin &&
          !allowedOrigins(
            env,
          ).includes(
            webOrigin,
          )
        ) {
          return respond(
            error(
              403,
              "origin_not_allowed",
            ),
          );
        }

        const id =
          randomHex();

        const stub =
          env.GACHA_AUTH.get(
            env.GACHA_AUTH.idFromName(
              id,
            ),
          );

        const response =
          await stub.fetch(
            new Request(
              env.PUBLIC_ORIGIN +
                "/internal/start",
              {
                method:
                  "POST",

                headers: {
                  "Content-Type":
                    "application/json",
                },

                body:
                  JSON.stringify(
                    {
                      id,

                      challenge:
                        data.challenge,

                      webOrigin,
                    },
                  ),
              },
            ),
          );

        return respond(
          response,
        );
      }

      let id;

      if (
        path === "/login"
      ) {
        id =
          url.searchParams.get(
            "desktop",
          );
      } else if (
        path ===
        "/oauth/callback"
      ) {
        id =
          (
            url.searchParams.get(
              "state",
            ) || ""
          ).split(".")[0];
      } else if (
        path ===
        "/desktop/poll"
      ) {
        const data =
          await readBody(
            request,
          );

        id =
          data.id;

        request =
          new Request(
            request.url,
            {
              method:
                request.method,

              headers:
                request.headers,

              body:
                JSON.stringify(
                  data,
                ),
            },
          );
      } else if (
        path ===
          "/session" ||
        path ===
          "/logout" ||
        path.startsWith(
          "/api/v2/",
        )
      ) {
        id =
          (
            request.headers.get(
              "Authorization",
            ) || ""
          )
            .replace(
              /^Bearer /,
              "",
            )
            .split(".")[0];
      } else {
        return respond(
          error(
            404,
            "not_found",
          ),
        );
      }

      if (
        !validHex64(
          id,
        )
      ) {
        return respond(
          path ===
            "/login"
            ? callbackPage(
                "Авторизация не была начата из SkillPush. Вернись на сайт и снова нажми «Войти через osu!».",
                false,
              )
            : error(
                400,
                "invalid_login",
              ),
        );
      }

      const response =
        await env.GACHA_AUTH
          .get(
            env.GACHA_AUTH.idFromName(
              id,
            ),
          )
          .fetch(
            request,
          );

      if (
        path ===
          "/desktop/poll" &&
        response.ok &&
        response.status ===
          200
      ) {
        try {
          const payload =
            await response
              .clone()
              .json();

          if (
            payload?.status ===
              "complete" &&
            payload?.user
          ) {
            const touch =
              await sharedStub(
                env,
              ).fetch(
                new Request(
                  env.PUBLIC_ORIGIN +
                    "/shared/users/touch",
                  {
                    method:
                      "POST",

                    headers: {
                      "Content-Type":
                        "application/json",
                    },

                    body:
                      JSON.stringify(
                        {
                          user:
                            payload.user,
                        },
                      ),
                  },
                ),
              );

            const touched =
              await touch
                .json()
                .catch(
                  () => ({}),
                );

            if (
              touched?.user
                ?.blocked
            ) {
              return respond(
                error(
                  403,
                  "account_blocked",
                ),
              );
            }
          }
        } catch (err) {
          console.warn(
            "SkillPush user registry touch failed",
            safeMessage(
              err,
            ),
          );
        }
      }

      return respond(
        response,
      );
    } catch (err) {
      const detail =
        safeMessage(
          err,
        );

      console.error(
        "SkillPush Worker error",
        {
          detail,

          stack:
            err?.stack,
        },
      );

      return withCors(
        error(
          500,
          "worker_exception",
          {
            detail,
          },
        ),

        originalRequest,
        env,
      );
    }
  },
};

export default worker;

// Оставляем то же имя класса,
// на которое уже указывает binding GACHA_AUTH.
export {
  allowedAPI,
  sha256 as hash,
  randomHex as random,
};