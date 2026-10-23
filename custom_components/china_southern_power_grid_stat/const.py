"""Constants for the China Southern Power Grid Statistics integration."""

from datetime import timedelta

from .csg_client import LoginType

DOMAIN = "china_southern_power_grid_stat_gdjm"

# The integration used to be published under an uppercase domain
# ("..._GDJM"). Home Assistant's brand-image endpoint validates the domain
# against ``[\da-z_]+`` only, so an uppercase domain can never serve a logo.
# The old name is kept here purely so the saved usage history can be migrated
# instead of being orphaned by the rename.
LEGACY_DOMAIN = "china_southern_power_grid_stat_GDJM"

# config flow
# main account (phone number)
CONF_ACCOUNT_NUMBER = "account_number"
CONF_LOGIN_TYPE = "login_type"
CONF_AUTH_TOKEN = "auth_token"
# electricity accounts
CONF_ELE_ACCOUNTS = "accounts"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_SETTINGS = "settings"
CONF_UPDATED_AT = "updated_at"
CONF_ACTION = "action"
CONF_SMS_CODE = "sms_code"
CONF_REFRESH_QR_CODE = "refresh_qr_code"

STEP_USER = "user"
STEP_SMS_LOGIN = "sms_login"
STEP_SMS_PWD_LOGIN = "sms_pwd_login"
STEP_VALIDATE_SMS_CODE = "validate_sms_code"
STEP_CSG_QR_LOGIN = "csg_qr_login"
STEP_WX_QR_LOGIN = "wx_qr_login"
STEP_ALI_QR_LOGIN = "ali_qr_login"
STEP_QR_LOGIN = "qr_login"
STEP_VALIDATE_QR_LOGIN = "validate_qr_login"
STEP_INIT = "init"
STEP_SETTINGS = "settings"
STEP_ADD_ACCOUNT = "add_account"

ABORT_NO_ACCOUNT = "no_account"
ABORT_ALL_ADDED = "all_added"

CONF_GENERAL_ERROR = "base"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"
ERROR_QR_NOT_SCANNED = "qr_not_scanned"

# UI
LOGIN_TYPE_TO_QR_APP_NAME = {
    LoginType.LOGIN_TYPE_CSG_QR: "南网APP",
    LoginType.LOGIN_TYPE_WX_QR: "微信",
    LoginType.LOGIN_TYPE_ALI_QR: "支付宝",
}

# api


# sensor updates
SUFFIX_BAL = "balance"
SUFFIX_ARR = "arrears"
SUFFIX_YESTERDAY_KWH = "yesterday_kwh"
SUFFIX_LATEST_DAY_KWH = "latest_day_kwh"
SUFFIX_LATEST_DAY_COST = "latest_day_cost"
SUFFIX_THIS_YEAR_KWH = "this_year_total_usage"
SUFFIX_THIS_YEAR_COST = "this_year_total_cost"
SUFFIX_THIS_MONTH_KWH = "this_month_total_usage"
SUFFIX_THIS_MONTH_COST = "this_month_total_cost"
SUFFIX_CURRENT_LADDER = "current_ladder"
SUFFIX_CURRENT_LADDER_REMAINING_KWH = "current_ladder_remaining_kwh"
SUFFIX_CURRENT_LADDER_TARIFF = "current_ladder_tariff"
SUFFIX_LAST_YEAR_KWH = "last_year_total_usage"
SUFFIX_LAST_YEAR_COST = "last_year_total_cost"
SUFFIX_LAST_MONTH_KWH = "last_month_total_usage"
SUFFIX_LAST_MONTH_COST = "last_month_total_cost"
SUFFIX_DAILY_USAGE_HISTORY = "daily_usage_history"
SUFFIX_MONTHLY_USAGE_SUMMARY = "monthly_usage_summary"
# Estimated charges derived from the hard-coded TOU rates (see TOU_RATES).
# These are computed locally because the CSG API does not return daily charges
# for accounts on time-of-use metering.
SUFFIX_ESTIMATED_DAY_COST = "estimated_day_cost"
SUFFIX_ESTIMATED_MONTH_COST = "estimated_month_cost"

ATTR_KEY_THIS_MONTH_BY_DAY = "this_month_by_day"
ATTR_KEY_THIS_YEAR_BY_MONTH = "this_year_by_month"
ATTR_KEY_LAST_MONTH_BY_DAY = "last_month_by_day"
ATTR_KEY_LAST_YEAR_BY_MONTH = "last_year_by_month"
ATTR_KEY_LATEST_DAY_DATE = "latest_day_date"
ATTR_KEY_CURRENT_LADDER_START_DATE = "current_ladder_start_date"
# history attributes
# NOTE: the ATTR_KEY_* names below are the public attribute names shown by
# Home Assistant. They live in the entity's `extra_state_attributes` dict,
# which is a different dict from the coordinator data, so reusing a SUFFIX_*
# value here is intentional and safe.
ATTR_KEY_DAILY_USAGE_HISTORY = "daily_usage_history"
ATTR_KEY_MONTHLY_USAGE_HISTORY = "monthly_usage_history"
ATTR_KEY_YEARLY_USAGE_HISTORY = "yearly_usage_history"
ATTR_KEY_HISTORY_START = "history_start"
ATTR_KEY_HISTORY_END = "history_end"
ATTR_KEY_HISTORY_DAYS = "history_days"
ATTR_KEY_HISTORY_BACKFILL_COMPLETE = "history_backfill_complete"

# Coordinator keys holding the attribute *payload* for the history sensors.
# These must be distinct from the SUFFIX_* keys: both live in the same
# per-account coordinator dict, so a shared name would overwrite the sensor's
# numeric state with the attribute dict.
COORD_KEY_DAILY_HISTORY_ATTRS = "daily_usage_history_attrs"
COORD_KEY_MONTHLY_HISTORY_ATTRS = "monthly_usage_summary_attrs"

STATE_UPDATE_UNCHANGED = "unchanged"
DATA_KEY_LAST_UPDATE_DAY = "last_update_day"

# history
# storage key for persistent daily/monthly usage history
STORAGE_KEY_USAGE_HISTORY = f"{DOMAIN}.usage_history"
STORAGE_VERSION_USAGE_HISTORY = 1
# months of daily data to back-fill on first run
HISTORY_BACKFILL_MONTHS = 12
# delay between back-fill requests to avoid hammering the CSG API
HISTORY_BACKFILL_INTERVAL = 1.5
# how many recent months are exposed in the `monthly_usage_history` attribute
HISTORY_ATTRIBUTE_MONTHS = 24
# debounce for writing history to disk
HISTORY_SAVE_DELAY = 10

# Time-of-use (峰谷) tariff.
#
# The CSG API cannot return a per-period breakdown (峰/谷/平) of consumption for
# every account, nor does it return a daily charge, so the cost of a day cannot
# be computed exactly. These rates are used to produce an *estimate*, and the
# estimator deliberately uses the 谷 (valley) rate only: it is the cheapest
# period, so the result is a lower bound rather than an over-statement.
#
# Periods (local time, hour ranges are [start, end)):
#   峰 peak   10-12, 14-19   1.012 CNY/kWh
#   谷 valley   0-8           0.233 CNY/kWh
#   平 flat     8-10, 12-14, 19-24   0.599 CNY/kWh
TOU_RATES = {"peak": 1.012, "valley": 0.233, "flat": 0.599}
TOU_PERIODS: tuple[tuple[str, int, int], ...] = (
    ("valley", 0, 8),
    ("flat", 8, 10),
    ("peak", 10, 12),
    ("flat", 12, 14),
    ("peak", 14, 19),
    ("flat", 19, 24),
)
#: Rate used for the cost estimate (谷电价).
ESTIMATE_RATE = TOU_RATES["valley"]

# frontend card
URL_BASE = "/china_southern_power_grid_stat"
CARD_FILENAME = "china-southern-power-grid-usage-card.js"
CARD_VERSION = "1.3.0"
CARD_URL = f"{URL_BASE}/{CARD_FILENAME}?v={CARD_VERSION}"

# entity naming
# Human friendly names shown in the UI, prefixed with the device name
# (e.g. "张三 幸福小区3栋501 余额").
SUFFIX_TO_ENTITY_NAME: dict[str, str] = {
    SUFFIX_BAL: "余额",
    SUFFIX_ARR: "欠费",
    SUFFIX_YESTERDAY_KWH: "昨日用电量",
    SUFFIX_LATEST_DAY_KWH: "最近用电量",
    SUFFIX_LATEST_DAY_COST: "最近电费",
    SUFFIX_THIS_YEAR_KWH: "今年用电量",
    SUFFIX_THIS_YEAR_COST: "今年电费",
    SUFFIX_THIS_MONTH_KWH: "本月用电量",
    SUFFIX_THIS_MONTH_COST: "本月电费",
    SUFFIX_CURRENT_LADDER: "当前阶梯",
    SUFFIX_CURRENT_LADDER_REMAINING_KWH: "阶梯剩余电量",
    SUFFIX_CURRENT_LADDER_TARIFF: "当前阶梯电价",
    SUFFIX_LAST_YEAR_KWH: "去年用电量",
    SUFFIX_LAST_YEAR_COST: "去年电费",
    SUFFIX_LAST_MONTH_KWH: "上月用电量",
    SUFFIX_LAST_MONTH_COST: "上月电费",
    SUFFIX_DAILY_USAGE_HISTORY: "用电日历数据",
    SUFFIX_MONTHLY_USAGE_SUMMARY: "月度用电趋势",
    SUFFIX_ESTIMATED_DAY_COST: "预计电费(日)",
    SUFFIX_ESTIMATED_MONTH_COST: "预计电费(月)",
}

# English object ids keep entity_ids ASCII and scriptable (sensor.balance)
# instead of the pinyin that a Chinese name would slugify to (sensor.yu_e).
SUFFIX_TO_OBJECT_ID: dict[str, str] = {
    SUFFIX_BAL: "balance",
    SUFFIX_ARR: "arrears",
    SUFFIX_YESTERDAY_KWH: "yesterday_usage",
    SUFFIX_LATEST_DAY_KWH: "latest_usage",
    SUFFIX_LATEST_DAY_COST: "latest_cost",
    SUFFIX_THIS_YEAR_KWH: "year_usage",
    SUFFIX_THIS_YEAR_COST: "year_cost",
    SUFFIX_THIS_MONTH_KWH: "month_usage",
    SUFFIX_THIS_MONTH_COST: "month_cost",
    SUFFIX_CURRENT_LADDER: "ladder_stage",
    SUFFIX_CURRENT_LADDER_REMAINING_KWH: "ladder_remaining",
    SUFFIX_CURRENT_LADDER_TARIFF: "ladder_tariff",
    SUFFIX_LAST_YEAR_KWH: "last_year_usage",
    SUFFIX_LAST_YEAR_COST: "last_year_cost",
    SUFFIX_LAST_MONTH_KWH: "last_month_usage",
    SUFFIX_LAST_MONTH_COST: "last_month_cost",
    SUFFIX_DAILY_USAGE_HISTORY: "usage_history",
    SUFFIX_MONTHLY_USAGE_SUMMARY: "usage_trend",
    SUFFIX_ESTIMATED_DAY_COST: "estimated_day_cost",
    SUFFIX_ESTIMATED_MONTH_COST: "estimated_month_cost",
}
CALENDAR_ENTITY_NAME = "用电日历"
CALENDAR_OBJECT_ID = "usage_calendar"

# settings

# currently, this timeout is for each request, user should not need to set it manually
SETTING_UPDATE_TIMEOUT = 60
# the first n days in a month that will get data of last month
SETTING_LAST_MONTH_UPDATE_DAY_THRESHOLD = 3
# the first n days in a year that will get data of last year
SETTING_LAST_YEAR_UPDATE_DAY_THRESHOLD = 7


# defaults
DEFAULT_UPDATE_INTERVAL = timedelta(hours=4).seconds
