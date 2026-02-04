# strike-selector

Select mini futures based on your risk, stop, and target levels. The CLI ranks the closest knock-out to your stop and shows the top 3 by default.

## Quick start

1. Create a virtual environment
2. Install

```bash
python -m pip install -e .
```

3. Run with a manual price

```bash
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url
```

## Avanza price (optional)

If you want to fetch the underlying price from Avanza, install the optional dependencies:

```bash
python -m pip install -e .[avanza]
```

The CLI will try `python-avanza` first and fall back to `avanzapy` if needed.

Then run:

```bash
strike-selector \
  --avanza-id 5361 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url
```

## Mini future data sources

This project currently supports:

- Vontobel product download CSV (auto-download or local file)
- Vontobel product overview API (scraped via the public site API)

If the download fails (or returns HTML due to a disclaimer), you can either:

- Pass a cookie string (copied from your browser after accepting the disclaimer), or
- Manually download the CSV from [Vontobel's product download page](https://markets.vontobel.com/en-ch/product-download) and pass the file path.

Example with cookie:

```bash
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url \
  --vontobel-cookie "cookie_name=cookie_value; other_cookie=other_value"
```

If you prefer not to paste cookies or URLs on the command line, you can store them in files or env vars:

```bash
# file-based
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url-file /path/to/vontobel_url.txt \
  --vontobel-cookie-file /path/to/vontobel_cookie.txt

# env-based
export VONTOBEL_URL="https://..."
export VONTOBEL_COOKIE="cookie_name=cookie_value; other_cookie=other_value"
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url
```

You can also put them in a `.env` file and the CLI will load it automatically:

```bash
cat <<'EOF' > .env
VONTOBEL_URL="https://..."
VONTOBEL_COOKIE="cookie_name=cookie_value; other_cookie=other_value"
EOF

strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-url
```

Manual CSV:

```bash
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-csv /path/to/export.csv

Tip: if the download still fails, open your browser DevTools Network tab, click "Product overview as CSV,"
and copy the full request URL and Cookie header. Pass them with `--vontobel-url` and `--vontobel-cookie`.

## Vontobel product overview API (no CSV required)

You can fetch mini futures directly from the Vontobel product overview API:

```bash
strike-selector \
  --price 100.50 \
  --underlying "ERIC B" \
  --risk 1000 \
  --stop 95 \
  --rr 2 \
  --vontobel-api \
  --vontobel-culture en-se
```

Optional tuning:

- `--vontobel-investor-type` (default `1` for private, `2` for professional)
- `--vontobel-page-size` (default `1000`)

## Ranking

- The tool filters out products whose knock-out is on the wrong side of your stop.
- It ranks by closest knock-out to your stop, then by leverage.
```

## Notes

- Mini futures and stock price data may be subject to provider terms of use.
- This is not financial advice.
