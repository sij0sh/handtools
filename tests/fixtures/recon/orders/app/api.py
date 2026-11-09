from flask import Flask, request

from app import events, store

app = Flask(__name__)


@app.route('/orders', methods=['POST'])
def create_order():
    body = request.get_json()
    if not body or 'items' not in body:
        return {'error': 'items required'}, 400
    order = store.save_order(body)
    events.publish_order_created(order)
    return order, 201
