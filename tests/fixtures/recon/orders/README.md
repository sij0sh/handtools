# orders

Accepts orders over HTTP, stores them, and announces each new order on the `orders.created` topic.
An hourly job imports vendor prices.
