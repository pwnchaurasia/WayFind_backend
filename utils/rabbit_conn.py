import os

import pika


class RabbitMQConn:
    __instance = None  # Singleton instance

    def __new__(cls):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(RabbitMQConn, cls).__new__(cls)

            cls.__instance.credentials = pika.PlainCredentials(
                os.getenv("RABBITMQ_USER"),
                os.getenv("RABBITMQ_PASS")
            )
            cls.__instance.parameters = pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST"),
                credentials=cls.__instance.credentials
            )

        return cls.__instance

    def get_connection(self):
        """Create a new RabbitMQ connection (not shared)"""
        return pika.BlockingConnection(self.parameters)