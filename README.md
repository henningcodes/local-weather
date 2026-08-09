# local-weather

3-day ECMWF HRES forecast (temperature, precipitation, sunshine, wind) for
Essen-Bredeney, auto-published to GitHub Pages.

GitHub Actions runs `make_html.py` twice a day (08:00 and 20:00 UTC — safely
after the 00Z and 12Z ECMWF runs are available on Open-Meteo) and deploys
the generated `site/` to Pages. change so that it stays online

## Local development

```
uv run python weather_bredeney_hres.py   # hourly + daily table in terminal
uv run python make_html.py               # builds site/index.html
```

## Wind / terrace advice

Each page carries a traffic-light verdict ("Terrasse · nächste 24 h") plus a
per-day wind block: can the parasol stay open, or does it need folding?

The advice keys off **gusts** (`wind_gusts_10m`), not mean wind — gusts are what
actually catch a parasol. Thresholds live in `TERRACE_LEVELS` in
`weather_bredeney_hres.py` and are gust values in km/h, *not* Beaufort bounds:
gusts typically run 1.5–2× the mean wind, so applying the Beaufort table to them
directly would warn far too early. Beaufort shown on the page is derived from the
mean wind, which is where it is defined.

Changing `TERRACE_LEVELS` updates the verdict, the per-day cards, the chart's
threshold lines and the legend table together — they are all derived from it.

## Configuration

Edit the constants at the top of `weather_bredeney_hres.py` (`LAT`, `LON`,
`LOCATION`, `MODEL`) to point at a different location or model.

## Data source

[Open-Meteo](https://open-meteo.com) serving the ECMWF IFS 0.25° deterministic
run (HRES). The first day of the forecast is still a model prediction, not an
observation.
