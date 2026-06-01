"""
examples/market_summary.py
Downloads IBOV and S&P500 data via yfinance and saves a summary report.

Requires: pip install yfinance

Usage:
    python examples/market_summary.py
    python examples/market_summary.py --report-file logs/market_summary.txt
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf


TICKERS = {
    "IBOV":   "^BVSP",
    "S&P500": "^GSPC",
}


def fetch_variations(symbol: str) -> dict:
    data = yf.download(symbol, period="2mo", interval="1d", progress=False, auto_adjust=True)
    if data.empty or len(data) < 2:
        raise ValueError(f"insufficient data for {symbol}")

    close = data["Close"].squeeze()
    last   = float(close.iloc[-1])
    prev   = float(close.iloc[-2])
    week   = float(close.iloc[-6])  if len(close) >= 6  else prev
    month  = float(close.iloc[-22]) if len(close) >= 22 else prev

    def pct(a, b):
        return (a - b) / b * 100

    return {
        "last":  last,
        "day":   pct(last, prev),
        "week":  pct(last, week),
        "month": pct(last, month),
    }


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def fmt_number(v: float) -> str:
    return f"{v:,.0f}"


def build_report(results: dict) -> str:
    lines = []
    lines.append(f"Market Summary — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("-" * 52)
    lines.append(f"{'Index':<10} {'Last':>12} {'Day':>8} {'Week':>8} {'Month':>8}")
    lines.append("-" * 52)
    for name, r in results.items():
        lines.append(
            f"{name:<10} {fmt_number(r['last']):>12} "
            f"{fmt_pct(r['day']):>8} {fmt_pct(r['week']):>8} {fmt_pct(r['month']):>8}"
        )
    lines.append("-" * 52)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-file", default="logs/market_summary.txt")
    args = parser.parse_args()

    results = {}
    for name, symbol in TICKERS.items():
        try:
            results[name] = fetch_variations(symbol)
        except Exception as e:
            print(f"[ERROR] failed to fetch {name} ({symbol}): {e}")
            sys.exit(1)

    report = build_report(results)
    print(report)

    report_path = Path(args.report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nreport saved to {report_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()