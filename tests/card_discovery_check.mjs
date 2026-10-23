// Unit tests for the card's entity discovery.
//
// The card is a plain browser script, so this harness stubs the few globals it
// touches at load time, captures the custom element it registers, and exercises
// `_findEntities` against fake Home Assistant states.
//
// Run: node tests/card_discovery_check.mjs   (exit 0 = all assertions passed)

import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const cardPath = path.join(
	here,
	"..",
	"custom_components",
	"china_southern_power_grid_stat",
	"frontend",
	"china-southern-power-grid-usage-card.js"
);

// --- browser stubs -----------------------------------------------------
globalThis.HTMLElement = class {
	attachShadow() {
		return { innerHTML: "", querySelector: () => null };
	}
};
const registered = new Map();
globalThis.customElements = {
	define: (name, cls) => registered.set(name, cls),
	get: (name) => registered.get(name),
};
globalThis.window = { customCards: [] };

await import(pathToFileURL(cardPath).href);

const Card = registered.get("csg-usage-calendar-card");
assert.ok(Card, "card did not register csg-usage-calendar-card");

const HISTORY_ID =
	"sensor.ou_yang_jin_qiang_yan_dong_jiang_men_030715039_usage_history";

/** Build a card instance with the given config and states. */
function makeCard(config, states) {
	const card = new Card();
	card._config = config;
	card._hass = { states };
	return card;
}

const historyStates = {
	[HISTORY_ID]: {
		attributes: { daily_usage_history: [["2026-10-01", 1.2]], kwh: 1.2 },
	},
	"sensor.something_else": { attributes: { unit_of_measurement: "kWh" } },
	"calendar.whatever": { attributes: {} },
};

const results = [];
function check(name, fn) {
	try {
		fn();
		results.push(`PASS  ${name}`);
	} catch (err) {
		results.push(`FAIL  ${name}: ${err.message}`);
		process.exitCode = 1;
	}
}

// A stale explicit entity (e.g. saved before the entity_id changed) must not
// stop the card: fall back to discovering the sensor by its attributes.
check("stale configured entity falls back to attribute discovery", () => {
	const card = makeCard(
		{ entity: "sensor.csgaccount_0307150390150952_0307150390150952_daily_usage_history" },
		historyStates
	);
	assert.deepEqual(card._findEntities(), [HISTORY_ID]);
});

// The regression: the entity_id no longer starts with "sensor.csgaccount".
check("discovers by attribute, not by entity_id prefix", () => {
	const card = makeCard({}, historyStates);
	assert.deepEqual(card._findEntities(), [HISTORY_ID]);
});

// A valid explicit entity is still honoured.
check("valid configured entity is used", () => {
	const card = makeCard({ entity: HISTORY_ID }, historyStates);
	assert.deepEqual(card._findEntities(), [HISTORY_ID]);
});

// No history sensor at all -> nothing discovered (card shows a hint).
check("returns nothing when no history sensor exists", () => {
	const card = makeCard({}, { "sensor.other": { attributes: {} } });
	assert.deepEqual(card._findEntities(), []);
});

// The monthly-only sensor also counts (it carries monthly_usage_history).
check("monthly_usage_history alone is enough", () => {
	const card = makeCard(
		{},
		{ "sensor.trend": { attributes: { monthly_usage_history: [] } } }
	);
	assert.deepEqual(card._findEntities(), ["sensor.trend"]);
});

// Multiple matches stay stable across refreshes (sorted).
check("multiple matches are stably ordered", () => {
	const states = {
		"sensor.z_history": { attributes: { daily_usage_history: [] } },
		"sensor.a_history": { attributes: { daily_usage_history: [] } },
	};
	const card = makeCard({}, states);
	assert.deepEqual(card._findEntities(), ["sensor.a_history", "sensor.z_history"]);
});

// Before _hass is set the card must not throw.
check("no hass yields no entities", () => {
	const card = new Card();
	card._config = {};
	assert.deepEqual(card._findEntities(), []);
});

// `account` narrows the choice when several meters are configured.
check("account narrows a multi-account setup", () => {
	const states = {
		"sensor.meter_a_111111111_usage_history": {
			attributes: { daily_usage_history: [] },
		},
		"sensor.meter_b_222222222_usage_history": {
			attributes: { daily_usage_history: [] },
		},
	};
	const card = makeCard({ account: "222222222" }, states);
	assert.deepEqual(card._findEntities(), [
		"sensor.meter_b_222222222_usage_history",
	]);
});

// The live entity_id only carries a truncated account number, so a shortened
// fingerprint has to be enough.
check("account matches a truncated entity_id", () => {
	const card = makeCard({ account: "0307150390150952" }, historyStates);
	assert.deepEqual(card._findEntities(), [HISTORY_ID]);
});

// An account that matches nothing must not blank the card.
check("unmatched account falls back to all matches", () => {
	const card = makeCard({ account: "999999" }, historyStates);
	assert.deepEqual(card._findEntities(), [HISTORY_ID]);
});

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} card checks passed`);
if (failed) process.exitCode = 1;
