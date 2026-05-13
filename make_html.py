"""
Builds a static `site/` directory with the latest ECMWF HRES forecast for
Essen-Bredeney: chart PNG, daily summary cards, hourly tables.
Optimised for iPhone viewing (responsive, dark mode, safe-area aware).

Run by the GitHub Actions workflow twice a day; output is deployed to Pages.
Local run: `uv run python make_html.py` → open site/index.html.
"""
import locale
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weather_bredeney_hres import (
    LOCATION, MODEL, TZ, daily_summary, fetch_hres, plot,
)

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

# best-effort German weekday names
for loc in ("de_DE.UTF-8", "de_DE", "German_Germany.1252", "de"):
    try:
        locale.setlocale(locale.LC_TIME, loc)
        break
    except locale.Error:
        continue

SITE = Path("site")
SITE.mkdir(exist_ok=True)

WEEKDAY_DE = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}


HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f6f6f7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0d0d0d" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>{location}</title>
<style>
  :root {{
    --bg: #f6f6f7;
    --card: #ffffff;
    --text: #111;
    --text-dim: #6e6e73;
    --border: #e3e3e6;
    --temp: #c0392b;
    --rain: #2980b9;
    --sun:  #e69100;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #000;
      --card: #1c1c1e;
      --text: #f2f2f7;
      --text-dim: #98989e;
      --border: #2c2c2e;
      --temp: #ff6b5e;
      --rain: #5ac8fa;
      --sun:  #ffd60a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    font-size: 17px;
    line-height: 1.4;
    padding: max(env(safe-area-inset-top), 1.25rem) 1rem
             max(env(safe-area-inset-bottom), 1rem);
    max-width: 720px;
    margin: 0 auto;
  }}
  header {{ margin-bottom: 1.5rem; }}
  h1 {{
    font-size: 2rem; margin: 0 0 0.25rem;
    font-weight: 700; letter-spacing: -0.02em;
  }}
  .meta, .updated {{ color: var(--text-dim); font-size: 0.8rem; margin: 0; }}
  .updated {{ margin-top: 0.4rem; }}

  .cards {{ display: grid; gap: 0.75rem; margin-bottom: 1.5rem; }}
  .card {{
    background: var(--card);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    border: 0.5px solid var(--border);
  }}
  .card h2 {{
    font-size: 0.78rem; font-weight: 600;
    margin: 0 0 0.85rem;
    color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 0.06em;
  }}
  .card.today h2 {{ color: var(--temp); }}
  .stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.4rem;
  }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat .v {{
    font-size: 1.55rem; font-weight: 600;
    letter-spacing: -0.02em; line-height: 1.05;
    font-variant-numeric: tabular-nums;
  }}
  .stat .u {{ font-size: 0.75rem; color: var(--text-dim); font-weight: 500; }}
  .stat .l {{
    font-size: 0.66rem; color: var(--text-dim);
    margin-top: 0.35rem;
    text-transform: uppercase; letter-spacing: 0.05em;
  }}
  .stat.tmax .v {{ color: var(--temp); }}
  .stat.rain .v {{ color: var(--rain); }}
  .stat.sun  .v {{ color: var(--sun);  }}

  .chart {{
    background: var(--card);
    border: 0.5px solid var(--border);
    border-radius: 16px;
    padding: 0.5rem;
    margin-bottom: 1.5rem;
  }}
  .chart img {{ display: block; width: 100%; height: auto; border-radius: 10px; }}

  details {{
    background: var(--card);
    border: 0.5px solid var(--border);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin-bottom: 1.5rem;
  }}
  details summary {{
    cursor: pointer; user-select: none;
    font-weight: 600; font-size: 0.95rem;
    list-style: none; padding: 0.4rem 0;
    display: flex; justify-content: space-between; align-items: center;
  }}
  details summary::-webkit-details-marker {{ display: none; }}
  details summary::after {{
    content: "›"; color: var(--text-dim);
    font-size: 1.4rem; line-height: 1;
    transition: transform 0.2s;
  }}
  details[open] summary::after {{ transform: rotate(90deg); }}

  .day-block {{ margin-top: 1.25rem; }}
  .day-block:first-of-type {{ margin-top: 0.5rem; }}
  .day-block h3 {{
    font-size: 0.72rem; font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 0.06em;
    margin: 0 0 0.5rem;
  }}
  table {{
    width: 100%; border-collapse: collapse;
    font-variant-numeric: tabular-nums;
    font-size: 0.88rem;
  }}
  th, td {{
    padding: 5px 4px;
    border-bottom: 0.5px solid var(--border);
    text-align: right;
  }}
  th:first-child, td:first-child {{ text-align: left; color: var(--text-dim); }}
  th {{
    color: var(--text-dim); font-weight: 600;
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.04em;
    border-bottom-width: 1px;
  }}
  tbody tr:last-child td {{ border-bottom: none; }}

  footer {{
    color: var(--text-dim); font-size: 0.72rem;
    margin: 1.5rem 0 0;
    line-height: 1.5;
  }}
  footer a {{ color: var(--text-dim); }}
</style>
</head>
<body>
<header>
  <h1>{location}</h1>
  <p class="meta">ECMWF HRES · {lat:.2f}°N {lon:.2f}°E · {elev:.0f} m</p>
  <p class="updated">Aktualisiert {updated}</p>
</header>

<section class="chart">
  <img src="forecast.png" alt="3-Tages-Vorhersage" loading="lazy">
</section>

<section class="cards">{cards_html}</section>

<details>
  <summary>Stündliche Werte</summary>
  {hourly_html}
</details>

<footer>
  Daten: <a href="https://open-meteo.com">Open-Meteo</a> /
  <a href="https://www.ecmwf.int">ECMWF</a> · Modell: {model}<br>
  Der heutige Tag ist Modell-Forecast, keine Beobachtung.
</footer>
</body>
</html>
"""


def _day_label(d, today_date):
    if d == today_date:
        return "Heute"
    delta = (d - today_date).days
    if delta == 1:
        return "Morgen"
    if delta == 2:
        return "Übermorgen"
    return f"{WEEKDAY_DE[d.weekday()]} {d.strftime('%d.%m')}"


def build_cards(daily, today_date):
    blocks = []
    for d, row in daily.iterrows():
        cls = "card today" if d == today_date else "card"
        date_str = f"{WEEKDAY_DE[d.weekday()]} {d.strftime('%d.%m.')}"
        blocks.append(f"""
  <article class="{cls}">
    <h2>{_day_label(d, today_date)} · {date_str}</h2>
    <div class="stats">
      <div class="stat tmax"><span class="v">{row.Tmax_C:.0f}<span class="u">°</span></span><span class="l">max</span></div>
      <div class="stat tmin"><span class="v">{row.Tmin_C:.0f}<span class="u">°</span></span><span class="l">min</span></div>
      <div class="stat rain"><span class="v">{row.Precip_mm:.1f}<span class="u">mm</span></span><span class="l">Regen</span></div>
      <div class="stat sun"><span class="v">{row.Sun_h:.1f}<span class="u">h</span></span><span class="l">Sonne</span></div>
    </div>
  </article>""")
    return "\n".join(blocks)


def build_hourly(df, today_date):
    blocks = []
    for d, g in df.groupby(df.index.date):
        date_str = f"{WEEKDAY_DE[d.weekday()]} {d.strftime('%d.%m.')}"
        label = _day_label(d, today_date)
        rows = []
        for ts, r in g.iterrows():
            rows.append(
                f"<tr><td>{ts.strftime('%H:%M')}</td>"
                f"<td>{r.temp_c:.1f}°</td>"
                f"<td>{r.precip_mm:.1f}</td>"
                f"<td>{int(round(r.sun_min))}</td></tr>"
            )
        blocks.append(f"""
  <div class="day-block">
    <h3>{label} · {date_str}</h3>
    <table>
      <thead><tr><th>Uhr</th><th>Temp</th><th>mm</th><th>Sonne min</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>""")
    return "\n".join(blocks)


def build():
    df = fetch_hres(days=3)
    plot(df, SITE / "forecast.png")

    daily = daily_summary(df)
    today_date = df.index[0].date()

    html = HTML.format(
        location=LOCATION,
        lat=df.attrs["grid_lat"], lon=df.attrs["grid_lon"],
        elev=df.attrs["elevation"], model=MODEL,
        updated=datetime.now(ZoneInfo(TZ)).strftime("%d.%m.%Y %H:%M %Z"),
        cards_html=build_cards(daily, today_date),
        hourly_html=build_hourly(df, today_date),
    )
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote {SITE/'index.html'} + {SITE/'forecast.png'}")


if __name__ == "__main__":
    build()
