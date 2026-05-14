"""
Builds a static `site/` directory with the latest ECMWF HRES forecast for
multiple cities. Generates one HTML page + one PNG per city, with a
top-right dropdown to switch between them. Default (index.html) is Essen.

Optimised for iPhone viewing (responsive, dark mode, safe-area aware).

Local run: `uv run python make_html.py` → open site/index.html.
"""
import locale
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weather_bredeney_hres import (
    MODEL, TZ, daily_summary, fetch_hres, plot,
)

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

for loc in ("de_DE.UTF-8", "de_DE", "German_Germany.1252", "de"):
    try:
        locale.setlocale(locale.LC_TIME, loc)
        break
    except locale.Error:
        continue

SITE = Path("site")
SITE.mkdir(exist_ok=True)

WEEKDAY_DE = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}

# Coordinates → snapped by Open-Meteo to the nearest 0.25° grid point.
CITIES = [
    {"slug": "essen",             "name": "Essen",             "lat": 51.413, "lon":  6.996, "default": True},
    {"slug": "tuebingen",         "name": "Tübingen",          "lat": 48.521, "lon":  9.058},
    {"slug": "hoehr-grenzhausen", "name": "Höhr-Grenzhausen",  "lat": 50.435, "lon":  7.670},
    {"slug": "potsdam",           "name": "Potsdam",           "lat": 52.391, "lon": 13.065},
]


HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f6f6f7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0d0d0d" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>{name}</title>
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
    --chevron: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'><path fill='%236e6e73' d='M6 8 0 0h12z'/></svg>");
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
      --chevron: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'><path fill='%2398989e' d='M6 8 0 0h12z'/></svg>");
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
  .topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.25rem;
  }}
  h1 {{
    font-size: 2rem; margin: 0;
    font-weight: 700; letter-spacing: -0.02em;
  }}
  .city-switcher {{
    -webkit-appearance: none;
    appearance: none;
    background-color: var(--card);
    background-image: var(--chevron);
    background-repeat: no-repeat;
    background-position: right 0.7rem center;
    background-size: 10px 7px;
    border: 0.5px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font: inherit;
    font-size: 0.95rem;
    font-weight: 500;
    padding: 0.55rem 1.9rem 0.55rem 0.85rem;
    cursor: pointer;
    min-height: 38px;
  }}
  .city-switcher:focus {{ outline: 2px solid var(--temp); outline-offset: 2px; }}
  .meta, .updated {{ color: var(--text-dim); font-size: 0.8rem; margin: 0; }}
  .updated {{ margin-top: 0.4rem; }}

  .chart {{
    background: var(--card);
    border: 0.5px solid var(--border);
    border-radius: 16px;
    padding: 0.5rem;
    margin-bottom: 1.5rem;
  }}
  .chart img {{ display: block; width: 100%; height: auto; border-radius: 10px; }}

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
  <div class="topbar">
    <h1>{name}</h1>
    <select class="city-switcher" aria-label="Stadt wählen"
            onchange="if(this.value)location.href=this.value">
{options}
    </select>
  </div>
  <p class="meta">ECMWF HRES · {lat:.2f}°N {lon:.2f}°E · {elev:.0f} m</p>
  <p class="updated">Aktualisiert {updated}</p>
</header>

<section class="chart">
  <img src="{png}" alt="3-Tages-Vorhersage" loading="lazy">
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


def _page_url(city):
    return "index.html" if city.get("default") else f"{city['slug']}.html"


def _options(current_slug):
    out = []
    for c in CITIES:
        sel = " selected" if c["slug"] == current_slug else ""
        out.append(f'      <option value="{_page_url(c)}"{sel}>{c["name"]}</option>')
    return "\n".join(out)


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


def build_city(city, updated_str, cache_buster):
    print(f"--- {city['name']} ---")
    df = fetch_hres(lat=city["lat"], lon=city["lon"], days=3)
    png_name = f"forecast_{city['slug']}.png"
    plot(df, SITE / png_name, title=city["name"])

    daily = daily_summary(df)
    today_date = df.index[0].date()

    html = HTML.format(
        name=city["name"],
        lat=df.attrs["grid_lat"], lon=df.attrs["grid_lon"],
        elev=df.attrs["elevation"], model=MODEL,
        updated=updated_str,
        png=f"{png_name}?v={cache_buster}",
        options=_options(city["slug"]),
        cards_html=build_cards(daily, today_date),
        hourly_html=build_hourly(df, today_date),
    )

    out = SITE / _page_url(city)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} + {SITE/png_name}")


def build():
    now = datetime.now(ZoneInfo(TZ))
    updated_str = now.strftime("%d.%m.%Y %H:%M %Z")
    cache_buster = now.strftime("%Y%m%d%H%M")
    for city in CITIES:
        build_city(city, updated_str, cache_buster)


if __name__ == "__main__":
    build()
