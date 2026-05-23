# Tradewinds Python Surface Inventory

Exhaustive map of the **public API surface** of the `tradewinds` Python SDK, organized so it can serve as the spec for a TypeScript port (`tradewinds-ts`).

Repo root: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/lucid-grothendieck-47fe70/`

Three distributions (PEP 420 namespace package `tradewinds`):

- `packages/core/` → `tradewinds` (core: `research()`, `snapshot.*`, mode2, transforms, qc, discovery, international, forecasts, plus `core/` v0.2 foundations: temporal, schemas, validator, formats, merge, exceptions)
- `packages/weather/` → `tradewinds-weather` (`tradewinds.weather.*`: AWC/IEM/GHCNh/NWS CLI fetchers, parsers, cache, catalog adapters)
- `packages/markets/` → `tradewinds-markets` (`tradewinds.markets.*`: Kalshi NHIGH/NLOW + Polymarket)

`__version__ = "0.1.0rc1"` (core + weather). `tradewinds-markets` is `0.0.1` placeholder.

---

## 1. Public Functions

### 1.1 `tradewinds` top-level (core `__init__.py`)

`packages/core/src/tradewinds/__init__.py` re-exports exactly one function:

| Symbol | Source | Notes |
|---|---|---|
| `research` | `tradewinds.research` | THE Sprint-0 public surface |
| `__version__` | string `"0.1.0rc1"` | |

#### `research()` — `tradewinds/research.py:876`

```python
def research(
    station: str,
    from_date: str,
    to_date: str,
    *,
    include_forecast: bool = False,
    forecast_model: str | None = None,
    as_dataframe: bool = True,
    tz_override: str | None = None,
) -> pandas.DataFrame | list[dict]
```

Orchestrates the v0.14.1 `pairs()` join. Inclusive `[from_date, to_date]` LST dates. Returns DataFrame indexed by `date` with columns:

`station, cli_high_f, cli_low_f, cli_report_type, obs_high_f, obs_low_f, obs_mean_f, obs_mean_dewpoint_f, obs_max_wind_kt, obs_max_gust_kt, obs_total_precip_in, obs_count, fcst_high_f, fcst_low_f, fcst_model, fcst_issued_at, fcst_pop_6hr_pct, fcst_qpf_6hr_in, market_close_utc`

- `station`: 3-letter NWS (`"NYC"`) or 4-letter ICAO (`"KNYC"`).
- `include_forecast=True` raises `NotImplementedError` in Phase 1.
- Unknown station raises `ValueError`.
- Calls AWC live + IEM ASOS + GHCNh + IEM CLI directly via parallel prefetch (`_prefetch_sources`) then sequential per-month assembly.
- Cache root: `$HOME/.tradewinds/cache/v1/` (override via `TRADEWINDS_CACHE_DIR`).

### 1.2 `tradewinds.snapshot` — `packages/core/src/tradewinds/snapshot.py`

| Function | Signature | File:Line |
|---|---|---|
| `settlement_date_for` | `(as_of: str\|datetime, station: str, tz_override: str\|None = None) -> str` | snapshot.py:215 |
| `settlement_window_utc` | `(date_str: str, station: str, tz_override: str\|None = None) -> tuple[datetime, datetime]` | snapshot.py:243 |
| `cli_available_at` | `(date_str: str, station: str, delay_hours: float = 10.0, tz_override: str\|None = None) -> datetime` | snapshot.py:273 |
| `build_snapshot` | `(station: str, as_of: str\|datetime, observations: list[Observation], all_climate: list[dict], cli_publication_delay_hours: float = 10.0, tz_override: str\|None = None) -> DataSnapshot` | snapshot.py:366 |

Module also exposes the constant `CLI_PUBLICATION_DELAY_HOURS = 10.0` and class `DataSnapshot` (see §2). Private helpers used by `research()`: `_station_code_normalized`, `_lst_offset`, `_parse_as_of`.

Returns ISO date string (`YYYY-MM-DD`) for `settlement_date_for`; aware `datetime` pairs (tz=UTC) for `settlement_window_utc`; aware UTC `datetime` for `cli_available_at`.

LST = January-reference UTC offset (DST ignored), per station IANA tz.

### 1.3 `tradewinds.mode2` — `packages/core/src/tradewinds/mode2.py`

| Function | Signature | File:Line |
|---|---|---|
| `research_by_source` | `(station: str, source: str, from_date: str, to_date: str, *, as_dataframe: bool = True) -> pd.DataFrame` | mode2.py:41 |
| `assert_source_identity` | `(df: pd.DataFrame, expected_source: str) -> None` | mode2.py:93 |

Constant: `_VALID_OBSERVATION_SOURCES = frozenset({"iem.archive", "iem.live", "awc.live", "ghcnh.archive"})`.

Raises `ValueError` for unsupported `source`; `SourceMismatchError` when rows do not all carry `expected_source`; `NotImplementedError` for the Phase 3 fetch wiring (v0.1 ships dispatch only).

### 1.4 `tradewinds.transforms` — `packages/core/src/tradewinds/transforms.py`

`__all__ = ["calendar_features", "clip_outliers", "diff", "diff2", "heat_index", "lag", "rolling", "spread", "wind_chill"]`

| Function | Signature | File:Line |
|---|---|---|
| `lag` | `(df, column: str, periods: int = 1) -> pd.Series` | transforms.py:43 |
| `diff` | `(df, column: str, periods: int = 1) -> pd.Series` | transforms.py:48 |
| `diff2` | `(df, column: str) -> pd.Series` | transforms.py:53 |
| `rolling` | `(df, column: str, window: int, fn: str\|Callable = "mean") -> pd.Series` | transforms.py:58 |
| `calendar_features` | `(df, date_column: str) -> pd.DataFrame` | transforms.py:71 — adds `month_sin/cos`, `dow_sin/cos`, `hour_sin/cos` |
| `spread` | `(df, col_a: str, col_b: str) -> pd.Series` | transforms.py:92 |
| `wind_chill` | `(temp_f: float, wind_mph: float) -> float\|None` (NWS) | transforms.py:97 |
| `heat_index` | `(temp_f: float, rh_pct: float) -> float\|None` (NWS Rothfusz) | transforms.py:108 |
| `clip_outliers` | `(df, column: str, *, std: float = 3.0) -> pd.Series` | transforms.py:139 |

### 1.5 `tradewinds.qc` — `packages/core/src/tradewinds/qc.py`

`__all__ = ["ALPHA_RULES", "QCEngine", "QCRule", "crosscheck_iem_ghcnh"]`

| Function | Signature | File:Line |
|---|---|---|
| `crosscheck_iem_ghcnh` | `(iem_df: pd.DataFrame, ghcnh_df: pd.DataFrame, *, tol_c: float = 2.0) -> pd.DataFrame` | qc.py:191 |

Returns disagreement DataFrame with columns `station, event_time, temp_c_iem, temp_c_ghcnh, delta_c`.

### 1.6 `tradewinds.discovery` — `packages/core/src/tradewinds/discovery.py`

`__all__ = ["DataVersion", "availability", "climate_gaps", "describe", "feature_catalog", "settlement_date_for", "settlement_window_utc"]`

| Function | Signature | File:Line |
|---|---|---|
| `availability` | `(station: str) -> dict` (keys: `station, months_cached, first_month, last_month`) | discovery.py:83 |
| `climate_gaps` | `(station, from_date, to_date) -> list[str]` — **NotImplementedError in v0.1** | discovery.py:99 |
| `describe` | `(schema_id: str) -> str` (multi-line schema description) | discovery.py:112 |
| `feature_catalog` | `() -> list[str]` (lists `transforms.__all__`) | discovery.py:131 |
| `settlement_date_for` | `(station, contract_id, ts: datetime) -> str` (top-level wrapper) | discovery.py:138 |
| `settlement_window_utc` | `(station, settlement_date) -> tuple[datetime, datetime]` — **NotImplementedError in v0.1** | discovery.py:145 |

### 1.7 `tradewinds.international` — `packages/core/src/tradewinds/international.py`

`__all__ = ["DeferredMarketError", "INTERNATIONAL_STATIONS", "daily_extremes"]`

| Function | Signature | File:Line |
|---|---|---|
| `daily_extremes` | `(df: pd.DataFrame, *, station_tz: str) -> pd.DataFrame` (whole-°C rounded) | international.py:98 |

Result columns: `local_date, temp_max_c, temp_min_c, temp_max_f, temp_min_f`.

### 1.8 `tradewinds.forecasts` — `packages/core/src/tradewinds/forecasts.py`

`__all__ = ["SUPPORTED_NWP_MODELS", "forecast_nwp"]`

| Function | Signature | File:Line |
|---|---|---|
| `forecast_nwp` | `(station: str, model: str, *, valid_time: str\|None = None, cycle: str\|None = None) -> pd.DataFrame` | forecasts.py:35 |

`SUPPORTED_NWP_MODELS = frozenset({"hrrr", "gfs", "nbm"})`.
Raises `ValueError` on unknown model; `SourceUnavailableError` if `[nwp]` extra not installed; `NotImplementedError` (Phase 3.2 wiring) otherwise.

### 1.9 `tradewinds.markets.polymarket` — `packages/markets/src/tradewinds/markets/polymarket.py`

`__all__ = ["RESOLUTION_SOURCE_ALLOWLIST", "polymarket_discover", "polymarket_settle"]`

| Function | Signature | File:Line |
|---|---|---|
| `polymarket_discover` | `() -> pd.DataFrame` — **NotImplementedError in v0.1** | polymarket.py:59 |
| `polymarket_settle` | `(event_id: str, *, description: str\|None = None) -> dict` — UUID4 validation + URL allowlist, then **NotImplementedError** | polymarket.py:78 |

Constants: `RESOLUTION_SOURCE_ALLOWLIST = frozenset({"wunderground.com", "www.wunderground.com", "weather.gov", "www.weather.gov"})`; `_MAX_DESCRIPTION_BYTES = 16 * 1024`; private `_EVENT_ID_RE` = strict UUID4 regex.

### 1.10 `tradewinds.markets.catalog.kalshi_nhigh` / `.kalshi_nlow`

NHIGH: `packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py`

```python
def resolve(contract_id: str, settlement_date: datetime.date) -> NHighResolution  # :28
```

NLOW: `packages/markets/src/tradewinds/markets/catalog/kalshi_nlow.py`

```python
def resolve(contract_id: str, settlement_date: datetime.date) -> NLowResolution   # :27
```

- Contract IDs are case-insensitive `KHIGH<CITY>` / `KLOW<CITY>` — city ticker looked up in `KALSHI_SETTLEMENT_STATIONS`.
- `settlement_date` MUST be `date` (not `datetime`), else `TypeError`.
- Returned dataclasses fix `settlement_source = "cli.archive"`.

### 1.11 `tradewinds.weather._fetchers.*` — HTTP fetchers

`tradewinds.weather._fetchers.awc`:
- `fetch_awc_metars(station_icaos: list[str], hours: int = 168) -> list[dict]` — `_fetchers/awc.py:50`
- Constants: `AWC_METAR_URL`, `AWC_MAX_HOURS = 168`.

`tradewinds.weather._fetchers.iem_asos`:
- `download_iem_asos(station: StationInfo, start: date, end: date, dest_dir: Path, *, skip_cache: bool = False, report_type: int = 3) -> list[Path]` — `_fetchers/iem_asos.py:128`
- Constants: `IEM_BASE_URL`, `IEM_POLITE_DELAY = 1.0`.

`tradewinds.weather._fetchers.iem_cli`:
- `download_cli(station_icao: str, year: int, dest_dir: Path, *, skip_cache: bool = False) -> Path` — `_fetchers/iem_cli.py:53`
- `download_cli_range(station_icao, start_year, end_year, dest_dir, *, skip_cache=False) -> list[Path]` — `_fetchers/iem_cli.py:149`
- Constants: `IEM_CLI_BASE_URL`, `IEM_CLI_POLITE_DELAY = 1.0`.

`tradewinds.weather._fetchers.ghcnh`:
- `download_ghcnh(station_id: str, year: int, dest_dir: Path, *, skip_cache: bool = False) -> Path` — `_fetchers/ghcnh.py:56`
- `download_ghcnh_range(station_id, start_year, end_year, dest_dir, *, skip_cache=False) -> list[Path]` — `_fetchers/ghcnh.py:115`
- Constants: `GHCNH_BASE_URL`, `NCEI_POLITE_DELAY = 1.0`.

`tradewinds.weather._fetchers._iem_chunks`:
- `yearly_chunks_inclusive(start: date, end: date) -> list[tuple[date, date]]` — `_iem_chunks.py:27`
- `yearly_chunks_exclusive_end(start: date, end: date) -> list[tuple[date, date]]` — `_iem_chunks.py:49`

### 1.12 Parsers (transform raw bytes → observation/climate dicts)

`tradewinds.weather._awc`:
- `awc_to_observation(m: dict) -> dict | None` — `_awc.py:215`
- `icao_to_station_code(icao: str) -> str` — `_awc.py:34`
- `parse_awc_visibility(vis) -> float | None` — `_awc.py:42`
- `map_cloud_cover(cover: str | None) -> str | None` — `_awc.py:111`

`tradewinds.weather._iem`:
- `iem_to_observation(row: dict[str, str], observation_type_override: str | None = None) -> dict | None` — `_iem.py:124`
- `parse_iem_file(path: Path, observation_type_override: str | None = None) -> list[dict]` — `_iem.py:260`

`tradewinds.weather._climate`:
- `parse_cli_record(record: dict, station_code: str) -> dict | None` — `_climate.py:103`
- `parse_cli_response(data: list[dict], station_code: str) -> list[dict]` — `_climate.py:181`
- `infer_report_type(product: str | None, observation_date: str) -> str` — `_climate.py:55`
- Constant: `REPORT_TYPE_PRIORITY = {"final": 3.0, "ncei_final": 2.5, "correction": 2.0, "preliminary": 1.0, "estimated": 0.0}`.

`tradewinds.weather._ghcnh`:
- `parse_ghcnh_row(row: dict[str, str]) -> dict | None` — `_ghcnh.py:158`
- `parse_ghcnh_file(path: Path) -> list[dict]` — `_ghcnh.py:346`
- `ghcnh_station_to_code(source_station_id: str) -> str | None` — `_ghcnh.py:133`

### 1.13 `tradewinds.weather.cache` — local parquet cache

`__all__ = ["CACHE_VERSION", "DEFAULT_ROOT", "cache_path", "climate_cache_path", "invalidate", "invalidate_climate", "read_cache", "read_climate_cache", "write_cache", "write_climate_cache"]`

| Function | Signature | File:Line |
|---|---|---|
| `cache_path` | `(station: str, year: int, month: int) -> Path` | cache.py:147 |
| `climate_cache_path` | `(station: str, year: int) -> Path` | cache.py:169 |
| `read_cache` | `(station: str, year: int, month: int) -> list[dict] \| None` | cache.py:259 |
| `write_cache` | `(station, year, month, rows: list[dict], *, source: str\|None = None) -> None` | cache.py:294 |
| `invalidate` | `(station, year, month) -> bool` | cache.py:335 |
| `read_climate_cache` | `(station: str, year: int) -> list[dict] \| None` | cache.py:355 |
| `write_climate_cache` | `(station, year, rows, *, source=None) -> None` | cache.py:383 |
| `invalidate_climate` | `(station, year) -> bool` | cache.py:416 |

Constants: `CACHE_VERSION = "v1"`, `DEFAULT_ROOT = Path.home() / ".tradewinds" / "cache"`, `LOCK_TIMEOUT_SECONDS = 30`.

Layout:
- Observations: `$HOME/.tradewinds/cache/v1/observations/<STATION>/<YYYY>/<MM>.parquet`
- Climate: `$HOME/.tradewinds/cache/v1/climate/<STATION>/<YYYY>.parquet`
- Override root via `TRADEWINDS_CACHE_DIR` env var.

Writes skip "current LST month/year" (mutable) and any source with `.live` suffix; use `filelock` `.lock` sidecar + atomic `.tmp`→`replace`.

### 1.14 `tradewinds.weather.catalog`

`__all__ = ["WeatherAdapter", "get_adapter", "list_sources", "register_adapter"]`

| Function | Signature | File:Line |
|---|---|---|
| `register_adapter` | `(source_id: str, adapter_cls: type[WeatherAdapter]) -> None` | catalog/__init__.py:56 |
| `get_adapter` | `(source: str) -> WeatherAdapter` (raises `SourceUnavailableError`) | catalog/__init__.py:73 |
| `list_sources` | `() -> list[str]` | catalog/__init__.py:88 |

Eagerly-registered adapter source IDs: `iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`, `cli.archive`, `cli.live`.

Each adapter exposes `.from_rows(rows, *, source, retrieved_at)` (or `.from_records` for CLI) returning a canonical DataFrame.

### 1.15 `tradewinds.core.*` (Phase 2 foundations)

Exports from `packages/core/src/tradewinds/core/__init__.py`:

- `validate_dataframe(df, schema_id: str, *, allow_source_drift: str | None = None) -> SchemaRegistration` — `core/validator.py:167`
- `assert_no_leakage(df, as_of: TimePoint) -> None` — `core/temporal/leakage.py:36`

Helper utility: `core/validator.register_schema(schema_cls: type[Schema]) -> None`.

Submodule `tradewinds.core.formats`:

- `df_dumps/df_loads`, `parquet_dumps/parquet_loads`, `json_dumps/json_loads`, `csv_dumps/csv_loads`, `toon_dumps/toon_loads`

Submodule `tradewinds.core.merge`:

- `query_time_merge(silver_df, *, policy: ObservationMergePolicy = LIVE_V1) -> pd.DataFrame` — `core/merge.py:76`
- Constant `LIVE_V1` = `ObservationMergePolicy(name="LIVE_V1", source_priority={"awc": 3, "iem": 2, "ghcnh": 1, "ncei": 0})`

### 1.16 `tradewinds._internal._pairs` (internal but consumed by `research()`)

- `build_pairs(station, dates, observations_by_date, climate_by_date, forecasts_by_date=None, *, forecast_model=None, tz_override=None) -> list[dict]` — `_pairs.py:402`
- `build_pairs_row(date_str, station, observations, climate, forecasts, *, forecast_model=None, tz_override=None) -> dict` — `_pairs.py:233`
- `pairs_to_dataframe(rows: list[dict]) -> pd.DataFrame` — `_pairs.py:380`
- `date_range(from_date: str, to_date: str) -> list[str]` — `_pairs.py:362`
- `market_close_utc(date_str: str, station: str, *, tz_override=None) -> datetime` — `_pairs.py:65`
- Constants: `_MARKET_CLOSE_HOUR_LST = 16`, `_MARKET_CLOSE_MINUTE_LST = 30`.

### 1.17 `tradewinds._internal._convert` (unit conversion)

- `kt_to_ms(kt) -> float | None`
- `kt_to_mph(kt) -> float | None`
- `mi_to_km(mi) -> float | None`, `mi_to_m(mi) -> float | None`
- `ft_to_m(ft) -> float | None`
- `inches_to_mm(inches) -> float | None`
- `celsius_to_fahrenheit(c) -> float | None`
- `fahrenheit_to_celsius(f) -> float | None`
- `hpa_to_inhg(hpa) -> float | None`
- `compute_relative_humidity(temp_c, dewp_c) -> float | None` (Magnus formula)
- `compute_feels_like(temp_f, wind_kt, rh) -> float | None` (NWS wind chill + heat index)
- `convert_observation(obs: Observation, units: str) -> Observation` — `units ∈ {"raw","metric","imperial"}`

Conversion constants:
- `_KT_TO_MPH = 1.15078`
- `_KT_TO_MS = 1852.0 / 3600.0`
- `_MI_TO_KM = 1.609344`, `_MI_TO_M = 1609.344`
- `_FT_TO_M = 0.3048`
- `_IN_TO_MM = 25.4`
- `_HPA_TO_INHG = 0.0295299875`
- Magnus: `_MAGNUS_A = 17.625`, `_MAGNUS_B = 243.04`

### 1.18 `tradewinds._internal.merge`

- `merge_observations(rows: list[dict]) -> list[dict]` (`_internal/merge/observations.py:21`) — dedup by `(station_code, observed_at, observation_type)`, strict `>` priority, **AWC=3 > IEM=2 > GHCNh=1**, unknown source=0, first-seen wins.
- `merge_climate(rows: list[dict]) -> list[dict]` (`_internal/merge/climate.py:45`) — dedup by `(station_code, observation_date)`, strict `>` on `report_type_priority`, first-seen wins.

### 1.19 `tradewinds._internal._http`

- `download_with_retry(url: str, dest: Path) -> None` — retries `429/500/502/503/504` with exponential backoff (`BASE_DELAY=1.0`, doubles); writes to `.tmp` then `os.replace`; `MAX_RETRIES = 3`; `HTTP_TIMEOUT = 60.0`.

### 1.20 `tradewinds._internal._bounds`

- `bounded_int(val, lo, hi) -> int | None`
- `bounded_float(val, lo, hi, *, field="") -> float | None`
- `bounded_float_min(val, lo) -> float | None`
- `validate_icao_for_path(value, *, field="station") -> str` (rejects non-`STATION_CODE_RE`)
- `validate_ghcnh_id_for_path(value, *, field="station_id") -> str`
- `assert_path_under(path: Path, root: Path, *, field="path") -> Path`

Constants:
- `SLP_MIN_MB = 870.0`, `SLP_MAX_MB = 1084.0`
- `TEMP_MIN_C = -90.0`, `TEMP_MAX_C = 60.0`
- `MAX_RAW_METAR_LEN = 2048`, `MAX_WX_CODES_LEN = 256`
- `MAX_VISIBILITY_MILES = 99.99`
- `WIND_DIR_BOUNDS = (0, 360)`, `WIND_SPEED_MAX = 200`, `WIND_GUST_MAX = 250`
- `SKY_BASE_MAX_FT = 60000`
- `MIN_YEAR = 1940`, `MAX_YEAR = 2100`
- Regex: `STATION_CODE_RE = re.compile(r"\A[A-Z]{3,4}\Z")`
- Regex: `GHCNH_STATION_ID_RE = re.compile(r"\A[A-Z0-9][A-Z0-9-]{0,31}\Z")`

---

## 2. Public Classes

### 2.1 Snapshot (`tradewinds/snapshot.py`)

#### `DataSnapshot` (frozen `@dataclass`) — snapshot.py:299

Fields:
- `station: str`
- `as_of: str` (ISO 8601 UTC)
- `settlement_date: str` (YYYY-MM-DD LST)
- `window_start_utc: str`, `window_end_utc: str`
- `observations: list[Observation]`
- `climate: dict[str, Any] | None`
- `climate_unavailable_reason: str | None`
- `cli_publication_delay_hours: float`
- `forecasts: list[dict] | None` (always `None` in v0.1)
- `version: DataVersion`

Methods:
- `to_dict() -> dict` — JSON-compatible (uses `to_storage_dict()` for observations).
- `to_toon() -> str` — TOON v3.0 encoded.

### 2.2 Station registry (`tradewinds/_internal/_stations.py`)

#### `StationInfo` (frozen `@dataclass`)

```python
@dataclass(frozen=True)
class StationInfo:
    code: str             # 3-letter NWS code, e.g. "ATL"
    ghcnh_id: str         # NCEI GHCNh id, e.g. "USW00013874"
    icao: str             # 4-letter ICAO, e.g. "KATL"
    name: str
    tz: str               # IANA timezone
    latitude: float
    longitude: float
```

`STATIONS: dict[str, StationInfo]` — exactly the **20 US stations** (the original v0.14.1 universe). See §5 for full list.

There is **also** a separate `StationInfo` model at `packages/core/src/tradewinds/_internal/models/station.py:39` (frozen `@dataclass`):

```python
@dataclass(frozen=True)
class StationInfo:
    code: str
    name: str
    icao: str
    timezone: str
    utc_offset_standard: int  # integer hours, e.g. -5
    latitude: float
    longitude: float
    kalshi_traded: bool = True
    def to_dict(self) -> dict
```

Plus module-level `_STATION_REGISTRY` built eagerly from `_internal._stations.STATIONS`. The two `StationInfo`s coexist — `_internal._stations` is the v0.14.1 lift carrying `ghcnh_id`; the public `models/station.py` is the SDK-facing public shape with `utc_offset_standard` derived from the IANA zone.

### 2.3 Observation model (`tradewinds/_internal/models/observation.py`)

#### `Observation` (frozen `@dataclass`) — observation.py:22

30 storage fields (matches `OBSERVATION_SCHEMA`) plus 2 computed fields (`relative_humidity`, `feels_like_f`) populated in `__post_init__` via `compute_relative_humidity` / `compute_feels_like`.

Storage fields: `station_code, observed_at, observation_type, source, temp_c, dewpoint_c, temp_f, dewpoint_f, wind_dir_degrees, wind_speed_kt, wind_gust_kt, altimeter_inhg, sea_level_pressure_mb, sky_cover_1, sky_base_1_ft, sky_cover_2, sky_base_2_ft, sky_cover_3, sky_base_3_ft, sky_cover_4, sky_base_4_ft, visibility_miles, weather_codes, precip_1hr_inches, peak_wind_gust_kt, peak_wind_dir, peak_wind_time, snow_depth_inches, qc_field, raw_metar`.

Computed: `relative_humidity, feels_like_f`.

Required (`_REQUIRED_FIELDS`): `station_code, observed_at, observation_type, source`.

Class methods:
- `from_dict(d: dict) -> Observation` — raises `ValueError` on missing required fields.

Plus `DictLikeMixin` adds dict-style access methods (see `_internal/models/_base.py`).

### 2.4 Versioning (`tradewinds/_internal/versioning.py`)

#### `DataVersion` (frozen `@dataclass`) — versioning.py:34

Fields: `version: str` (16-hex), `station: str`, `as_of: str`, `latest_observation: str | None`, `observation_count: int`.

Class methods:
- `from_timestamps(*, station: str, as_of: str, observation_timestamps: list[str]) -> DataVersion` — token = SHA-256 of `f"{station}|{','.join(sorted(timestamps))}"` truncated to 16 hex chars. `as_of` is metadata only (not hashed).
- `from_dict(d: dict) -> DataVersion`

Instance methods:
- `to_dict() -> dict`
- `is_newer_than(other) -> bool`
- `is_stale(*, compared_to) -> bool`

### 2.5 Discovery `DataVersion` (different, in `tradewinds/discovery.py:36`)

```python
@dataclass(frozen=True)
class DataVersion:
    sdk_version: str
    schema_ids: tuple[str, ...]
    sources: tuple[str, ...]
    code_sha: str
    data_sha: str
    token: str
    @classmethod
    def from_components(...) -> DataVersion  # SHA-256 of canonical "|"-join
```

NOTE: same name, different shape than `_internal/versioning.DataVersion`. The TS port should disambiguate (`DataVersionV2` vs `DataVersionV1`).

### 2.6 Core (Phase 2 foundations) `tradewinds.core.*`

Exported from `tradewinds.core.__init__`:

- `Schema` (base class) — `core/schema.py:189`. Subclasses declare `schema_id`, `COLUMNS: list[ColumnSpec]`, `IMPERIAL_RENAMES: dict[str, str]`. Class methods: `column_names(mode="metric"|"imperial")`, `column(name)`, `register(source, retrieved_at, rows) -> SchemaRegistration`. `from_dataframe(...)` raises `NotImplementedError` in v0.1.
- `ColumnSpec` (frozen `@dataclass`) — `core/schema.py:43`. Fields: `name, dtype ∈ {string,float64,int64,timestamp_utc,date,bool,enum}, units, nullable, enum_values: tuple[str,...] | None, notes`.
- `SchemaRegistration` (dataclass) — `core/schema.py:101`. Fields: `schema, source, retrieved_at_min, retrieved_at_max, rows, _audit: list[dict]`. Methods: `audit_log()` (defensive copy), `_append_audit(event, **kwargs)` (Validator/`Schema.register` only).
- `TimePoint` — `core/temporal/timepoint.py:29` (UTC-aware wrapper, `__slots__ = ("_utc",)`). Constructor accepts `datetime | pd.Timestamp | str`; rejects naive; rejects date-only ISO strings; rejects `NaT/NaN`. Methods: `to_utc()`, `iso()`, `as_zone(tz: str) -> datetime`. Class methods: `now()`, `from_pandas(ts)`. Comparable & hashable by UTC value.
- `KnowledgeView` — `core/temporal/knowledge_view.py:34` (`__slots__ = ("_df", "_as_of")`). Constructor `KnowledgeView(df, as_of: TimePoint)` validates `df["knowledge_time"]` is tz-aware UTC datetime64. Methods: `dataframe()` (filtered copy, `knowledge_time <= as_of`), property `as_of`.
- `LeakageDetector` — `core/temporal/leakage.py:118`. `LeakageDetector(as_of: TimePoint)`. Method: `check(df) -> None` calls `assert_no_leakage`.

Also in `tradewinds.core.merge`:

- `ObservationMergePolicy` (frozen `@dataclass`) — `core/merge.py:36`. Fields: `name, source_priority: Mapping[str,int], secondary_key: tuple[str, ...] = ("source_received_at", "ingestion_id")`. ClassVar `STRICT_PRIORITY = True`. `__post_init__` wraps `source_priority` in `MappingProxyType`. Method: `apply(silver_df)` = `query_time_merge(silver_df, policy=self)`.

In `tradewinds.qc`:

- `QCRule` (Protocol) — `qc.py:34`. Attributes `rule_id: str, bit_position: int`; method `evaluate(df) -> pd.Series` (bool mask).
- `QCEngine` — `qc.py:137`. ClassVar `rules = ALPHA_RULES`. Methods: `apply(df) -> pd.DataFrame` (adds `obs_qc_status` Int64 bitfield); `build_sidecar_rows(df) -> list[dict]` (matches `schema.observation_qc.v1`).

Private record types: `_RuleSpec` (frozen `@dataclass`: `rule_id, bit_position, description, evaluator`).

### 2.7 Market dataclasses

`StationCitation` (frozen, `markets/catalog/kalshi_stations.py:27`):

```python
@dataclass(frozen=True)
class StationCitation:
    station: str   # 4-letter ICAO, MUST start with "K"
    citation: str  # URL string
    # __post_init__ validates ICAO shape
```

`NHighResolution` (frozen, `markets/catalog/kalshi_nhigh.py:18`) / `NLowResolution` (frozen, `markets/catalog/kalshi_nlow.py:17`):

```python
@dataclass(frozen=True)
class NHighResolution / NLowResolution:
    settlement_source: str   # always "cli.archive"
    settlement_station: str  # 4-letter ICAO
    city_ticker: str
    contract_date: datetime.date
```

`PolymarketEventError` (TradewindsError subclass): `default_error_code = "POLYMARKET_EVENT_INVALID"`.

### 2.8 `WeatherAdapter` Protocol

`tradewinds.weather.catalog.WeatherAdapter` (typing.Protocol, `catalog/__init__.py:33`):

```python
class WeatherAdapter(Protocol):
    SUPPORTED_SOURCES: ClassVar[list[str]]
    def fetch_observations(self, source: str, station: str, from_date: str, to_date: str) -> pd.DataFrame: ...
```

Concrete classes:
- `IEMAdapter` (`catalog/iem.py:41`) — sources: `["iem.archive", "iem.live"]`. `IEM_METAR_LAG = timedelta(minutes=15)`. Static `from_rows(rows, *, source="iem.archive", retrieved_at=None)`.
- `AWCAdapter` (`catalog/awc.py:30`) — sources: `["awc.live"]`. `AWC_LAG = timedelta(minutes=5)`.
- `GHCNhAdapter` (`catalog/ghcnh.py:31`) — sources: `["ghcnh.archive"]`. `GHCNH_LAG = timedelta(hours=6)`.
- `CLIAdapter` (`catalog/cli.py:50`) — sources: `["cli.archive", "cli.live"]`. Static `from_records(records, *, source="cli.archive", station_tz="UTC", retrieved_at=None)`. Performs `(station, observation_date)` dedup with `REPORT_TYPE_PRIORITY`.

---

## 3. Canonical Schemas

Schema framework lives at `tradewinds/core/schema.py` + concrete classes at `tradewinds/core/schemas/`. Eagerly registered with the Validator via `tradewinds/core/schemas/__init__.py`:

- `ObservationSchema` → `schema.observation.v1`
- `ForecastSchema` → `schema.forecast.iem_mos.v1`
- `SettlementSchema` → `schema.settlement.cli.v1`
- `ObservationLedgerSchema` → `schema.observation_ledger.v1`
- `ObservationQCSchema` → `schema.observation_qc.v1`

Each Schema also declares `_registered_source` (the canonical source ID expected by `validate_dataframe`).

### 3.1 `schema.observation.v1` — METAR/SPECI rows (SI units)

`_registered_source = "iem.archive"`. 20 columns. Plus overlay columns `source`, `retrieved_at`, `knowledge_time`, `event_time` populated by adapters (not part of `COLUMNS`).

| Column | dtype | units | nullable | notes |
|---|---|---|---|---|
| station | string | — | False | ICAO/ASOS ID (e.g. KORD) |
| event_time | timestamp_utc | — | False | observation valid time |
| observation_type | enum {METAR,SPECI} | — | False | |
| temp_c | float64 | celsius | True | bounded |
| dew_point_c | float64 | celsius | True | |
| wind_speed_ms | float64 | m/s | True | from kt |
| wind_dir_deg | int64 | degrees | True | 0-360 |
| wind_gust_ms | float64 | m/s | True | from kt |
| slp_hpa | float64 | hPa | True | aviation unit, not converted |
| visibility_m | float64 | meters | True | from statute miles |
| precip_mm_1h | float64 | mm | True | from inches |
| sky_cover_1 | enum {CLR,FEW,SCT,BKN,OVC,VV} | — | True | |
| sky_base_1_m | float64 | meters | True | from feet |
| sky_cover_2 | enum {CLR,FEW,SCT,BKN,OVC,VV} | — | True | |
| sky_base_2_m | float64 | meters | True | |
| sky_cover_3 | enum | — | True | |
| sky_base_3_m | float64 | meters | True | |
| sky_cover_4 | enum | — | True | |
| sky_base_4_m | float64 | meters | True | |
| metar_raw | string | — | True | null for AWC JSON |

Imperial rename map: `event_time→utc_datetime`, `temp_c→temp_F`, `dew_point_c→dew_point_F`, `wind_speed_ms→wind_speed_kt`, `wind_gust_ms→gust_kt`, `visibility_m→vsby`, `precip_mm_1h→precip_in_1h`, `sky_base_N_m→sky_base_N_ft`.

### 3.2 `schema.forecast.iem_mos.v1` — IEM MOS forecast (subset of mostlyright 37-col FORECAST_FIELDS)

`_registered_source = "iem.archive"`. 11 columns.

| Column | dtype | units | nullable |
|---|---|---|---|
| station | string | — | False |
| issued_at | timestamp_utc | — | False |
| valid_at | timestamp_utc | — | False |
| forecast_hour | int64 | hours | False |
| model | string | — | False (NBE, GFS, LAV, MET, …) |
| temp_c | float64 | celsius | True |
| dew_point_c | float64 | celsius | True |
| wind_speed_ms | float64 | m/s | True |
| wind_dir_deg | int64 | degrees | True |
| precip_probability | float64 | probability (0–1) | True |
| sky_cover_pct | int64 | percent (0–100) | True |

Imperial renames: `temp_c→temp_F`, `dew_point_c→dew_point_F`, `wind_speed_ms→wind_speed_kt`.

### 3.3 `schema.settlement.cli.v1` — NWS CLI daily settlement (Fahrenheit canonical)

`_registered_source = "cli.archive"`. 12 columns. No imperial rename map.

| Column | dtype | units | nullable | notes |
|---|---|---|---|---|
| station | string | — | False | ICAO/ASOS ID |
| station_tz | string | — | False | IANA tz (e.g. America/Chicago) |
| observation_date | date | — | False | NWS local climate day |
| event_time | timestamp_utc | — | False | 00:00 local → UTC |
| product_release_time | timestamp_utc | — | False | from product header |
| report_type | enum {preliminary,final,correction} | — | False | |
| temp_max_F | float64 | fahrenheit | True | daily high |
| temp_min_F | float64 | fahrenheit | True | daily low |
| precipitation_in | float64 | inches | True | |
| snowfall_in | float64 | inches | True | |
| cli_data_quality | enum {clean,flagged_instrument,flagged_late,flagged_other,missing} | — | False | |
| settlement_finality | enum {provisional,final,superseded} | — | False | |

### 3.4 `schema.observation_ledger.v1` — silver-tier per-source ledger

`_registered_source = "iem.archive"`. Natural key: `(station_code, observed_at, source, parser_name, as_of_time, ingestion_id)`.

Includes the 30 v0.14.1 fields (truncated in Schema dataclass — full set is in `OBSERVATION_LEDGER_SCHEMA` pyarrow definition at `_internal/merge/_schemas.py:71`). Plus 9 lineage fields (all nullable):

- `parser_name: enum {mostlyright_v1, iem, ncei, ghcnh}`
- `parser_version: string`
- `ingestion_id: string`
- `as_of_time: timestamp_utc`
- `source_received_at: string`
- `qc_status: enum {clean, flagged, suspect}`
- `observation_kind: enum {METAR, SPECI}`
- `provenance: enum {legacy, reingested}`
- `observation_quality: enum {clean, flagged, suspect}`

Key columns explicitly declared in the Python Schema class: `station_code (string, !null), observed_at (timestamp_utc, !null), observation_type (enum {METAR,SPECI}, !null), source (enum {awc, iem, ghcnh, ncei}, !null), temp_c (float64, null), dewpoint_c (float64, null)` + the 9 lineage fields.

### 3.5 `schema.observation_qc.v1` — QC sidecar (Phase 2.1 forward-compat)

13 columns. `_registered_source = "iem.archive"`.

| Column | dtype | nullable | notes |
|---|---|---|---|
| station_code | string | False | |
| observed_at | timestamp_utc | False | |
| observation_kind | enum {METAR,SPECI} | True | |
| source | enum {awc,iem,ghcnh,ncei} | False | |
| parser_name | string | True | |
| as_of_time | timestamp_utc | True | |
| ingestion_id | string | True | |
| qc_system | string | False | e.g. "tradewinds.qc.alpha" |
| qc_version | string | False | e.g. "v0.1.0a1" |
| rule_id | string | False | e.g. "temp_c.out_of_range" |
| field | string | False | observation column the rule evaluated |
| flag | enum {clean,flagged,suspect} | False | |
| detector_metadata | string | True | JSON payload |

### 3.6 pyarrow schemas (cache storage)

At `tradewinds/_internal/merge/_schemas.py`:

`OBSERVATION_SCHEMA` — 30 pyarrow fields used by parquet cache writes. Field order (verbatim from v0.14.1):

```
station_code string, observed_at string, observation_type string, source string,
temp_c float64, dewpoint_c float64, temp_f float64, dewpoint_f float64,
wind_dir_degrees int32, wind_speed_kt int32, wind_gust_kt int32,
altimeter_inhg float64, sea_level_pressure_mb float64,
sky_cover_1 string, sky_base_1_ft int32,
sky_cover_2 string, sky_base_2_ft int32,
sky_cover_3 string, sky_base_3_ft int32,
sky_cover_4 string, sky_base_4_ft int32,
visibility_miles float64, weather_codes string, precip_1hr_inches float64,
peak_wind_gust_kt int32, peak_wind_dir int32, peak_wind_time string,
snow_depth_inches float64, qc_field int32, raw_metar string
```

`OBSERVATION_LEDGER_SCHEMA` — `OBSERVATION_SCHEMA` + 9 lineage fields (all string).

`QC_SIDECAR_SCHEMA` — 13 string fields, identical to `schema.observation_qc.v1`.

Climate cache uses the inferred-from-rows pyarrow schema (cache layer falls back to inference; canonical row dict shape produced by `parse_cli_record`):

```python
{
  "station_code": str,
  "observation_date": str (YYYY-MM-DD),
  "high_temp_f": int | None,
  "low_temp_f": int | None,
  "report_type": str,                # final|ncei_final|correction|preliminary|estimated
  "report_type_priority": float,
  "source": str,                     # "iem"
  "product_id": str | None,
  "issued_at": str | None,           # ISO-8601 UTC
}
```

Climate temp bounds (from `_climate.py`): `HIGH_TEMP_MIN_F=-60, HIGH_TEMP_MAX_F=150, LOW_TEMP_MIN_F=-80, LOW_TEMP_MAX_F=130`.

---

## 4. HTTP Endpoints

### 4.1 AWC METAR (live, ~168h history)

- Base URL: `https://aviationweather.gov/api/data/metar`
- Request: GET with query params `ids=<csv ICAOs>&format=json&taf=false&hours=<N≤168>`
- Politeness: AWC has no published delay; the fetcher uses none.
- Response: JSON array of dicts. Key fields used by `awc_to_observation`:

  ```
  icaoId, obsTime (Unix seconds), metarType ("METAR"|"SPECI"),
  wdir (int|"VRB"|str), wspd, wgst, altim (hPa), slp, temp (°C), dewp (°C),
  visib (str: "10+", "1/2", "2 1/4", plain numbers, etc.),
  clouds: [{cover, base}, ...],
  rawOb (raw METAR text up to 2048 chars),
  wxString (weather codes),
  precip (precipitation, "T" = trace),
  qcField (bitmask int)
  ```

- Error contract: never raises — empty list on 4xx, timeout, exhausted retries, non-list body.
- Retry: 5xx + 429 with exponential backoff; `BASE_DELAY=1.0`, `MAX_RETRIES=3`.

### 4.2 IEM ASOS (historical METAR/SPECI CSV)

- Base URL: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`
- Granularity: per-station-year (yearly chunks, EXCLUSIVE end day).
- Request: GET with params (exact byte-shape, no leading `?` shown):

  ```
  station=<3-letter NWS code>           # e.g. NYC (NOT KNYC)
  &data=all
  &tz=Etc/UTC
  &format=comma
  &latlon=no
  &elev=no
  &missing=M
  &trace=T
  &direct=no
  &report_type=<3|4>                    # 3=METAR, 4=SPECI
  &year1=YYYY&month1=MM&day1=DD         # inclusive start
  &year2=YYYY&month2=MM&day2=DD         # EXCLUSIVE end (always Jan 1 of next year)
  ```

- Response: CSV with `#`-prefix comment lines + header + rows. Columns parsed by `iem_to_observation` include: `station, valid (YYYY-MM-DD HH:MM), tmpf (°F), dwpf (°F), drct, sknt, gust, alti (inHg), mslp (mb), vsby (mi), skyc1..4, skyl1..4 (ft), wxcodes, p01i, snowdepth, peak_wind_gust, peak_wind_drct, peak_wind_time, metar`.
- Politeness: `IEM_POLITE_DELAY = 1.0` s between requests.
- Errors: 5xx + 429 retried; 4xx propagates via `download_with_retry`.
- Cache filename: `iem_{start_iso}_{end_iso}_{partial?}_{metar|speci}.csv` under `dest_dir/<station.code>/`.

### 4.3 IEM CLI (NWS climate / settlement)

- Base URL: `https://mesonet.agron.iastate.edu/json/cli.py`
- Request: GET with `station=<ICAO e.g. KNYC>&year=<YYYY>`.
- Granularity: one request per (station-year).
- Response: JSON, either bare array or `{"results": [...]}`. Each record consumed by `parse_cli_record`:

  ```
  valid:    str (YYYY-MM-DD local climate day, NWS convention)
  high:     int | "M" | "" (°F)
  low:      int | "M" | "" (°F)
  product:  str (e.g. "202501160620-KFFC-CDUS42-CLIATL")
              first 12 chars = YYYYMMDDHHmm issued timestamp UTC
  ```

- Cache: `dest_dir/<icao>/cli_<year>.json` (unwrapped JSON array).
- Politeness: `IEM_CLI_POLITE_DELAY = 1.0` s. FileLock on `cli_<year>.json.lock` (30s timeout).
- Errors: 404 (no data for year) raised as `HTTPStatusError`; callers using `download_cli_range` skip 404s with `info` log.

### 4.4 GHCNh (NCEI per-station-year PSV)

- Base URL: `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access`
- Request: GET `<base>/by-year/<YEAR>/psv/GHCNh_<station_id>_<YEAR>.psv` (no query params).
- `station_id`: NCEI GHCNh id (e.g. `"USW00094728"` for KNYC, or the joined `"744860-94789"` form).
- Politeness: `NCEI_POLITE_DELAY = 1.0` s **after** successful download (cache hits and 404s skip the delay).
- Response: PSV (pipe-delimited). Columns consumed by `parse_ghcnh_row`:

  ```
  DATE (YYYY-MM-DDTHH:MM:SSZ?), temperature_Report_Type ("FM15"|"FM16"|...),
  temperature, temperature_Quality_Code, temperature_Source_Station_ID,
  dew_point_temperature[...], wind_direction[...], wind_speed[...], wind_gust[...],
  sea_level_pressure[...], altimeter[...], visibility[...] (km),
  precipitation[...] (mm), snow_depth[...] (cm),
  sky_cover_summation_{1..4}[/baseht/Quality_Code/etc],
  pres_wx_AW{1..3}[/Quality_Code], REM (raw remarks containing METAR text)
  ```

  Quality_Code filtering: accept `{"0", "1", "4", "5", ""}`; reject `{"2", "3", "6", "7", "I", "P", "R", "U"}`.

- Cache: `dest_dir/<station_id>/GHCNh_<station_id>_<YEAR>.psv`.
- Errors: 404 raises `HTTPStatusError`; `download_ghcnh_range` skips 404s.

### 4.5 NOAA Big Data Program (HRRR / GFS / NBM)

Phase 3.2 stub only. `forecast_nwp()` declares the dispatch but raises `NotImplementedError`. URLs and byte-range/cfgrib decode logic are deferred to v0.2 (the `[nwp]` optional extra requires `cfgrib`, `xarray`, `scikit-learn`).

### 4.6 Polymarket Gamma API

Phase 3.3 stub. `polymarket_discover()` and `polymarket_settle()` raise `NotImplementedError` after boundary validation. URLs not yet wired in v0.1. Allowed resolution-source netlocs: `wunderground.com`, `www.wunderground.com`, `weather.gov`, `www.weather.gov`.

---

## 5. Station Registry

### 5.1 v0.14.1 US registry — `tradewinds/_internal/_stations.py`

`STATIONS: dict[str, StationInfo]` contains exactly **20 US stations** (the v0.14.1 Kalshi universe). Full list:

| code | icao | ghcnh_id | name | tz | lat | lon |
|---|---|---|---|---|---|---|
| ATL | KATL | USW00013874 | Hartsfield-Jackson Atlanta International | America/New_York | 33.6407 | -84.4277 |
| AUS | KAUS | USW00013904 | Austin-Bergstrom International | America/Chicago | 30.1975 | -97.6664 |
| BOS | KBOS | USW00014739 | Boston Logan International | America/New_York | 42.3656 | -71.0096 |
| DCA | KDCA | USW00013743 | Washington Reagan National | America/New_York | 38.8512 | -77.0402 |
| DEN | KDEN | USW00003017 | Denver International | America/Denver | 39.8561 | -104.6737 |
| DFW | KDFW | USW00003927 | Dallas-Fort Worth International | America/Chicago | 32.8998 | -97.0403 |
| HOU | KHOU | USW00012918 | Houston Hobby | America/Chicago | 29.6454 | -95.2789 |
| LAS | KLAS | USW00023169 | Harry Reid (McCarran) International | America/Los_Angeles | 36.0840 | -115.1537 |
| LAX | KLAX | USW00023174 | Los Angeles International | America/Los_Angeles | 33.9425 | -118.4081 |
| MDW | KMDW | USW00014819 | Chicago Midway International | America/Chicago | 41.7868 | -87.7522 |
| MIA | KMIA | USW00012839 | Miami International | America/New_York | 25.7959 | -80.2870 |
| MSP | KMSP | USW00014922 | Minneapolis-St Paul International | America/Chicago | 44.8848 | -93.2223 |
| MSY | KMSY | USW00012916 | New Orleans Louis Armstrong International | America/Chicago | 29.9934 | -90.2580 |
| NYC | KNYC | USW00094728 | Central Park, New York | America/New_York | 40.7789 | -73.9692 |
| OKC | KOKC | USW00013967 | Oklahoma City Will Rogers World | America/Chicago | 35.3931 | -97.6007 |
| PHL | KPHL | USW00013739 | Philadelphia International | America/New_York | 39.8721 | -75.2411 |
| PHX | KPHX | USW00023183 | Phoenix Sky Harbor International | America/Phoenix | 33.4373 | -112.0078 |
| SAT | KSAT | USW00012921 | San Antonio International | America/Chicago | 29.5337 | -98.4698 |
| SEA | KSEA | USW00024233 | Seattle-Tacoma International | America/Los_Angeles | 47.4502 | -122.3088 |
| SFO | KSFO | USW00023234 | San Francisco International | America/Los_Angeles | 37.6213 | -122.3790 |

### 5.2 International stations — `tradewinds/international.py`

`INTERNATIONAL_STATIONS: dict[str, str]` — **40 ICAOs → IANA tz** (Phase 3.1 expansion). Categorized:

**Europe (20):** EGLL, EGKK, LFPG, LFPB, LFPO, EDDF, EDDB, EDDM, LEMD, LEBL, LIRF, LIMC, EHAM, EKCH, ESSA, EFHK, LSZH, LOWW, EPWA, UUEE

**Asia (14):** RJTT, RJAA, RKSI, ZBAA, ZSPD, VHHH (deferred — HKO), RCTP (deferred — CWA), WSSS, VTBS, VABB, VIDP, OMDB, OERK, OTHH

**Oceania (5):** YSSY, YMML, YBBN, NZAA, NZWN

**Americas non-US (2):** SBGR, SAEZ

(20 + 14 + 5 + 2 = **41** entries, not 40 as advertised — recount: Europe LFPO is the 5th Paris airport, EDDB is Berlin, EDDM Munich, LEBL Barcelona, LIMC Milan ⇒ Europe = 20. Asia: RJTT, RJAA, RKSI, ZBAA, ZSPD, VHHH, RCTP, WSSS, VTBS, VABB, VIDP, OMDB, OERK, OTHH ⇒ 14. Oceania: YSSY, YMML, YBBN, NZAA, NZWN ⇒ 5. Americas: SBGR, SAEZ ⇒ 2. **Total = 41.** US = 20. Grand total = 61.) The "60 stations" comment in the user's question is approximate — the actual count is 20 US + 41 international = 61.

Also at module level:
- `DEFERRED_STATIONS: frozenset[str] = frozenset({"VHHH", "RCTP"})` — markets that resolve to these stations raise `DeferredMarketError` until v0.2 adds CWA + HKO clients.

The `STATIONS` dict in `_internal/_stations.py` is **NOT** updated with international stations; `INTERNATIONAL_STATIONS` is a separate ICAO→tz map. The `research()` orchestrator currently rejects unknown stations from `STATIONS`, so the 41 international entries are not yet end-to-end wired in v0.1.

### 5.3 Snapshot tz map — `tradewinds/snapshot.py:46`

`_STATION_TZ: dict[str, str]` — exhaustive list of ~80 US station codes (3-letter NWS) mapped to IANA tz. Used by `_lst_offset()` and `settlement_window_utc()`. Covers Eastern, Central, Mountain (incl. Phoenix/Tucson with no DST), Pacific, Alaska, Hawaii. Public surface accepts `tz_override` for stations not in this map.

---

## 6. Kalshi Contract Spec

### 6.1 `KALSHI_SETTLEMENT_STATIONS` — `packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py:49`

20-city whitelist. `dict[str, StationCitation]` keyed by **city ticker** (the suffix of `KHIGH<CITY>` / `KLOW<CITY>` Kalshi contract IDs):

```
NYC → KNYC (Central Park, NOT LGA/JFK)
CHI → KMDW (Midway, NOT ORD)
LAX → KLAX
MIA → KMIA
DEN → KDEN
BOS → KBOS
AUS → KAUS
DCA → KDCA (Reagan, NOT Dulles or BWI)
PHL → KPHL
SFO → KSFO (NOT OAK)
SEA → KSEA (NOT BFI)
ATL → KATL
HOU → KIAH (Intercontinental, NOT Hobby — note Kalshi quirk)
DAL → KDFW (NOT Love Field)
PHX → KPHX
MSP → KMSP
DTW → KDTW
CVG → KCVG
BNA → KBNA
SLC → KSLC
```

### 6.2 `KNOWN_WRONG_STATIONS` — frozen set

```python
{"KLGA", "KJFK", "KEWR", "KORD", "KIAD", "KBWI", "KOAK", "KHOU", "KDAL"}
```

Contract test asserts none of these appear as values in `KALSHI_SETTLEMENT_STATIONS`. If a TS port re-implements this whitelist, port the test too — silently swapping `KMDW → KORD` would invalidate every Chicago backtest.

### 6.3 Resolvers

```python
# kalshi_nhigh.resolve("KHIGHNYC", date(2025,1,6))
#   -> NHighResolution(settlement_source="cli.archive",
#                      settlement_station="KNYC",
#                      city_ticker="NYC",
#                      contract_date=date(2025,1,6))

# kalshi_nlow.resolve("KLOWCHI", date(2025,1,6))
#   -> NLowResolution(settlement_source="cli.archive",
#                     settlement_station="KMDW",
#                     city_ticker="CHI",
#                     contract_date=date(2025,1,6))
```

Both raise `TypeError` on `datetime` (must be `date` only), `TypeError` on non-str `contract_id`, `ValueError` on bad prefix or unknown city.

### 6.4 Market close

Kalshi NHIGH/NLOW markets close at 4:30 PM LST (`_MARKET_CLOSE_HOUR_LST=16, _MARKET_CLOSE_MINUTE_LST=30`). Computed by `tradewinds._internal._pairs.market_close_utc()` and exposed via the `market_close_utc` column in `research()` output.

---

## 7. Format Serializers

`tradewinds.core.formats` exposes 5 lossless/lossy pairs. Dispatch by name:

| Format | dumps | loads | wire type | lossy? |
|---|---|---|---|---|
| `dataframe` | identity passthrough | identity | `pd.DataFrame` | no (in-memory only) |
| `parquet` | pyarrow + zstd | pyarrow | `bytes` | lossless for canonical schemas |
| `json` | `df.to_json(orient="records", date_format="iso")` + empty-frame envelope `{"columns":[...],"data":[]}` | parses records OR envelope | `str` | lossy: Int64→float64, Categorical→object, possibly tz |
| `csv` | `df.to_csv(index=False)` | `pd.read_csv` | `str` | lossy: dtype, null distinction, tz |
| `toon` | TOON v3.0 tabular block `rows[N]{col1,col2,...}:` via lifted `encode_tabular` | regex/hand parser → DataFrame | `str` | lossy: ns→µs truncation, Categorical→object, ISO timestamps stay as strings (caller must `pd.to_datetime`) |

Re-exports in `tradewinds.core.formats.__init__`:
- `df_dumps`, `df_loads`
- `parquet_dumps`, `parquet_loads`
- `json_dumps`, `json_loads`
- `csv_dumps`, `csv_loads`
- `toon_dumps`, `toon_loads`

Plus low-level TOON helpers in `tradewinds._internal._toon` (re-used by `DataSnapshot.to_toon()`): `encode(obj) -> str`.

---

## 8. Exception Hierarchy

All defined in `tradewinds.core.exceptions` (`packages/core/src/tradewinds/core/exceptions.py`). Base class hierarchy:

```
Exception
└── TradewindsError                  (default_error_code = "TRADEWINDS_ERROR")
    ├── SourceUnavailableError        ("SOURCE_UNAVAILABLE")
    ├── SchemaValidationError         ("SCHEMA_VALIDATION_FAILED")
    ├── SourceMismatchError           ("SOURCE_MISMATCH")
    ├── LeakageError                  ("LEAKAGE_DETECTED")
    ├── TemporalDriftError            ("TEMPORAL_DRIFT")
    ├── PayloadTooLargeError          ("PAYLOAD_TOO_LARGE")
    │
    ├── DeferredMarketError           ("DEFERRED_MARKET")            # in tradewinds.international
    ├── PolymarketEventError          ("POLYMARKET_EVENT_INVALID")   # in tradewinds.markets.polymarket
    │
    └── TherminalError                 (HTTP-layer marker; from tradewinds._internal.exceptions)
        ├── NotFoundError              (HTTP 404)
        ├── RateLimitError             (HTTP 429, carries .retry_after)
        ├── ValidationError            (HTTP 400)
        ├── AuthenticationError        (HTTP 401)
        ├── ForbiddenError             (HTTP 403)
        └── ServerError                (HTTP 5xx)
```

Deprecation alias: `MostlyRightMCPError` resolves to `TradewindsError` via `__getattr__`, emits `DeprecationWarning` once. Removal target v0.3.

### 8.1 Base class: `TradewindsError.__init__`

```python
TradewindsError(
    message: str = "",
    *,
    error_code: str | None = None,   # defaults to default_error_code
    source: str | None = None,
    request_id: str | None = None,
)
```

`to_dict() -> dict` returns a JSON-safe dict (via `tradewinds.core._json_safe.to_json_safe`). Base payload:

```json
{"error_code": str, "message": str, "source": str|null, "request_id": str|null}
```

Subclasses override `_payload()` to extend the dict.

### 8.2 `SourceUnavailableError`

Extra fields: `http_status: int | None`, `retryable: bool = False`, `retry_after_s: float | None`, `underlying: str = ""`, `url: str | None`.

`to_dict()` adds: `http_status, retryable, retry_after_s, underlying, url`.

### 8.3 `SchemaValidationError`

Constructor:
```python
SchemaValidationError(message, *, schema_id: str, violations: list[dict] | None = None,
                      quarantine_count: int = 0, sample_violations: list[dict] | None = None,
                      source=None, request_id=None, error_code=None)
```

Extra fields: `schema_id, violations, quarantine_count, sample_violations`.

Violation dicts use the shape `{"column": str, "rule": str, ...extras}`. Known rules:
- `source_attr_required` — missing `df.attrs["source"]`
- `source_column_required` — missing per-row `source` column
- `retrieved_at_required` — neither attrs nor column carried provenance
- `required_column_missing`
- `non_nullable_has_nulls` (carries `count`)
- `mixed_null_sentinels` (Pitfall 15)
- `dtype_mismatch` (carries `expected, actual`)
- `dtype_check_error` (carries `error`)
- `unknown_dtype` (carries `dtype`)
- `enum_value_violation` (carries `count, sample`)
- `unknown_schema_id`

### 8.4 `SourceMismatchError`

```python
SourceMismatchError(message, *, schema_source: str, data_source: str,
                    role: str | None = None,                 # ∈ {"observations","forecasts","settlement"} or None
                    catalog_warning: str | None = None,
                    source=None, request_id=None, error_code=None)
```

ClassVar `VALID_ROLES = frozenset({"observations","forecasts","settlement"})`. `to_dict()` adds `schema_source, data_source, role, catalog_warning`.

### 8.5 `LeakageError`

```python
LeakageError(message, *, as_of: str, violating_count: int,
             sample_violations: list[dict] | None = None,
             source=None, request_id=None, error_code=None)
```

Sample violation shape: `{"row_idx": int, "knowledge_time": str (ISO 8601 UTC)}`.

`to_dict()` adds `as_of, violating_count, sample_violations`.

### 8.6 `TemporalDriftError`

```python
TemporalDriftError(message, *, schema_id: str, asserted_range: tuple[str, str],
                   violating_rows: int, sample_violations: list[dict] | None = None,
                   source=None, request_id=None, error_code=None)
```

`to_dict()` adds `schema_id, asserted_range (as list), violating_rows, sample_violations`.

### 8.7 `PayloadTooLargeError`

```python
PayloadTooLargeError(message, *, declared_size: int, limit: int,
                     accepted_modes: list[str] | None = None,
                     source=None, request_id=None, error_code=None)
```

`to_dict()` adds `declared_size, limit, accepted_modes`.

### 8.8 `TherminalError` (HTTP-layer marker)

```python
class TherminalError(TradewindsError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
```

Subclasses bind known status codes (404, 429, 400, 401, 403, 5xx). `RateLimitError` additionally carries `retry_after: int`. Not registered in `core/__init__.py.__all__`; importable from `tradewinds._internal.exceptions`.

### 8.9 `to_json_safe` coercion (`tradewinds/core/_json_safe.py`)

`to_dict()` returns JSON-safe payload via `to_json_safe(obj, seen=None)`. Rules:

- `pd.Timestamp` / `datetime.datetime` → ISO 8601 UTC string; naive → `{"_repr_only": True, "value": "<iso> (naive)"}`.
- `float NaN`, `inf`, `-inf`, `pd.NaT`, `pd.NA`, `None` → `None`.
- `np.bool_/integer/floating` → native Python.
- `np.ndarray` → recursive `list`.
- `dict | list | tuple` → recursive (tuples become lists). Cycles → `{"_cycle": True, "value": repr(obj)}`.
- Anything else → `{"_repr_only": True, "value": repr(obj)}`.
- Dict keys MUST be `str` (else `TypeError`).

---

## Appendix A — Source priorities (TS port: keep byte-exact)

```python
# tradewinds._internal.merge.observations.SOURCE_PRIORITY
{"awc": 3, "iem": 2, "ghcnh": 1}   # unknown → 0; strict ">" tiebreak; first-seen wins at equal

# tradewinds._internal.merge.climate.REPORT_TYPE_PRIORITY
{"final": 3.0, "ncei_final": 2.5, "correction": 2.0, "preliminary": 1.0, "estimated": 0.0}
# strict ">" — overnight final wins; first-seen wins at equal

# tradewinds.core.merge.LIVE_V1
ObservationMergePolicy(name="LIVE_V1",
                       source_priority={"awc": 3, "iem": 2, "ghcnh": 1, "ncei": 0},
                       secondary_key=("source_received_at", "ingestion_id"))
```

## Appendix B — Settlement-window math (TS port)

```python
LST offset = January UTC offset of station's IANA timezone (DST ignored)
settlement_date_for(as_of_utc, station) =  (as_of_utc + LST_offset).date()
settlement_window_utc(date_str, station) = (midnight_LST → UTC,
                                            midnight_LST + 24h → UTC)
cli_available_at(date_str, station, delay=10h) = window_end + delay
market_close_utc(date_str, station) =  (date_str + 16:30 LST) → UTC
```

`_JAN_REF = datetime(2024, 1, 15, 12, 0)` used as the offset-extraction reference.
`CLI_PUBLICATION_DELAY_HOURS = 10.0` (NWS overnight final ~04:00–10:00 UTC).

## Appendix C — Source ID vocabulary (Mode-2 dispatch)

Canonical source IDs flowing through `df.attrs["source"]`, schemas' `_registered_source`, catalog adapter dispatch:

- `iem.archive`, `iem.live` — IEM ASOS METAR/SPECI (parser: `_iem.iem_to_observation`)
- `awc.live` — AWC live METAR (parser: `_awc.awc_to_observation`)
- `ghcnh.archive` — NCEI GHCNh PSV (parser: `_ghcnh.parse_ghcnh_row`)
- `cli.archive`, `cli.live` — IEM CLI / NWS climate (parser: `_climate.parse_cli_record`)

Adapter projection (catalog/_obs_projection.PROJECTION_SPEC) renames + unit-converts:
- `station_code → station`
- `observed_at → event_time` (timestamp_utc)
- `temp_c → temp_c`, `dewpoint_c → dew_point_c`
- `wind_speed_kt → wind_speed_ms` (× `_KT_TO_MS = 0.514444…`)
- `wind_gust_kt → wind_gust_ms`
- `wind_dir_degrees → wind_dir_deg`
- `sea_level_pressure_mb → slp_hpa`
- `visibility_miles → visibility_m` (× 1609.344)
- `precip_1hr_inches → precip_mm_1h` (× 25.4)
- `sky_base_N_ft → sky_base_N_m` (× 0.3048)
- `raw_metar → metar_raw`

Overlay columns added by `add_overlay_columns`: `source`, `retrieved_at` (tz-aware UTC), `knowledge_time = event_time + lag`. Per-adapter lag:
- IEM: 15 min
- AWC: 5 min
- GHCNh: 6 h
- CLI: knowledge_time = `product_release_time` (parsed from product header)

## Appendix D — File map (most public files)

Public surface entry points:

- `packages/core/src/tradewinds/__init__.py` — public `research`, `__version__`
- `packages/core/src/tradewinds/research.py` — `research()` orchestrator
- `packages/core/src/tradewinds/snapshot.py` — `settlement_date_for`, `settlement_window_utc`, `cli_available_at`, `build_snapshot`, `DataSnapshot`, `_STATION_TZ`
- `packages/core/src/tradewinds/mode2.py` — `research_by_source`, `assert_source_identity`
- `packages/core/src/tradewinds/transforms.py` — 9 transforms
- `packages/core/src/tradewinds/qc.py` — `QCEngine`, `ALPHA_RULES`, `crosscheck_iem_ghcnh`
- `packages/core/src/tradewinds/discovery.py` — `availability`, `describe`, `feature_catalog`, top-level settlement wrappers, `DataVersion`
- `packages/core/src/tradewinds/international.py` — `INTERNATIONAL_STATIONS`, `daily_extremes`, `DeferredMarketError`
- `packages/core/src/tradewinds/forecasts.py` — `forecast_nwp`, `SUPPORTED_NWP_MODELS`
- `packages/core/src/tradewinds/core/__init__.py` — exports `validate_dataframe`, `Schema`, `ColumnSpec`, `SchemaRegistration`, `TimePoint`, `KnowledgeView`, `LeakageDetector`, `assert_no_leakage`, all 7 exception classes
- `packages/core/src/tradewinds/core/exceptions.py` — exception hierarchy
- `packages/core/src/tradewinds/core/validator.py` — `validate_dataframe`, `register_schema`
- `packages/core/src/tradewinds/core/schema.py` — Schema framework
- `packages/core/src/tradewinds/core/schemas/{observation,forecast,settlement,observation_ledger,observation_qc}.py` — 5 canonical schemas
- `packages/core/src/tradewinds/core/temporal/{timepoint,knowledge_view,leakage}.py` — temporal primitives
- `packages/core/src/tradewinds/core/formats/{dataframe,parquet,json,csv,toon}.py` — 5 format serializers
- `packages/core/src/tradewinds/core/merge.py` — `LIVE_V1`, `ObservationMergePolicy`, `query_time_merge`
- `packages/core/src/tradewinds/_internal/_stations.py` — `STATIONS` (20 US)
- `packages/core/src/tradewinds/_internal/_pairs.py` — `build_pairs`, `pairs_to_dataframe`, `market_close_utc`
- `packages/core/src/tradewinds/_internal/_convert.py` — unit conversions
- `packages/core/src/tradewinds/_internal/_bounds.py` — bounds constants + path validators
- `packages/core/src/tradewinds/_internal/_http.py` — `download_with_retry`
- `packages/core/src/tradewinds/_internal/versioning.py` — `DataVersion` (v1 shape)
- `packages/core/src/tradewinds/_internal/exceptions.py` — Therminal HTTP exceptions
- `packages/core/src/tradewinds/_internal/models/observation.py` — `Observation` dataclass
- `packages/core/src/tradewinds/_internal/models/station.py` — public `StationInfo` (v2)
- `packages/core/src/tradewinds/_internal/merge/{observations,climate,_schemas}.py` — merge policies + pyarrow schemas
- `packages/weather/src/tradewinds/weather/_fetchers/{awc,iem_asos,iem_cli,ghcnh,_iem_chunks}.py` — HTTP fetchers
- `packages/weather/src/tradewinds/weather/{_awc,_iem,_climate,_ghcnh}.py` — parsers
- `packages/weather/src/tradewinds/weather/cache.py` — parquet cache
- `packages/weather/src/tradewinds/weather/catalog/{__init__,_obs_projection,iem,awc,ghcnh,cli}.py` — catalog adapters
- `packages/markets/src/tradewinds/markets/polymarket.py` — Polymarket stub + boundary
- `packages/markets/src/tradewinds/markets/catalog/{kalshi_stations,kalshi_nhigh,kalshi_nlow}.py` — Kalshi metadata
