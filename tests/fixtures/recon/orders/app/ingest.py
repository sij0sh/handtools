"""Hourly price import from the vendor feed (see deploy/cron.yaml)."""
import csv
import io
import sqlite3
from urllib.request import urlopen

FEED = 'https://feeds.example-vendor.com/v2/prices.csv'


def main():
    with urlopen(FEED, timeout=30) as response:
        rows = list(csv.DictReader(io.TextIOWrapper(response, encoding='utf-8')))
    with sqlite3.connect('orders.db') as conn:
        conn.executemany('INSERT OR REPLACE INTO prices (sku, cents) VALUES (:sku, :cents)', rows)


if __name__ == '__main__':
    main()
