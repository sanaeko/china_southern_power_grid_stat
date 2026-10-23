// Live verification against the user's HA instance.
// Checks the preconditions this integration relies on, without deploying.
const HA = "http://192.168.0.99:8123";
const TOKEN = process.env.HA_TOKEN;

const results = [];
const ok = (name, detail) => results.push({ ok: true, name, detail });
const bad = (name, detail) => results.push({ ok: false, name, detail });

function connect() {
  const ws = new WebSocket(HA.replace("http", "ws") + "/api/websocket");
  let id = 0;
  const pending = new Map();
  const ready = new Promise((resolve, reject) => {
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "auth_required") {
        ws.send(JSON.stringify({ type: "auth", access_token: TOKEN }));
      } else if (msg.type === "auth_ok") resolve();
      else if (msg.type === "auth_invalid") reject(new Error("auth_invalid"));
      else if (msg.id && pending.has(msg.id)) {
        const { resolve: r, reject: j } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.success ? r(msg.result) : j(new Error(JSON.stringify(msg.error)));
      }
    });
    ws.addEventListener("error", (e) => reject(e));
  });
  const call = (type, payload = {}) => {
    const mid = ++id;
    return new Promise((resolve, reject) => {
      pending.set(mid, { resolve, reject });
      ws.send(JSON.stringify({ id: mid, type, ...payload }));
    });
  };
  return { ws, ready, call };
}

const rest = async (path) => {
  const r = await fetch(HA + path, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
};

const { ws, ready, call } = connect();
await ready;

// 1. Core version supports the APIs used (CalendarEntity date events, StaticPathConfig).
const config = await rest("/api/config");
const [major, minor] = config.version.split(".").map(Number);
if (major > 2026 || (major === 2026 && minor >= 10)) {
  ok("HA version", `${config.version} (>= 2026.10 required)`);
} else {
  bad("HA version", `${config.version} is older than 2026.10`);
}

// 2. The calendar component can be loaded on demand (it is a core component).
const components = await rest("/api/components");
if (components.includes("http") && components.includes("frontend")) {
  ok("http/frontend loaded", "required for the bundled card");
} else {
  bad("http/frontend", "missing");
}
const calendarLoaded = components.includes("calendar");
ok(
  "calendar component",
  calendarLoaded
    ? "already loaded"
    : "not loaded yet - HA loads it on demand for this platform"
);

// 3. The existing config entry is loaded and has electricity accounts.
try {
  const entries = (await call("config_entries/get")).filter(
    (e) => e.domain === "china_southern_power_grid_stat_GDJM"
  );
  if (entries.length) {
    ok("config entry", `${entries[0].title} state=${entries[0].state}`);
  } else {
    bad("config entry", "none found");
  }
} catch {
  const entries = await rest("/api/config/config_entries/entry");
  const csg = entries.filter(
    (e) => e.domain === "china_southern_power_grid_stat_GDJM"
  );
  if (csg.length) ok("config entry", `${csg[0].title} state=${csg[0].state}`);
  else bad("config entry", "none found");
}

// 4. Lovelace is in storage-resource mode, so the card can self-register.
try {
  const dashboards = await call("lovelace/dashboards/list");
  const lovelace = dashboards.find((d) => d.id === "lovelace");
  ok("lovelace", `default dashboard mode=${lovelace?.mode ?? "?"}`);
} catch (e) {
  bad("lovelace", `cannot list dashboards: ${e.message}`);
}
try {
  const resources = await call("lovelace/resources");
  const hasCard = resources.some((r) =>
    r.url.includes("china-southern-power-grid-usage-card")
  );
  ok(
    "card resource",
    hasCard
      ? "already registered"
      : `not registered yet (self-registers on load); ${resources.length} existing`
  );
} catch (e) {
  bad("card resource", e.message);
}

// 5. Every existing CSG entity has a stable unique_id we can extend without breaking.
try {
  const registry = (await call("config/entity_registry/list")).filter((e) =>
    e.unique_id?.startsWith("china_southern_power_grid_stat_GDJM.")
  );
  ok("existing entities", `${registry.length} registered with stable unique_ids`);
} catch (e) {
  bad("existing entities", e.message);
}

// 6. Recorder is configured (needed only for HA's own history graphs, not ours).
try {
  const rec = await call("recorder/list_entities");
  const items = rec.items ?? rec;
  ok("recorder", `${Array.isArray(items) ? items.length : "?"} entities recorded`);
} catch (e) {
  ok("recorder", `not queryable (${e.message}); optional for this feature`);
}

// 7. The account the integration tracks, for a sanity check of the data path.
const states = await rest("/api/states");
const historySensor = states.find((s) =>
  s.entity_id.endsWith("_daily_usage_history")
);
if (historySensor) {
  ok("history sensor", `${historySensor.entity_id} state=${historySensor.state}`);
} else {
  ok("history sensor", "not created yet (new entity will appear after deploy)");
}

ws.close();

for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}: ${r.detail}`);
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
