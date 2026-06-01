"""
examples/weather_summary.py
Fetches today's weather forecast via Open-Meteo (free, no API key required)
and saves a summary report.

No external dependencies — uses urllib from the standard library.

Usage:
    python examples/weather_summary.py
    python examples/weather_summary.py --city "Belo Horizonte" --lat -19.9191 --lon -43.9386
    python examples/weather_summary.py --report-file logs/weather_summary.txt
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode


def fetch_weather(lat: float, lon: float) -> dict:
    params = urlencode({
        "latitude":    lat,
        "longitude":   lon,
        "daily":       "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode",
        "timezone":    "auto",
        "forecast_days": 1,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    daily = data["daily"]
    return {
        "date":       daily["time"][0],
        "temp_max":   daily["temperature_2m_max"][0],
        "temp_min":   daily["temperature_2m_min"][0],
        "rain_prob":  daily["precipitation_probability_max"][0],
    }


def build_report(city: str, w: dict) -> str:
    lines = []
    lines.append(f"Weather Forecast — {city} — {w['date']}")
    lines.append("-" * 40)
    lines.append(f"  Max temperature : {w['temp_max']}°C")
    lines.append(f"  Min temperature : {w['temp_min']}°C")
    lines.append(f"  Rain probability: {w['rain_prob']}%")
    lines.append("-" * 40)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city",        default="Belo Horizonte")
    parser.add_argument("--lat",         type=float, default=-19.9191)
    parser.add_argument("--lon",         type=float, default=-43.9386)
    parser.add_argument("--report-file", default="logs/weather_summary.txt")
    args = parser.parse_args()

    try:
        weather = fetch_weather(args.lat, args.lon)
    except Exception as e:
        print(f"[ERROR] failed to fetch weather: {e}")
        sys.exit(1)

    report = build_report(args.city, weather)
    print(report)

    report_path = Path(args.report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nreport saved to {report_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()