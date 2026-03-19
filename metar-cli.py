# metar-cli.py
# Console client for displaying METAR observations in a compact and cross-platform mannner.
# michael.smith2@nrcan-rncan.gc.ca
# Written with assistance of CoPilot; reviewed by a human per GoC guidelines on AI use.

# Documentation including best practices and schema are at# https://aviationweather.gov/data/api/#schema
# This script follows the above best practices as of March 2026.

# Force runtime eval of type annotations. 
from __future__ import annotations

import argparse
import json
import socket
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Iterable, Sequence
from urllib import error, parse, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# User options.
# Best practices recommend using a custom User-Agent string that identifies the application and provides a contact URL.
# DEFAULT_HOURS: Default # of hours to display
# MAX_HOURS: Max hours to request, per station. API allows up to 100 requests/minute
# MAX_STATIONS: Arbitrary, but will be affected by the max API rate. Suggest keeping it to <=3.
# DEFAULT_TIMEOUT_SECONDS: Arbitrary, but may need to be increased if the API is slow to respond. The API is generally fast, but network conditions can vary.
# USER_AGENT: Custom UA as suggested by Aviationweather.gov best practices.
# TIMEZONE_ALIASES: Any IANA compliant TZ (America/Vancouver) will be accepted, but some common abbreviations are mapped so that they can also be used.
API_URL = "https://aviationweather.gov/api/data/metar"
DEFAULT_HOURS = 25
MAX_HOURS = 48
MAX_STATIONS = 3
DEFAULT_TIMEOUT_SECONDS = 5 # May have to increase
USER_AGENT = "metar-display/1.0 (+https://aviationweather.gov/data/api/)"
TIMEZONE_ALIASES = {
	"utc": timezone.utc,
	"gmt": timezone.utc,
	"pst": timezone(timedelta(hours=-8), name="PST"),
	"pdt": timezone(timedelta(hours=-7), name="PDT"),
	"mst": timezone(timedelta(hours=-7), name="MST"),
	"mdt": timezone(timedelta(hours=-6), name="MDT"),
	"cst": timezone(timedelta(hours=-6), name="CST"),
	"cdt": timezone(timedelta(hours=-5), name="CDT"),
	"est": timezone(timedelta(hours=-5), name="EST"),
	"edt": timezone(timedelta(hours=-4), name="EDT"),
	"akst": timezone(timedelta(hours=-9), name="AKST"),
	"akdt": timezone(timedelta(hours=-8), name="AKDT"),
	"hst": timezone(timedelta(hours=-10), name="HST"),
}

# Parse input args.
def parse_args(argv: Sequence[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Display recent METAR observations for up to five ICAO stations "
			"using the aviationweather.gov data API."
		)
	)
	parser.add_argument(
		"--hours",
		type=int,
		default=DEFAULT_HOURS,
		help=f"Hours to return, from 1 to {MAX_HOURS}. Default: {DEFAULT_HOURS}.",
	)
	parser.add_argument(
		"--stations",
		help="Comma-delimited 4-letter ICAO station list, for example CYXY,CYVR.",
	)
	parser.add_argument(
		"--config",
		type=Path,
		help=(
			"Path to a text file containing station codes. Entries may be comma "
			"or whitespace separated, and '#' starts a comment."
		),
	)
	parser.add_argument(
		"--order",
		choices=("desc", "asc"),
		default="desc",
		help="Observation order by time. Default: desc.",
	)
	parser.add_argument(
		"--timezone",
		default="utc",
		help=(
			"Output timezone. Default: utc. Accepts IANA names such as "
			"America/Vancouver and common abbreviations such as pst or pdt."
		),
	)
	return parser.parse_args(argv)


def parse_station_tokens(raw_text: str) -> list[str]:
	station_codes: list[str] = []
	for line in raw_text.splitlines():
		content = line.split("#", 1)[0].strip()
		if not content:
			continue
		normalized = content.replace(",", " ")
		station_codes.extend(token.strip().upper() for token in normalized.split())
	return station_codes


def load_station_codes(args: argparse.Namespace) -> list[str]:
	collected: list[str] = []

	if args.config:
		try:
			collected.extend(parse_station_tokens(args.config.read_text(encoding="utf-8")))
		except FileNotFoundError as exc:
			raise SystemExit(f"Configuration file not found: {args.config}") from exc
		except OSError as exc:
			raise SystemExit(f"Unable to read configuration file {args.config}: {exc}") from exc

	if args.stations:
		collected.extend(parse_station_tokens(args.stations))

	if not collected:
		raise SystemExit("Provide station codes with --stations, --config, or both.")

	unique_codes: list[str] = []
	seen_codes: set[str] = set()
	for code in collected:
		validate_station_code(code)
		if code not in seen_codes:
			unique_codes.append(code)
			seen_codes.add(code)

	if len(unique_codes) > MAX_STATIONS:
		raise SystemExit(f"No more than {MAX_STATIONS} unique stations may be requested.")

	return unique_codes


def validate_station_code(code: str) -> None:
	if len(code) != 4 or not code.isalpha():
		raise SystemExit(f"Invalid station code '{code}'. Use 4-letter ICAO identifiers such as CYXY.")


def validate_hours(hours: int) -> None:
	if not 1 <= hours <= MAX_HOURS:
		raise SystemExit(f"--hours must be between 1 and {MAX_HOURS}.")


def resolve_timezone(timezone_name: str) -> tzinfo:
	normalized = timezone_name.strip()
	if not normalized:
		raise SystemExit("--timezone must not be empty.")

	alias = TIMEZONE_ALIASES.get(normalized.lower())
	if alias is not None:
		return alias

	try:
		return ZoneInfo(normalized)
	except ZoneInfoNotFoundError as exc:
		raise SystemExit(
			"Invalid timezone '{0}'. Use an IANA timezone such as "
			"America/Vancouver or a supported abbreviation such as pst, pdt, or utc.".format(timezone_name)
		) from exc


def build_request_url(station_codes: Sequence[str], hours: int) -> str:
	params = {
		"ids": ",".join(station_codes),
		"hours": str(hours),
		"format": "json",
	}
	return f"{API_URL}?{parse.urlencode(params)}"

# Build the URL, check the response and provide useful error messages if applicable.
def fetch_metars(station_codes: Sequence[str], hours: int) -> list[dict]:
	request_url = build_request_url(station_codes, hours)
	req = request.Request(
		request_url,
		headers={
			"Accept": "application/json",
			"User-Agent": USER_AGENT,
		},
		method="GET",
	)

	try:
		with request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
			status_code = getattr(response, "status", None)
			payload = response.read().decode("utf-8").strip()
	except error.HTTPError as exc:
		if exc.code == 204:
			return []
		if exc.code == 400:
			raise SystemExit("The API rejected the request. Check the station codes and hours value.") from exc
		if exc.code == 429:
			raise SystemExit("The API rate limit was exceeded. Wait before sending another request.") from exc
		raise SystemExit(f"The API returned HTTP {exc.code}: {exc.reason}") from exc
	except TimeoutError as exc:
		raise SystemExit(
			f"Request timed out after {DEFAULT_TIMEOUT_SECONDS} seconds. "
			"Please retry or increase DEFAULT_TIMEOUT_SECONDS."
		) from exc
	except socket.timeout as exc:
		raise SystemExit(
			f"Request timed out after {DEFAULT_TIMEOUT_SECONDS} seconds. "
			"Please retry or increase DEFAULT_TIMEOUT_SECONDS."
		) from exc
	except error.URLError as exc:
		if isinstance(exc.reason, TimeoutError):
			raise SystemExit(
				f"Request timed out after {DEFAULT_TIMEOUT_SECONDS} seconds. "
				"Please retry or increase DEFAULT_TIMEOUT_SECONDS."
			) from exc
		raise SystemExit(f"Unable to reach aviationweather.gov: {exc.reason}") from exc

	if status_code == 204 or not payload:
		return []

	try:
		data = json.loads(payload)
	except json.JSONDecodeError as exc:
		raise SystemExit(f"The API returned invalid JSON: {exc}") from exc

	if not isinstance(data, list):
		raise SystemExit("Unexpected API response format: expected a JSON array.")

	return [item for item in data if isinstance(item, dict)]

# Group observations for display in the case where multiple stations were requested.
def group_observations(observations: Iterable[dict], descending: bool) -> dict[str, list[dict]]:
	grouped: dict[str, list[dict]] = defaultdict(list)
	for observation in observations:
		station_code = str(observation.get("icaoId", "")).upper()
		if station_code:
			grouped[station_code].append(observation)

	for station_items in grouped.values():
		station_items.sort(key=observation_sort_key, reverse=descending)

	return dict(grouped)


def observation_sort_key(observation: dict) -> tuple[int, str]:
	obs_time = observation.get("obsTime")
	if isinstance(obs_time, (int, float)):
		return (int(obs_time), str(observation.get("reportTime", "")))
	return (0, str(observation.get("reportTime", "")))


def format_station_header(station_code: str, observations: Sequence[dict]) -> str:
	if not observations:
		return f"{station_code} | no observations returned"

	sample = observations[0]
	name = str(sample.get("name") or station_code)
	lat = format_coordinate(sample.get("lat"), "N", "S")
	lon = format_coordinate(sample.get("lon"), "E", "W")
	elev = format_elevation(sample.get("elev"))
	return f"{station_code} | {name} | {lat} {lon} | elev {elev}"


def format_coordinate(value: object, positive_suffix: str, negative_suffix: str) -> str:
	if not isinstance(value, (int, float)):
		return "n/a"
	suffix = positive_suffix if value >= 0 else negative_suffix
	return f"{abs(value):.3f}{suffix}"


def format_elevation(value: object) -> str:
	if not isinstance(value, (int, float)):
		return "n/a"
	return f"{int(round(value))} m"


def format_observation_line(observation: dict, output_timezone: tzinfo) -> str:
	report_time = format_report_time(observation, output_timezone)
	obs_type = str(observation.get("metarType") or "METAR")
	flight_category = str(observation.get("fltCat") or "-")
	temperature = format_temperature_pair(observation.get("temp"), observation.get("dewp"))
	wind = format_wind(observation)
	visibility = format_visibility(observation.get("visib"))
	slp = format_slp(observation.get("slp"))
	weather = str(observation.get("wxString") or "-")
	clouds = format_clouds(observation)
	remarks = extract_remarks(observation)

	parts = [
		report_time,
		obs_type,
		f"cat {flight_category}",
		f"temp {temperature}",
		f"wind {wind}",
		f"vis {visibility}",
		f"slp {slp}",
		f"wx {weather}",
		f"cld {clouds}",
	]
	parts.extend(format_precipitation(observation))
	if remarks:
		parts.append(f"rmk {remarks}")
	return " | ".join(parts)


def format_report_time(observation: dict, output_timezone: tzinfo) -> str:
	report_time = observation.get("reportTime")
	if isinstance(report_time, str):
		try:
			timestamp = datetime.fromisoformat(report_time.replace("Z", "+00:00"))
			return timestamp.astimezone(output_timezone).strftime("%Y-%m-%d %H:%M %Z")
		except ValueError:
			return report_time

	obs_time = observation.get("obsTime")
	if isinstance(obs_time, (int, float)):
		timestamp = datetime.fromtimestamp(obs_time, tz=timezone.utc)
		return timestamp.astimezone(output_timezone).strftime("%Y-%m-%d %H:%M %Z")

	return "unknown-time"


def format_temperature_pair(temp: object, dewpoint: object) -> str:
	return f"{format_number(temp)}C/{format_number(dewpoint)}C"


def format_number(value: object) -> str:
	if isinstance(value, int):
		return str(value)
	if isinstance(value, float):
		if value.is_integer():
			return str(int(value))
		return f"{value:.1f}"
	return "-"


def format_wind(observation: dict) -> str:
	direction = observation.get("wdir")
	speed = observation.get("wspd")
	gust = observation.get("wgst")

	if direction in (None, "VRB"):
		direction_text = "VRB"
	elif isinstance(direction, (int, float)):
		direction_text = f"{int(direction):03d}"
	else:
		direction_text = str(direction)

	if gust is None:
		return f"{direction_text}@{format_number(speed)}kt"
	return f"{direction_text}@{format_number(speed)}G{format_number(gust)}kt"


def format_visibility(value: object) -> str:
	if isinstance(value, int):
		return f"{value}SM"
	if isinstance(value, float):
		return f"{value:g}SM"
	return "-"


def format_slp(value: object) -> str:
	if isinstance(value, (int, float)):
		return f"{value:.1f} hPa"
	return "-"


# Precipitation values in the API are in inches.
# precip/pcp3hr/pcp6hr are converted to mm; snow is converted to cm.
def format_precipitation(observation: dict) -> list[str]:
	parts: list[str] = []

	precip = observation.get("precip")
	if isinstance(precip, (int, float)):
		parts.append(f"prcp {precip * 25.4:.1f}mm")

	pcp3hr = observation.get("pcp3hr")
	if isinstance(pcp3hr, (int, float)):
		parts.append(f"pcp3h {pcp3hr * 25.4:.1f}mm")

	pcp6hr = observation.get("pcp6hr")
	if isinstance(pcp6hr, (int, float)):
		parts.append(f"pcp6h {pcp6hr * 25.4:.1f}mm")

	snow = observation.get("snow")
	if isinstance(snow, (int, float)):
		parts.append(f"snow {snow * 2.54:.1f}cm")

	return parts


def format_clouds(observation: dict) -> str:
	layers = observation.get("clouds")
	if isinstance(layers, list) and layers:
		formatted_layers: list[str] = []
		for layer in layers:
			if not isinstance(layer, dict):
				continue
			cover = str(layer.get("cover") or "?")
			base = layer.get("base")
			if isinstance(base, (int, float)):
				formatted_layers.append(f"{cover}{int(round(base / 100.0)):03d}")
			else:
				formatted_layers.append(cover)
		if formatted_layers:
			return ",".join(formatted_layers)

	cover = observation.get("cover")
	if cover:
		return str(cover)
	return "-"


def extract_remarks(observation: dict) -> str:
	raw_observation = observation.get("rawOb")
	if not isinstance(raw_observation, str):
		return ""

	_, separator, remarks = raw_observation.partition(" RMK ")
	if not separator:
		return ""

	return remarks.strip()

# Render and print to cli
def render_report(station_codes: Sequence[str], grouped: dict[str, list[dict]], output_timezone: tzinfo) -> str:
	lines: list[str] = []
	for index, station_code in enumerate(station_codes):
		observations = grouped.get(station_code, [])
		if index:
			lines.append("")
		lines.append(format_station_header(station_code, observations))
		if observations:
			lines.extend(format_observation_line(observation, output_timezone) for observation in observations)
		else:
			lines.append("No observations available in the requested time window.")
	return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
	output_timezone = None
	args = parse_args(argv or sys.argv[1:])
	validate_hours(args.hours)
	output_timezone = resolve_timezone(args.timezone)
	station_codes = load_station_codes(args)
	observations = fetch_metars(station_codes, args.hours)
	grouped = group_observations(observations, descending=args.order == "desc")
	print(render_report(station_codes, grouped, output_timezone))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())