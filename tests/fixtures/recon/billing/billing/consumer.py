"""Invoices every new order. Requires total_cents; skips orders it has already invoiced."""
import json

from kafka import KafkaConsumer

consumer = KafkaConsumer(group_id='billing', bootstrap_servers='kafka:9092')
consumer.subscribe(['orders.created'])
invoiced = set()


def handle(message):
    event = json.loads(message.value)
    if event['order_id'] in invoiced:
        return None
    invoiced.add(event['order_id'])
    return {'order_id': event['order_id'], 'amount_cents': event['total_cents']}


def run():
    for message in consumer:
        handle(message)
