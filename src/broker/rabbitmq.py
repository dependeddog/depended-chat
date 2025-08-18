import aio_pika

from src.config import settings


class RabbitMQBroker:
    def __init__(self, url: str):
        self.url = url
        self._connection: aio_pika.RobustConnection | None = None

    async def connect(self) -> aio_pika.RobustConnection:
        if self._connection is None:
            self._connection = await aio_pika.connect_robust(self.url)
        return self._connection

    async def publish(self, queue: str, message: str) -> None:
        connection = await self.connect()
        channel = await connection.channel()
        await channel.default_exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=queue,
        )


broker = RabbitMQBroker(settings.rabbitmq_url)
