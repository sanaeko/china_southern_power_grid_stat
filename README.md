# China Southern Power Grid Statistics GDJM

# 南方电网电费数据HA集成

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/sanaeko/china_southern_power_grid_stat)](https://github.com/sanaeko/china_southern_power_grid_stat/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## 支持功能

- ✅支持南方电网覆盖范围内的电费数据查询（广东、广西、云南、贵州、海南）
- ✅支持使用手机号、短信验证码和密码（可选）登录，支持南网在线APP、微信、支付宝扫码登录
- ✅支持多个南网账户（每个账户一个集成），支持单个账户下的多个缴费号
- ✅数据自动抓取和更新（默认间隔4小时，可配置）
- ✅全程GUI配置，无需编辑yaml进行配置（暂不支持yaml配置）

可接入如下数据：

- 当前余额和欠费
- 当前阶梯电量数据（档位、阶梯剩余电量、阶梯电价）
- 昨日用电量
- 最新一日用电量、电费（取有数据的最近一日）
- 本年度总用电量、总电费（非实时，更新到上个月）
- 本年度每月用电量、电费（非实时，更新到上个月）
- 上年度总用电量、总电费
- 上年度每月用电量、电费
- 当月累计用电量、电费（非实时，有2天左右的延迟）
- 当月每日用电量、电费（非实时，有2天左右的延迟）
- 上月累计用电量、电费
- 上月每日用电量、电费
- **最近一日用电量（持久化历史版）** + 1年每日用电历史
- **月度趋势 / 年度趋势**（最近24个月、按年汇总）

## 用电历史、日历与趋势（v1.4.0 新增）

### 持久化 1 年用电历史

集成会把每天抓到的用电量/电费写入 Home Assistant 的存储文件
（`.storage/china_southern_power_grid_stat_GDJM.usage_history`），
即使重启 HA 也不会丢失，并自动滚动保留最近 **400 天**。

首次加载时会在**后台**自动回填过去 **12 个月**的每日用电数据
（每月一次请求，间隔 1.5 秒，不阻塞集成启动）。回填进度可通过
`history_backfill_complete` 属性查看。

### 新增实体

| 实体后缀 | 说明 |
| --- | --- |
| `daily_usage_history` | 最近一日用电量；属性包含 1 年每日历史 |
| `monthly_usage_summary` | 最近一个月用电量；属性包含月度趋势 |
| `usage_calendar` | 日历实体，每天的用电量是一条全天事件 |

`daily_usage_history` 的属性：

- `daily_usage_history`：`[{date, kwh, cost}, ...]`，逐日数据，无数据的日子 `kwh` 为 `null`
- `monthly_usage_history`：`[{month, kwh, cost, days, partial}, ...]`，最近 24 个月
- `yearly_usage_history`：`[{year, kwh, cost, months}, ...]`，按年汇总
- `history_start` / `history_end` / `history_days`：历史覆盖范围
- `history_backfill_complete`：是否已完成首次回填

> `partial: true` 表示该月数据尚未完整（当月，或部分日期缺数据）。

### 日历

集成会在设备下创建 `calendar.*_usage_calendar` 实体，可直接在
**日历**面板（侧边栏「日历」）或日历卡片中查看每日用电量。
每一天（有数据时）是一条全天事件，标题形如 `用电 58.45 kWh`，
描述中包含当日电费。

### 用电量日历卡片

集成自带一张 Lovelace 卡片，安装后会自动注册前端资源：

```yaml
type: custom:csg-usage-calendar-card
# 可选：指定历史传感器，留空则自动查找
# entity: sensor.xxx_0307150390150952_daily_usage_history
# 可选：显示内容 calendar / monthly / yearly / all（默认 all）
view: all
title: 用电量日历
```

卡片功能：

- 月度日历网格，颜色深浅代表用电量高低，可左右切换月份
- 显示当月合计、有数据天数、日均用电
- 月度趋势条形图（最近 12 个月）
- 年度对比（每年总电量/电费）

如果前端资源没有自动注册（例如 Lovelace 使用 YAML 资源模式），请到
**设置 → 仪表盘 → 资源** 手动添加：

```
/china_southern_power_grid_stat/china-southern-power-grid-usage-card.js
```

### 作为能源仪表盘数据源

`usage_history` 与 `usage_trend` 是 `measurement`
类型的电量传感器，可用于能源仪表盘展示每日/每月用电趋势。

### 实体命名（v1.5.0 起）

设备与实体名称改为使用**户名和地址**，不再堆叠缴费号：

| 项目 | 旧 | 新 |
| --- | --- | --- |
| 设备名 | `CSGAccount-0307150390150952` | `张三 幸福小区3栋501 0307150390150952` |
| 实体显示名 | `CSGAccount-... 0307150390150952-balance` | `张三 幸福小区3栋501 余额` |
| entity_id | `sensor.csgaccount_0307150390150952_..._balance` | `sensor.balance` |

entity_id 使用英文，避免中文名被转成拼音（如 `sensor.yu_e`）：

| entity_id | 显示名 |
| --- | --- |
| `sensor.balance` | 余额 |
| `sensor.arrears` | 欠费 |
| `sensor.yesterday_usage` | 昨日用电量 |
| `sensor.latest_usage` | 最近用电量 |
| `sensor.latest_cost` | 最近电费 |
| `sensor.month_usage` | 本月用电量 |
| `sensor.month_cost` | 本月电费 |
| `sensor.year_usage` | 今年用电量 |
| `sensor.year_cost` | 今年电费 |
| `sensor.last_month_usage` | 上月用电量 |
| `sensor.last_month_cost` | 上月电费 |
| `sensor.last_year_usage` | 去年用电量 |
| `sensor.last_year_cost` | 去年电费 |
| `sensor.ladder_stage` | 当前阶梯 |
| `sensor.ladder_remaining` | 阶梯剩余电量 |
| `sensor.ladder_tariff` | 当前阶梯电价 |
| `sensor.usage_history` | 用电日历数据 |
| `sensor.usage_trend` | 月度用电趋势 |
| `calendar.usage_calendar` | 用电日历 |

> **注意：已有实体不会自动改名。**
> Home Assistant 的实体注册表以 `unique_id` 为准，已存在的实体保留其原有
> `entity_id`。想要得到上表中的干净 ID，需要：
> 1. 在「设置 → 设备与服务」中**删除**本集成
> 2. **重新添加**并重新扫码登录、选择缴费号
>
> 删除不会清空已保存的用电历史（历史存在
> `.storage/china_southern_power_grid_stat_GDJM.usage_history`，按缴费号保存，
> 重新添加后会继续使用）。如果你希望保留现有 `entity_id` 不动，只改显示名，
> 可以只删除实体注册表里的旧实体后再重载集成。

❌**不支持**阶梯电费设置（仅能获取当前所在阶梯）、峰谷电价设置和电费计算（本插件只进行数据抓取和转换，不进行任何计算），
暂时也没有支持计划（南网暂时没有统一的API），如有需求，建议单独创建对应的电价实体。

❌因为南网登录API调整，不再支持登录态失效之后自动重新登录，需要手动重新登录。
## 使用方法

使用[HACS](https://hacs.xyz/)或[手动下载安装](https://github.com/sanaeko/china_southern_power_grid_stat/releases)

注意：本集成需求`Home Assistant`最低版本为`2026.6`。

### 配置界面

支持的登录方式

<img src="https://raw.githubusercontent.com/sanaeko/china_southern_power_grid_stat/master/img/setup_login.png" alt="" style="width: 400px;">

配置界面

<img src="https://raw.githubusercontent.com/sanaeko/china_southern_power_grid_stat/master/img/setup_add_account.png" alt="" style="width: 400px;">

添加缴费号

<img src="https://raw.githubusercontent.com/sanaeko/china_southern_power_grid_stat/master/img/setup_select_account.png" alt="" style="width: 400px;">

传感器列表
- 余额
- 欠费
- 当前阶梯档位
- 当前阶梯剩余电量
- 当前阶梯电价
- 上月电费
- 上月用电量
- 当月用电量
- 当月电费
- 本年度电费
- 本年度用电量
- 上年度电费
- 上年度用电量
- 最近日用电量
- 最近日电费
- 昨日用电量
- 最近一日用电量（历史版，含 1 年每日历史）
- 最近一月用电量（含月度趋势）
- 用电量日历（calendar 实体）




传感器额外参数（每月用量、每日用量）

<img src="https://raw.githubusercontent.com/sanaeko/china_southern_power_grid_stat/master/img/sensor_attr.png" alt="" style="width: 400px;">

参数设置

<img src="https://raw.githubusercontent.com/sanaeko/china_southern_power_grid_stat/master/img/setup_params.png" alt="" style="width: 400px;">

### 数据更新策略

由于上月数据和去年数据在生成之后一般不会发生变化，因此对于上月累计用电量、上月每日用电量、上年度累计用电量、上年度每月用电量，数据更新间隔将会与一般更新间隔有所不同。
具体更新策略如下：

对于上月数据，在每月前3天（1~3日）将会跟随一般更新间隔更新（默认为4小时），其余时间将会停止更新，但数据依然可用。

对于去年数据，在每年一月的前7天（1月1日~1月7日）将会每天更新（在每天第一次触发更新时更新），其余时间将会停止更新，但数据依然可用。

如果需要强制刷新数据，重载集成即可。

对于**用电历史**（`daily_usage_history`），每次更新都会把当月/上月的最新逐日数据
合并进历史文件，因此历史永远是"已知最好"的数据：

- 每日数据只会被更新，不会被空值覆盖（避免某次接口异常抹掉已有数据）
- 月度汇总由逐日数据求和得出；若接口直接返回的月总量大于逐日之和
  （说明部分日期缺数据），则保留接口总量并标记 `partial: true`
- 首次加载时后台回填 12 个月，回填过的月份不会被重复请求

## 一些技术细节

### 登录接口加密原理

登录接口的请求数据和返回数据都经过加密，其中请求数据经过两层加密：整个请求数据的`AES`加密和密码字段的`RSA`
公钥加密（密钥、公钥具体值见代码）。

加密前的请求数据结构如下：

```json5
{
  "areaCode": "xxx",
  "acctId": "xxx",
  "logonChan": "xxx",
  "credType": "xxx",
  "credentials": "xxx"  // <- encrypted with RSA
}
```

返回数据同样经过`AES`加密，密钥与请求数据相同。但返回值其中暂时不包含有用信息，验证状态码正常后可以直接忽略内容。

### Web端接口和App端接口

对于南网API相关信息的提取主要通过Web端的抓包和JS代码获取。
之后因为登录态有效期问题，对App端抓包进行比对后切换到App端API。
经过验证，Web端（网上营业厅）和App端（南网在线）的API接口基本相同，差别主要在于：

|              | Web                        | App                     |
|--------------|----------------------------|-------------------------|
| API路径        | ucs/ma/wt/                 | ucs/ma/zt/              |
| 支持登录方式       | 手机号+验证码（+密码），南网在线/微信/支付宝扫码 | 手机号+验证码（+密码），微信/支付宝跳转登录 |
| token有效期     | 几小时（有待进一步确认）               | 较长（有待进一步确认）                      |
| Cookies      | token包含在cookies中           | 无cookies                |
| 敏感信息（姓名、地址等） | 部分信息用“*”隐去                 | 有明文全文                   |

另外在HTTP请求头上有细微的差别（如：UA），但实际上对于请求的返回结果没有影响。

### API 实现库

本项目代码中的[`csg_client/__init__.py`](https://github.com/sanaeko/china_southern_power_grid_stat/blob/master/custom_components/china_southern_power_grid_stat/csg_client/__init__.py)
是对南网在线 App API 的实现，可以独立于此项目单独使用。
详细使用方法见`csg_client_demo.py`

## Thank you
- [lyylyylyylyy](https://github.com/lyylyylyylyy): PR [#30](https://github.com/sanaeko/china_southern_power_grid_stat/pull/30) 短信验证码登录支持

感谢[瀚思彼岸](https://bbs.hassbian.com/)论坛以下帖子作者的辛苦付出，排名不分先后

- [不折腾，超简单接入电费数据](https://bbs.hassbian.com/thread-18474-1-1.html)
- [北京电费查询加强版](https://bbs.hassbian.com/thread-13820-1-1.html)
- [电费插件（Node-Red流）-广东南方电网](https://bbs.hassbian.com/thread-17830-1-1.html)
- [【抄作业】电费插件(NR流)-南网](https://bbs.hassbian.com/thread-18122-1-1.html)

自定义集成教程参考：[Building a Home Assistant Custom Component Part 1: Project Structure and Basics](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/)






