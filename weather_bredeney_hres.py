"""
Pulls the ECMWF HRES (IFS deterministic, 9 km) forecast for Essen-Bredeney
for the next 3 days from Open-Meteo, prints an hourly + daily table and
saves a 3-panel chart (temperature, precipitation, sunshine).

Usage: `uv run python weather_bredeney_hres.py`
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

LAT, LON = 51.413, 6.996  # Essen-Bredeney
LOCATION = "Essen-Bredeney"
MODEL = "ecmwf_ifs025"     # HRES deterministic
TZ = "Europe/Berlin"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)


def fetch_hres(days: int = 3) -> pd.DataFrame:
    start = date.today()
    end = start + timedelta(days=days - 1)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,precipitation,sunshine_duration",
        "models": MODEL,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": TZ,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    h = j["hourly"]
    df = pd.DataFrame({
        "time": pd.to_datetime(h["time"]),
        "temp_c": h["temperature_2m"],
        "precip_mm": h["precipitation"],
        "sun_min": [s / 60.0 for s in h["sunshine_duration"]],
    }).set_index("time")
    df.attrs["grid_lat"] = j["latitude"]
    df.attrs["grid_lon"] = j["longitude"]
    df.attrs["elevation"] = j["elevation"]
    return df


def daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(df.index.date)
    return pd.DataFrame({
        "Tmin_C": g["temp_c"].min().round(1),
        "Tmax_C": g["temp_c"].max().round(1),
        "Tmean_C": g["temp_c"].mean().round(1),
        "Precip_mm": g["precip_mm"].sum().round(1),
        "Sun_h": (g["sun_min"].sum() / 60).round(1),
    })


def print_tables(df: pd.DataFrame) -> None:
    print(f"\nHRES (ECMWF IFS 0.25°) — {LOCATION}")
    print(f"Grid: {df.attrs['grid_lat']:.2f}°N / {df.attrs['grid_lon']:.2f}°E   "
          f"Elevation: {df.attrs['elevation']:.0f} m   TZ: {TZ}")
    print(f"Issued: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")

    print("=== Daily summary ===")
    print(daily_summary(df).to_string())

    print("\n=== Hourly ===")
    out = df.copy()
    out["temp_c"] = out["temp_c"].round(1)
    out["precip_mm"] = out["precip_mm"].round(2)
    out["sun_min"] = out["sun_min"].round(0).astype(int)
    out.index = out.index.strftime("%a %d.%m %H:%M")
    out.columns = ["T °C", "Niederschlag mm", "Sonne min"]
    print(out.to_string())


def plot(df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)

    ax = axes[0]
    ax.plot(df.index, df["temp_c"], color="#c0392b", lw=1.8)
    ax.fill_between(df.index, df["temp_c"], alpha=0.15, color="#c0392b")
    ax.set_ylabel("Temperatur [°C]")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"ECMWF HRES — {LOCATION}  ({df.attrs['grid_lat']:.2f}°N, "
                 f"{df.attrs['grid_lon']:.2f}°E, {df.attrs['elevation']:.0f} m)")

    ax = axes[1]
    ax.bar(df.index, df["precip_mm"], width=1/24, color="#2980b9",
           align="edge", edgecolor="none")
    ax.set_ylabel("Niederschlag [mm/h]")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.bar(df.index, df["sun_min"], width=1/24, color="#f39c12",
           align="edge", edgecolor="none")
    ax.set_ylabel("Sonne [min/h]")
    ax.set_ylim(0, 65)
    ax.grid(True, alpha=0.3)

    # day boundaries + labels
    for ax in axes:
        for d in pd.date_range(df.index[0].normalize(),
                               df.index[-1].normalize() + pd.Timedelta(days=1),
                               freq="D"):
            ax.axvline(d, color="grey", lw=0.6, alpha=0.4)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%a %d.%m"))
    axes[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    axes[-1].xaxis.set_minor_formatter(mdates.DateFormatter("%Hh"))
    axes[-1].tick_params(axis="x", which="major", pad=18, labelsize=10)
    axes[-1].tick_params(axis="x", which="minor", labelsize=7, colors="grey")

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    df = fetch_hres(days=3)
    print_tables(df)
    plot(df, OUT_DIR / "weather_bredeney_hres.png")
