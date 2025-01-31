import time
from utils.conn import RabbitMQConn



class RabbitMQConsumer:
    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.conn = RabbitMQConn()
        self.connection = None
        self.channel = None
        self.reconnect()

    def reconnect(self):
        """Reconnects to RabbitMQ if connection is lost"""
        while True:
            try:
                self.connection = self.conn.get_connection()
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue_name, durable=True)  # Queue is persistent
                break
            except Exception as e:
                print(f" [!] Connection failed, retrying in 5s: {e}")
                time.sleep(5)


    def process_message(self, ch, method, properties, body):
        print(f" [x] Received: {body.decode()}")

    def start_consuming(self):
        """Runs indefinitely to listen for messages on a specific queue."""
        self.channel.basic_consume(queue=self.queue_name,
                                   on_message_callback=self.process_message,
                                   auto_ack=True)
        print(f" [*] Waiting for messages in queue '{self.queue_name}'. Press CTRL+C to stop.")

        while True:
            try:
                self.channel.start_consuming()
            except Exception as e:
                print(f" [!] Consumer error: {e}, reconnecting...")
                self.reconnect()


"""

consumer1 = RabbitMQConsumer("high_priority_tasks")
consumer1.start_consuming()  # Runs for high-priority tasks

consumer2 = RabbitMQConsumer("low_priority_tasks")
consumer2.start_consuming()  # Runs for low-priority tasks

consumer3 = RabbitMQConsumer("scheduled_jobs")
consumer3.start_consuming()  # Runs for scheduled jobs

"""