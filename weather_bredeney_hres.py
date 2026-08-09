"""
Pulls the ECMWF HRES (IFS deterministic, 9 km) forecast for Essen-Bredeney
for the next 3 days from Open-Meteo, prints an hourly + daily table and
saves a 4-panel chart (temperature, precipitation, sunshine, wind).

Usage: `uv run python weather_bredeney_hres.py`
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

LAT, LON = 51.413, 6.996  # Essen-Bredeney (default for standalone run)
LOCATION = "Essen"
MODEL = "ecmwf_ifs025"     # HRES deterministic
TZ = "Europe/Berlin"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

# Böen-Schwellen (km/h) für Terrassen-Mobiliar. Was den Schirm umwirft, ist die BÖE,
# nicht das Mittel — die Einschätzung hängt deshalb an wind_gusts_10m.
# WICHTIG: Das sind BÖEN-Werte, keine Beaufort-Grenzen. Böen liegen typisch beim
# 1,5- bis 2-fachen des Mittelwinds; die Beaufort-Tabelle direkt auf Böen anzuwenden
# warnt viel zu früh (25 km/h Böe ≈ Bft 2-3 im Mittel — da passiert nichts).
TERRACE_LEVELS = [
    (25, "ok",     "Schirm kann offen bleiben"),
    (45, "warn",   "Schirm zuklappen"),
    (65, "alert",  "Schirm zu, Leichtes reinholen"),
    (999, "danger", "Alles sichern und reinholen"),
]

COMPASS_DE = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]


def terrace_advice(gust_kmh: float) -> tuple[str, str]:
    """(level, Klartext) für die stärkste Böe eines Zeitraums."""
    for limit, level, text in TERRACE_LEVELS:
        if gust_kmh < limit:
            return level, text
    return TERRACE_LEVELS[-1][1], TERRACE_LEVELS[-1][2]


def beaufort(kmh: float) -> int:
    """Beaufort-Stufe aus km/h (v = 3.01 * Bft^1.5, nach Windstärke aufgelöst)."""
    for bft in range(12, -1, -1):
        if kmh >= 3.01 * bft ** 1.5:
            return bft
    return 0


def compass(deg: float) -> str:
    """Windrichtung als Kompass-Kürzel (meteorologisch: Richtung, aus der es weht)."""
    if deg != deg:  # NaN
        return "—"
    return COMPASS_DE[int(deg % 360 / 45 + 0.5) % 8]


def fetch_hres(lat: float = LAT, lon: float = LON, days: int = 3) -> pd.DataFrame:
    start = datetime.now(ZoneInfo(TZ)).date()
    end = start + timedelta(days=days - 1)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ("temperature_2m,precipitation,sunshine_duration,"
                   "wind_speed_10m,wind_gusts_10m,wind_direction_10m"),
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
        "wind_kmh": h["wind_speed_10m"],      # Open-Meteo liefert km/h per Default
        "gust_kmh": h["wind_gusts_10m"],
        "wind_dir": h["wind_direction_10m"],
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
        "Wind_max_kmh": g["wind_kmh"].max().round(0),
        "Gust_max_kmh": g["gust_kmh"].max().round(0),
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
    out["wind_kmh"] = out["wind_kmh"].round(0).astype(int)
    out["gust_kmh"] = out["gust_kmh"].round(0).astype(int)
    out["wind_dir"] = out["wind_dir"].map(compass)
    out.index = out.index.strftime("%a %d.%m %H:%M")
    out.columns = ["T °C", "Niederschlag mm", "Sonne min", "Wind km/h", "Böe km/h", "Richtung"]
    print(out.to_string())

    gmax = df["gust_kmh"].max()
    wmax = df["wind_kmh"].max()
    level, text = terrace_advice(gmax)
    print(f"\n=== Terrasse ===\nStärkste Böe in 3 Tagen: {gmax:.0f} km/h  ·  "
          f"Mittelwind bis {wmax:.0f} km/h (Bft {beaufort(wmax)}) → {text} [{level}]")


def plot(df: pd.DataFrame, path: Path, title: str = LOCATION) -> None:
    plt.rcParams.update({
        "font.size": 13,
        "axes.titlesize": 14,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    fig, axes = plt.subplots(4, 1, figsize=(7, 13), sharex=True)

    ax = axes[0]
    ax.plot(df.index, df["temp_c"], color="#c0392b", lw=2.4)
    ax.fill_between(df.index, df["temp_c"], alpha=0.15, color="#c0392b")
    ax.set_ylabel("Temperatur [°C]")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"{title} — ECMWF HRES", pad=10)

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

    # Wind: Böe als Fläche (die entscheidet über den Schirm), Mittelwind als Linie.
    # Die waagerechten Linien sind die TERRACE_LEVELS-Schwellen.
    ax = axes[3]
    ax.fill_between(df.index, df["gust_kmh"], alpha=0.25, color="#16a085",
                    label="Böen")
    ax.plot(df.index, df["gust_kmh"], color="#16a085", lw=1.6)
    ax.plot(df.index, df["wind_kmh"], color="#34495e", lw=2.0, label="Mittelwind")
    gmax = float(df["gust_kmh"].max())
    # Eine Schwellenlinie markiert den UEBERGANG: beschriftet wird sie deshalb mit der
    # Empfehlung der naechsthoeheren Stufe (was gilt, sobald die Boeen drueber liegen).
    for (limit, _lvl, _below), (_nl, _nlvl, above) in zip(TERRACE_LEVELS[:-1],
                                                          TERRACE_LEVELS[1:]):
        if limit > gmax * 1.35:
            continue          # Schwellen weit über der Prognose nicht mitzeichnen
        ax.axhline(limit, color="#c0392b", lw=0.9, ls="--", alpha=0.55)
        ax.annotate(f"ab hier: {above}", (df.index[0], limit), xytext=(3, 3),
                    textcoords="offset points", fontsize=8, color="#c0392b", alpha=0.9)
    ax.set_ylabel("Wind [km/h]")
    ax.set_ylim(0, max(gmax * 1.2, 25))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.85)

    for ax in axes:
        for d in pd.date_range(df.index[0].normalize(),
                               df.index[-1].normalize() + pd.Timedelta(days=1),
                               freq="D"):
            ax.axvline(d, color="grey", lw=0.6, alpha=0.4)
    axes[-1].xaxis.set_major_locator(mdates.DayLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%a %d.%m"))
    axes[-1].xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    axes[-1].xaxis.set_minor_formatter(mdates.DateFormatter("%Hh"))
    axes[-1].tick_params(axis="x", which="major", pad=22, labelsize=11)
    axes[-1].tick_params(axis="x", which="minor", labelsize=9, colors="grey")

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    df = fetch_hres(days=3)
    print_tables(df)
    plot(df, OUT_DIR / "weather_bredeney_hres.png")
