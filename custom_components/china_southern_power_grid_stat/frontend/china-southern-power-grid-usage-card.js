/**
 * China Southern Power Grid Usage Calendar Card
 *
 * A Lovelace card that shows daily electricity usage of a month as a calendar
 * grid, plus monthly / yearly trend charts. Data comes from the
 * `daily_usage_history` and `monthly_usage_summary` sensors of the
 * china_southern_power_grid_stat integration.
 *
 * Config:
 *   type: custom:csg-usage-calendar-card
 *   entity: sensor.xxx_0307150390150952_daily_usage_history  # optional
 *   account: "0307150390150952"                              # optional
 *   view: calendar | monthly | yearly | all                  # default: all
 *   title: 用电量                                            # optional
 */

const CARD_VERSION = "1.3.0";

const MS_PER_DAY = 86400000;
// 谷电价（元/度）。南网不提供分时电量，卡片按谷电价给一个偏低的估算值。
const ESTIMATE_RATE = 0.233;
const WEEK_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

/** Format a Date as YYYY-MM-DD in local time. */
const toKey = (d) =>
	`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
		d.getDate()
	).padStart(2, "0")}`;

/** Parse "YYYY-MM-DD" as a local date (avoids UTC shifting). */
const parseKey = (key) => {
	const [y, m, d] = key.split("-").map(Number);
	return new Date(y, m - 1, d);
};

const fmt = (value, digits = 2) =>
	value === null || value === undefined
		? "--"
		: Number(value).toLocaleString("zh-CN", {
				minimumFractionDigits: 0,
				maximumFractionDigits: digits,
		  });

class CsgUsageCalendarCard extends HTMLElement {
	constructor() {
		super();
		this.attachShadow({ mode: "open" });
		this._config = {};
		this._hass = null;
		this._monthOffset = 0; // 0 = current month
		this._view = "all";
		this._initialised = false;
	}

	static getStubConfig(hass) {
		const entity = Object.keys(hass.states).find(
			(eid) =>
				eid.includes("csgaccount") && eid.endsWith("daily_usage_history")
		);
		return { entity: entity || "", view: "all" };
	}

	getCardSize() {
		return 12;
	}

	setConfig(config) {
		if (!config) {
			throw new Error("Invalid configuration");
		}
		this._config = { ...config };
		this._view = config.view || "all";
		// `account` used to be turned into a guessed entity_id. That id scheme
		// no longer exists, so it now only narrows the automatic discovery.
	}

	set hass(hass) {
		const oldStates = this._hass?.states;
		this._hass = hass;
		// Re-render when the sensor state or any of the relevant sensors change.
		const relevant = this._findEntities();
		const changed = relevant.some(
			(eid) => oldStates?.[eid] !== hass.states[eid]
		);
		if (!this._initialised || changed) {
			this._initialised = true;
			this._render();
		}
	}

	/** Locate the history sensor for the configured account. */
	/**
	 * Locate the history sensors.
	 *
	 * Discovery deliberately keys off the *attributes* the integration
	 * publishes, not the entity_id. The entity_id is derived from the device
	 * name (holder + address) and therefore changes whenever the device is
	 * renamed, which used to leave the card pointing at a dead id.
	 */
	_findEntities() {
		if (!this._hass) return [];
		const states = this._hass.states;

		const carriesHistory = (eid) => {
			const attrs = states[eid]?.attributes;
			return !!(
				attrs &&
				("daily_usage_history" in attrs || "monthly_usage_history" in attrs)
			);
		};

		// Honour an explicit entity only while it is actually present.
		if (this._config.entity && states[this._config.entity]) {
			return [this._config.entity];
		}

		const discovered = Object.keys(states).filter(carriesHistory);
		if (discovered.length) {
			// `account` narrows the result when several meters are configured.
			// The device name may truncate the account number, so a shortened
			// fingerprint is accepted too.
			const account = String(this._config.account || "").trim();
			if (account) {
				const fingerprint = account.slice(0, 9);
				const byAccount = discovered.filter(
					(eid) =>
						eid.includes(account) ||
						(fingerprint.length >= 6 && eid.includes(fingerprint))
				);
				if (byAccount.length) return byAccount.sort();
			}
			return discovered.sort();
		}

		// Last resort: the historical id pattern, before the attribute names
		// were settled. Keeps very old cards working.
		if (this._config.entity) {
			return [this._config.entity];
		}
		return Object.keys(states).filter(
			(eid) =>
				eid.startsWith("sensor.csgaccount") && eid.endsWith("daily_usage_history")
		);
	}

	_historySensor() {
		const ids = this._findEntities();
		const id = ids[0];
		return id ? this._hass.states[id] : undefined;
	}

	_render() {
		const entityId = this._findEntities()[0];
		if (!entityId) {
			const stale = this._config.entity
				? `<br><small>配置中的 entity <code>${this._config.entity}</code> 已不存在，` +
				  `可在卡片配置里清空该项让卡片自动查找。</small>`
				: "";
			this._renderError(
				`未找到用电历史传感器，请确认南网集成已加载。${stale}`
			);
			return;
		}
		const stateObj = this._hass.states[entityId];
		if (!stateObj) {
			this._renderError(`实体不存在：${entityId}`);
			return;
		}

		const daily = stateObj.attributes.daily_usage_history || [];
		const monthly = stateObj.attributes.monthly_usage_history || [];
		const yearly = stateObj.attributes.yearly_usage_history || [];

		this.shadowRoot.innerHTML = `
			<style>${this._style()}</style>
			<ha-card>
				<div class="card-header">
					<span>${this._config.title || "用电量日历"}</span>
					<span class="version">v${CARD_VERSION}</span>
				</div>
				<div class="body">
					${this._view !== "monthly" && this._view !== "yearly" ? this._calendarSection(daily) : ""}
					${this._view !== "calendar" ? this._monthlySection(monthly) : ""}
					${yearly.length ? this._yearlySection(yearly) : ""}
				</div>
			</ha-card>
		`;
		this._bindEvents();
	}

	_renderError(message) {
		this.shadowRoot.innerHTML = `
			<style>${this._style()}</style>
			<ha-card>
				<div class="card-header">用电量日历</div>
				<div class="body"><div class="error">${message}</div></div>
			</ha-card>`;
	}

	/** The month grid showing one cell per day. */
	_calendarSection(daily) {
		const now = new Date();
		const viewDate = new Date(
			now.getFullYear(),
			now.getMonth() + this._monthOffset,
			1
		);
		const year = viewDate.getFullYear();
		const month = viewDate.getMonth();
		const daysInMonth = new Date(year, month + 1, 0).getDate();
		// Monday-first offset.
		const firstWeekday = (viewDate.getDay() + 6) % 7;

		const byDate = new Map();
		for (const row of daily) {
			// Rows are [date, kwh] or [date, kwh, cost] to stay under Home
			// Assistant's attribute size limit; accept the older dict form too.
			let rec = null;
			if (Array.isArray(row)) {
				rec = { date: row[0], kwh: row[1], cost: row[2] };
			} else if (row && row.date) {
				rec = { date: row.date, kwh: row.kwh, cost: row.cost };
			}
			if (rec && rec.date) byDate.set(rec.date, rec);
		}

		const values = [];
		for (let day = 1; day <= daysInMonth; day++) {
			const key = toKey(new Date(year, month, day));
			const row = byDate.get(key);
			if (row && row.kwh !== null && row.kwh !== undefined) {
				values.push(row.kwh);
			}
		}
		const maxValue = values.length ? Math.max(...values) : 0;

		let cells = "";
		for (let i = 0; i < firstWeekday; i++) {
			cells += '<div class="day empty"></div>';
		}
		let monthTotal = 0;
		let dataDays = 0;
		for (let day = 1; day <= daysInMonth; day++) {
			const key = toKey(new Date(year, month, day));
			const row = byDate.get(key);
			const hasData = row && row.kwh !== null && row.kwh !== undefined;
			// The CSG API reports many days as exactly 0 kWh (usage is billed in
			// batches). Distinguish "read 0" from "no reading at all".
			const isZero = hasData && Number(row.kwh) === 0;
			const isToday = key === toKey(now);
			if (hasData) {
				monthTotal += row.kwh;
				dataDays += 1;
			}
			const intensity =
				hasData && maxValue > 0 ? Math.max(0.12, row.kwh / maxValue) : 0;
			const bg = hasData
				? isZero
					? ""
					: `background: rgba(3, 155, 229, ${intensity.toFixed(3)});`
				: "";
			const title = hasData
				? `${key}　用电 ${fmt(row.kwh)} kWh${
						row.cost !== null && row.cost !== undefined
							? `　电费 ${fmt(row.cost)} 元`
							: ""
				  }${isZero ? "（当日无用电）" : ""}`
				: `${key}　无数据`;
			const stateClass = isZero ? " zero" : hasData ? "" : " nodata";
			cells += `<div class="day${isToday ? " today" : ""}${stateClass}" style="${bg}" title="${title}">
				<span class="dnum">${day}</span>
				<span class="dval">${hasData ? (isZero ? "0" : fmt(row.kwh, 1)) : ""}</span>
			</div>`;
		}

		return `
			<div class="section">
				<div class="month-nav">
					<button class="nav prev" title="上个月">‹</button>
					<strong>${year}年${month + 1}月</strong>
					<button class="nav next" title="下个月" ${
						this._monthOffset >= 0 ? "disabled" : ""
					}>›</button>
				</div>
				<div class="stats">
					<span>合计 <b>${fmt(monthTotal)}</b> kWh</span>
					<span>有数据 <b>${dataDays}</b> 天</span>
					<span>日均 <b>${
						dataDays ? fmt(monthTotal / dataDays) : "--"
					}</b> kWh</span>
					<span title="按谷电价 ${ESTIMATE_RATE} 元/度估算，非账单金额">
						预计 <b>${fmt(monthTotal * ESTIMATE_RATE)}</b> 元
						<small class="est-tag">估</small>
					</span>
				</div>
				<div class="grid weekdays">
					${WEEK_LABELS.map((w) => `<div class="wd">${w}</div>`).join("")}
				</div>
				<div class="grid">${cells}</div>
			</div>`;
	}

	/** Horizontal bars per month. */
	_monthlySection(monthly) {
		if (!monthly.length) {
			return "";
		}
		const rows = monthly.slice(-12);
		const max = Math.max(...rows.map((r) => r.kwh || 0), 0.0001);
		const bars = rows
			.map((r) => {
				const pct = Math.max(1.5, ((r.kwh || 0) / max) * 100);
				const label = r.month.slice(5);
				return `
				<div class="bar-row" title="${r.month}　${fmt(r.kwh)} kWh${
					r.cost ? `　${fmt(r.cost)} 元` : ""
				}${r.partial ? "（本月进行中）" : ""}">
					<span class="bar-label">${label}月</span>
					<div class="bar-track">
						<div class="bar-fill${r.partial ? " partial" : ""}" style="width:${pct}%"></div>
					</div>
					<span class="bar-value">${fmt(r.kwh, 1)}</span>
				</div>`;
			})
			.join("");
		return `
			<div class="section">
				<div class="section-title">月度趋势</div>
				${bars}
			</div>`;
	}

	/** Yearly totals. */
	_yearlySection(yearly) {
		const rows = yearly
			.map(
				(y) => `
				<div class="year-row">
					<span class="year-label">${y.year}年</span>
					<span class="year-kwh">${fmt(y.kwh)} kWh</span>
					<span class="year-cost">${
						y.cost ? `${fmt(y.cost)} 元` : ""
					}</span>
					<span class="year-note">${y.months} 个月${
					y.partial ? "（含进行中）" : ""
				}</span>
				</div>`
			)
			.join("");
		return `
			<div class="section">
				<div class="section-title">年度对比</div>
				${rows}
			</div>`;
	}

	_bindEvents() {
		const prev = this.shadowRoot.querySelector(".nav.prev");
		const next = this.shadowRoot.querySelector(".nav.next");
		if (prev) {
			prev.addEventListener("click", () => {
				this._monthOffset -= 1;
				this._render();
			});
		}
		if (next) {
			next.addEventListener("click", () => {
				if (this._monthOffset < 0) {
					this._monthOffset += 1;
					this._render();
				}
			});
		}
	}

	_style() {
		return `
			:host { display: block; }
			ha-card { overflow: hidden; }
			.card-header {
				display: flex; justify-content: space-between; align-items: center;
				padding: 14px 16px 6px; font-size: 1.1em; font-weight: 500;
			}
			.version { font-size: 0.7em; color: var(--secondary-text-color); }
			.body { padding: 0 16px 14px; }
			.section { margin-top: 10px; }
			.section-title {
				font-size: 0.95em; font-weight: 500; margin-bottom: 8px;
				color: var(--primary-text-color);
			}
			.month-nav {
				display: flex; justify-content: space-between; align-items: center;
				margin: 4px 0 6px;
			}
			.nav {
				border: none; background: none; cursor: pointer; font-size: 1.4em;
				line-height: 1; padding: 0 10px; color: var(--primary-color);
			}
			.nav[disabled] { color: var(--disabled-text-color); cursor: default; }
			.stats {
				display: flex; gap: 14px; font-size: 0.85em;
				color: var(--secondary-text-color); margin-bottom: 8px;
				flex-wrap: wrap;
			}
			.stats b { color: var(--primary-text-color); }
			.est-tag {
				display: inline-block; margin-left: 2px; padding: 0 3px;
				border-radius: 3px; font-size: 0.85em; line-height: 1.4;
				background: var(--secondary-background-color);
				color: var(--secondary-text-color);
			}
			.grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
			.weekdays { margin-bottom: 4px; }
			.wd {
				text-align: center; font-size: 0.75em;
				color: var(--secondary-text-color);
			}
			.day {
				aspect-ratio: 1 / 0.95; border-radius: 6px; display: flex;
				flex-direction: column; align-items: center; justify-content: center;
				background: var(--secondary-background-color);
				font-variant-numeric: tabular-nums; position: relative;
			}
			.day.empty { background: transparent; }
			.day.nodata { opacity: 0.55; }
			.day.zero { color: var(--secondary-text-color); }
			.day.zero .dval { opacity: 0.7; }
			.day.today { outline: 2px solid var(--primary-color); }
			.dnum { font-size: 0.8em; line-height: 1; }
			.dval { font-size: 0.68em; opacity: 0.9; margin-top: 2px; }
			.bar-row {
				display: flex; align-items: center; gap: 8px;
				font-size: 0.85em; margin-bottom: 4px;
			}
			.bar-label {
				width: 42px; text-align: right; flex: none;
				color: var(--secondary-text-color);
			}
			.bar-track {
				flex: 1; height: 12px; border-radius: 6px; overflow: hidden;
				background: var(--secondary-background-color);
			}
			.bar-fill { height: 100%; background: var(--primary-color); border-radius: 6px; }
			.bar-fill.partial {
				background: repeating-linear-gradient(
					45deg, var(--primary-color), var(--primary-color) 5px,
					transparent 5px, transparent 10px);
			}
			.bar-value { width: 52px; flex: none; font-variant-numeric: tabular-nums; }
			.year-row {
				display: flex; gap: 12px; font-size: 0.87em; padding: 5px 0;
				border-bottom: 1px solid var(--divider-color);
				flex-wrap: wrap;
			}
			.year-label { font-weight: 500; width: 62px; }
			.year-kwh { font-variant-numeric: tabular-nums; }
			.year-cost { color: var(--secondary-text-color); }
			.year-note {
				margin-left: auto; color: var(--secondary-text-color);
				font-size: 0.9em;
			}
			.error {
				color: var(--error-color); font-size: 0.9em; padding: 8px 0;
			}
		`;
	}
}

customElements.define("csg-usage-calendar-card", CsgUsageCalendarCard);

window.customCards = window.customCards || [];
window.customCards.push({
	type: "csg-usage-calendar-card",
	name: "南网用电量日历",
	description:
		"以日历形式显示每日用电量，并提供月度与年度趋势（China Southern Power Grid）",
	preview: true,
});
