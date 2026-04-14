# metar-display

A compact, cross-platform command-line client for displaying recent METAR observations from [aviationweather.gov](https://aviationweather.gov/data/api/).

---

## Technical Requirements

| Item | Detail |
|---|---|
| Python version | **3.9 or later** (`zoneinfo` was added in 3.9) |
| Non-standard libraries | None — uses the standard library only |
| Network access | HTTPS connection to `aviationweather.gov` |

Standard library modules used: `argparse`, `json`, `urllib`, `zoneinfo`, `pathlib`, `datetime`, `collections`.

---

## User Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--stations` | `str` | *(none)* | Comma-delimited list of up to 3 four-character station identifiers (letters and numbers), e.g. `CYXY,CFA5`. Required unless `--config` is provided. |
| `--config` | `str` (file path) | *(none)* | Path to a plain-text file containing station codes. Codes may be separated by commas or whitespace; `#` starts a comment. Required unless `--stations` is provided. Both options may be combined. |
| `--hours` | `int` | `25` | Number of hours of observations to return, from `1` to `48`. |
| `--order` | `str` | `desc` | Time-sort order for observations: `desc` (most recent first) or `asc` (oldest first). |
| `--timezone` | `str` | `utc` | Timezone for displayed observation times. Accepts IANA zone names (e.g. `America/Vancouver`) or common abbreviations (e.g. `pst`, `pdt`, `mst`, `est`, `utc`). |

### Station code file format

```text
# Stations of interest
CYXY          # Whitehorse
CFA5          # Grande Prairie area pseudo-ICAO
CYVR, CYYZ    # Vancouver and Toronto
```

---

## Output Format

Each requested station is printed with a compact header, followed by one line per observation:

```
ICAO | Name, Province, Country | lat lon | elev Xm
YYYY-MM-DD HH:MM TZ | TYPE | cat CAT | temp TC/DC | wind DDD@SSkt | vis VSM | slp P hPa | wx WX | cld LAYERS [| prcp Xmm] [| pcp3h Xmm] [| pcp6h Xmm] [| snow Xcm] [| rmk REMARKS]
```

Fields in `[]` are only shown when available in the data.

---

## Examples

### 1 — Simplest: one station, all defaults

```bash
python metar-cli.py --stations CYXY
```

Returns the past 25 hours of METARs for Whitehorse, displayed in UTC, most recent first.

---

### 2 — One station, custom hours

```bash
python metar-cli.py --stations CYVR --hours 6
```

Returns the past 6 hours for Vancouver International.

---

### 3 — One station, local timezone

```bash
python metar-cli.py --stations CYVR --timezone America/Vancouver
```

Timestamps are shown in Pacific time (automatically uses PDT or PST depending on the date).

---

### 4 — Multiple stations from command line

```bash
python metar-cli.py --stations CYXY,CFA5,CYYZ --hours 12 --order asc
```

Returns 12 hours of METARs for Whitehorse, a pseudo-ICAO station (CFA5), and Toronto, sorted oldest-first.

---

### 5 — All options specified, using a config file

```bash
python metar-cli.py --config stations.txt --hours 48 --order desc --timezone pst
```

Reads station codes from `stations.txt`, returns up to 48 hours of observations per station, most recent first, with times displayed in PST (UTC−8).

---

### 6 — Config file combined with a command-line station

```bash
python metar-cli.py --config stations.txt --stations CYOW --hours 3 --timezone est
```

Combines stations from the config file with CYOW (Ottawa), returning the past 3 hours in Eastern Standard Time.
