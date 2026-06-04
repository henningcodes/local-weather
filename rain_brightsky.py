"""
DWD precipitation via Bright Sky: the last 14 days (measured) plus a 5-day
forecast for one location. Feeds the precipitation section that sits below the
ECMWF forecast on the HTML page, and runs standalone as a console table + chart.

Unlike weather_bredeney_hres.py (Open-Meteo / ECMWF HRES, pure forecast), this
uses DWD station data through https://brightsky.dev, so it also shows the rain
that has actually fallen. Chart styling mirrors weather_bredeney_hres.plot().

Usage: `uv run python rain_brightsky.py`
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd
import requests

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

TZ = "Europe/Berlin"
LAT, LON = 51.413, 6.996   # Essen-Bredeney (default for standalone run)
LOCATION = "Essen"

HISTORY_DAYS = 14          # measured days shown before today
FORECAST_DAYS = 5          # forecast days shown after today
DETAIL_BACK = 2            # last N days rendered in 6-hour blocks

RAIN = "#2980b9"           # same blue as the ECMWF precip panel
RAIN_FC = "#9ecae1"        # lighter blue: forecast / not yet measured

OUT_DIR = Path("data")


# ------------------------------------------------------------
# Status: realisiert (measured) / gemischt (today) / prognose (forecast)
# ------------------------------------------------------------

def day_status(d, today):
    if d < today:
        return "realisiert"
    if d == today:
        return "gemischt"
    return "prognose"


def interval_status(start_ts, end_ts, now):
    if end_ts <= now:
        return "realisiert"
    if start_ts >= now:
        return "prognose"
    return "gemischt"


# ------------------------------------------------------------
# Bright Sky fetch
# ------------------------------------------------------------

def fetch_rain(lat: float = LAT, lon: float = LON, tz: str = TZ) -> pd.Series:
    """Hourly precipitation [mm] over the history + forecast window."""
    today = datetime.now(ZoneInfo(tz)).date()
    start = today - timedelta(days=HISTORY_DAYS)
    end = today + timedelta(days=FORECAST_DAYS)

    r = requests.get(
        "https://api.brightsky.dev/weather",
        params={
            "lat": lat, "lon": lon,
            "date": start.isoformat(),
            "last_date": end.isoformat(),
            "tz": tz,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame(data["weather"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(tz)
    df = df.set_index("timestamp").sort_index()

    rain = df["precipitation"].fillna(0.0)
    rain.attrs["sources"] = data.get("sources", [])
    return rain


# ------------------------------------------------------------
# Aggregations for chart + tables
# ------------------------------------------------------------

def daily_frame(rain: pd.Series, tz: str = TZ) -> pd.DataFrame:
    """One row per calendar day: mm total and status."""
    today = pd.Timestamp.now(tz=tz).date()
    daily = rain.groupby(rain.index.normalize()).sum()
    df = daily.to_frame("mm")
    df["status"] = [day_status(ts.date(), today) for ts in df.index]
    return df


def detail_blocks(rain: pd.Series, tz: str = TZ) -> list:
    """6-hour blocks (00-06, 06-12, 12-18, 18-24) + daily total for the
    last DETAIL_BACK days, today and tomorrow."""
    today = pd.Timestamp.now(tz=tz).date()
    now = pd.Timestamp.now(tz=tz)

    detail_start = today - timedelta(days=DETAIL_BACK)
    detail_end = today + timedelta(days=1)   # tomorrow, inclusive

    blocks = []
    for day_start in pd.date_range(detail_start, detail_end, freq="D", tz=tz):
        d = day_start.date()
        day_end = day_start + pd.Timedelta(days=1)
        day_data = rain[(rain.index >= day_start) & (rain.index < day_end)]
        if day_data.empty:
            continue

        rows = []
        for ts, val in day_data.resample("6h", label="left", closed="left").sum().items():
            if ts.date() != d:
                continue
            end_ts = ts + pd.Timedelta(hours=6)
            rows.append({
                "window": f"{ts.hour:02d}–{ts.hour + 6:02d}",
                "mm": float(val),
                "status": interval_status(ts, end_ts, now),
            })

        blocks.append({
            "date": d,
            "total_mm": float(day_data.sum()),
            "status": day_status(d, today),
            "rows": rows,
        })
    return blocks


# ------------------------------------------------------------
# Chart — same look as weather_bredeney_hres.plot()
# ------------------------------------------------------------

def plot_rain(rain: pd.Series, path: Path, title: str = LOCATION,
              tz: str = TZ) -> None:
    df = daily_frame(rain, tz)

    plt.rcParams.update({
        "font.size": 13,
        "axes.titlesize": 14,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    fig, ax = plt.subplots(figsize=(7, 3.6))

    colors = [RAIN_FC if s == "prognose" else RAIN for s in df["status"]]
    ax.bar(df.index, df["mm"], width=0.8, color=colors,
           align="center", edgecolor="none")

    ax.set_ylabel("Niederschlag [mm/Tag]")
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_title(f"{title} — Niederschlag (DWD)", pad=10)

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")

    ax.legend(
        handles=[Patch(color=RAIN, label="gemessen"),
                 Patch(color=RAIN_FC, label="Prognose")],
        frameon=False, fontsize=10, loc="upper left",
    )

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(f"wrote {path}")


# ------------------------------------------------------------
# Standalone run
# ------------------------------------------------------------

def print_table(rain: pd.Series) -> None:
    df = daily_frame(rain).copy()
    df.index = [f"{ts.strftime('%a %d.%m')}" for ts in df.index]
    df["mm"] = df["mm"].round(1)
    print(f"\nNiederschlag (DWD / Bright Sky) — {LOCATION}")
    print(f"Letzte {HISTORY_DAYS} Tage + {FORECAST_DAYS} Tage Prognose   TZ: {TZ}\n")
    print(df.to_string())


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    rain = fetch_rain()
    print_table(rain)
    plot_rain(rain, OUT_DIR / "rain_brightsky.png")
