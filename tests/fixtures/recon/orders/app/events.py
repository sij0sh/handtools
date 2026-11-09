"""Announce new orders. Payload shape: schemas/order_created.v1.json."""
import json

from kafka import KafkaProducer

SCHEMA = 'schemas/order_created.v1.json'
producer = KafkaProducer(bootstrap_servers='kafka:9092')


def publish_order_created(order):
    message = {'order_id': order['id'], 'total_cents': order['total_cents'], 'currency': order['currency']}
    producer.send('orders.created', json.dumps(message).encode())
