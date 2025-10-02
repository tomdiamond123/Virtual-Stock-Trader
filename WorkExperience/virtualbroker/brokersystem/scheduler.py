import os
import time
from decimal import Decimal
from typing import Optional, List

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from django.db import transaction
from django.utils import timezone

from brokersystem.models import Stock, PriceHistory
import os


FINNHUB_TOKEN = os.getenv("FINNHUB_API_KEY")
FINNHUB_BASE = "https://finnhub.io/api/v1"
# 50 calls/minute budget -> ~1.25 seconds between calls
REQUEST_SPACING_SEC = 1.25


class RateLimiter:
    """
    Simple pacing limiter: ensures at least REQUEST_SPACING_SEC passes
    between successive API calls (process-wide).
    """
    def __init__(self, min_interval_sec: float):
        self.min_interval = float(min_interval_sec)
        self._last = 0.0

    def wait(self):
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


def _fetch_quote(symbol: str, session: requests.Session, limiter: RateLimiter) -> Optional[Decimal]:
    """
    Call Finnhub /quote for a single symbol. Returns Decimal price or None on failure.
    """
    if not FINNHUB_TOKEN:
        raise RuntimeError("FINNHUB_API_KEY environment variable is not set")

    limiter.wait()
    try:
        resp = session.get(
            f"{FINNHUB_BASE}/quote",
            params={"symbol": symbol, "token": FINNHUB_TOKEN},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # Finnhub /quote fields: c=current, h=high, l=low, o=open, pc=prev close, t=timestamp
        price = data.get("c")
        if price is None or float(price) <= 0:
            return None
        return Decimal(str(float(price)))
    except Exception as e:
        print(f"[Finnhub] {symbol} failed: {e}")
        return None


def fetch_prices_job():
    """
    Fetch latest prices from Finnhub and store in PriceHistory.
    Respects 50 req/min by pacing each /quote call with ~1.25s spacing.
    """
    symbols = list(Stock.objects.values_list("symbol", flat=True))
    if not symbols:
        print("No symbols to fetch.")
        return

    session = requests.Session()
    limiter = RateLimiter(REQUEST_SPACING_SEC)
    now = timezone.now()

    est_seconds = len(symbols) * REQUEST_SPACING_SEC
    print(f"[{now:%H:%M:%S}] Fetching {len(symbols)} symbols via Finnhub (~{int(est_seconds)}s)…")

    ids = dict(Stock.objects.filter(symbol__in=symbols).values_list("symbol", "id"))
    batch_records: List[PriceHistory] = []

    for sym in symbols:
        price = _fetch_quote(sym, session, limiter)
        if price is None:
            continue
        batch_records.append(
            PriceHistory(
                stock_id=ids.get(sym),
                price=price,
                timestamp=now,  # one logical “cycle time”
            )
        )

        if len(batch_records) >= 500:
            with transaction.atomic():
                PriceHistory.objects.bulk_create(batch_records, ignore_conflicts=True)
            batch_records.clear()

    if batch_records:
        with transaction.atomic():
            PriceHistory.objects.bulk_create(batch_records, ignore_conflicts=True)

    print(f"[{timezone.now():%H:%M:%S}] Price fetch cycle complete.")


# ---- APScheduler wiring ----
scheduler = None

def start_scheduler():
    """
    Start the background scheduler (only once).
    We also set coalesce/max_instances so jobs won't overlap if a cycle runs long.
    """
    global scheduler
    if scheduler and scheduler.running:
        return

    scheduler = BackgroundScheduler(timezone="Europe/London")
    scheduler.add_job(
        fetch_prices_job,
        "interval",
        minutes=25,                 # adjust if you have lots of symbols
        id="fetch_prices",
        next_run_time=timezone.now(),  # fire once at startup
        replace_existing=True,
        coalesce=True,             # collapse missed runs into one
        max_instances=1,           # prevent overlapping runs
        misfire_grace_time=60,
    )
    scheduler.start()
    print("APScheduler started (Finnhub).")
