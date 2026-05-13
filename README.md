# local-weather

3-day ECMWF HRES forecast for Essen-Bredeney, auto-published to GitHub Pages.

GitHub Actions runs `make_html.py` twice a day (08:00 and 20:00 UTC — safely
after the 00Z and 12Z ECMWF runs are available on Open-Meteo) and deploys
the generated `site/` to Pages.

## Local development

```
uv run python weather_bredeney_hres.py   # hourly + daily table in terminal
uv run python make_html.py               # builds site/index.html
```

## Configuration

Edit the constants at the top of `weather_bredeney_hres.py` (`LAT`, `LON`,
`LOCATION`, `MODEL`) to point at a different location or model.

## Data source

[Open-Meteo](https://open-meteo.com) serving the ECMWF IFS 0.25° deterministic
run (HRES). The first day of the forecast is still a model prediction, not an
observation.
