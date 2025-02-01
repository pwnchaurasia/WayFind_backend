import pika

from utils.rabbit_conn import RabbitMQConn




class RabbitMQProducer:

    def __init__(self):
        self.conn = RabbitMQConn()

    def publish(self, queue: str, message: str):
        """Publish a message to any RabbitMQ queue"""
        connection = self.conn.get_connection()  # Get a fresh connection
        channel = connection.channel()

        channel.queue_declare(queue=queue, durable=True)  # Ensures queue persists
        channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2  # Makes message persistent
            )
        )

        print(f" [x] Sent '{message}' to queue '{queue}'")
        connection.close()


    def close_connection(self):
        """Close RabbitMQ connection"""
        if self.connection:
            self.connection.close()
            print(" [x] RabbitMQ connection closed")



"""
Example: 

producer = RabbitMQProducer()
producer.publish("high_priority_tasks", "Urgent Task")
producer.publish("low_priority_tasks", "Non-Urgent Task")
producer.publish("scheduled_jobs", "Scheduled Task")

"""