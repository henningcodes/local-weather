"""
Builds a static `site/` directory with the latest ECMWF HRES forecast for
Essen-Bredeney: chart PNG, daily summary table, hourly table.

Run by the GitHub Actions workflow twice a day; output is deployed to Pages.
Local run: `uv run python make_html.py` → open site/index.html.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from weather_bredeney_hres import (
    LOCATION, MODEL, TZ, daily_summary, fetch_hres, plot,
)

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

SITE = Path("site")
SITE.mkdir(exist_ok=True)


HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wetter {location} — ECMWF HRES</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  img {{ width: 100%; height: auto; border: 1px solid #ddd; border-radius: 6px; }}
  table {{ border-collapse: collapse; margin: 1rem 0; font-variant-numeric: tabular-nums; }}
  th, td {{ padding: 4px 10px; text-align: right; border-bottom: 1px solid #eee; }}
  th {{ background: #f4f4f4; }}
  td:first-child, th:first-child {{ text-align: left; }}
  details {{ margin-top: 1.5rem; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  footer {{ margin-top: 2rem; color: #888; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>{location}</h1>
<div class="meta">
  ECMWF HRES (IFS 0.25°) · Gitter {lat:.2f}°N {lon:.2f}°E · {elev:.0f} m · TZ {tz}<br>
  Aktualisiert: {updated} UTC
</div>

<img src="forecast.png" alt="3-Tages Vorhersage">

<h2>Tageszusammenfassung</h2>
{daily_html}

<details>
<summary>Stündliche Werte</summary>
{hourly_html}
</details>

<footer>
  Daten: <a href="https://open-meteo.com">Open-Meteo</a> · Modell: {model} ·
  Quelle: <a href="https://www.ecmwf.int">ECMWF</a>.
  Die "heutige" Zeile ist Modell-Forecast, keine Beobachtung.
</footer>
</body>
</html>
"""


def build():
    df = fetch_hres(days=3)
    plot(df, SITE / "forecast.png")

    daily = daily_summary(df)
    daily.index.name = "Datum"
    daily_html = daily.to_html(border=0, classes="daily")

    hourly = df.copy()
    hourly["temp_c"] = hourly["temp_c"].round(1)
    hourly["precip_mm"] = hourly["precip_mm"].round(2)
    hourly["sun_min"] = hourly["sun_min"].round(0).astype(int)
    hourly.columns = ["T °C", "Niederschlag mm", "Sonne min"]
    hourly.index = hourly.index.strftime("%a %d.%m %H:%M")
    hourly.index.name = "Zeit"
    hourly_html = hourly.to_html(border=0, classes="hourly")

    html = HTML.format(
        location=LOCATION,
        lat=df.attrs["grid_lat"], lon=df.attrs["grid_lon"],
        elev=df.attrs["elevation"], tz=TZ, model=MODEL,
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        daily_html=daily_html, hourly_html=hourly_html,
    )
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote {SITE/'index.html'} + {SITE/'forecast.png'}")


if __name__ == "__main__":
    build()
