import sqlite3

DB = 'orders.db'


def price_of(conn, sku):
    row = conn.execute('SELECT cents FROM prices WHERE sku = ?', (sku,)).fetchone()
    return row[0] if row else 0


def save_order(body):
    with sqlite3.connect(DB) as conn:
        total = sum(price_of(conn, item['sku']) * item.get('qty', 1) for item in body['items'])
        cur = conn.execute('INSERT INTO orders (total_cents, currency) VALUES (?, ?)', (total, 'USD'))
        return {'id': cur.lastrowid, 'total_cents': total, 'currency': 'USD'}
