import os
import redis
import pika
from utils import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
print(f"DB URL {DB_URL}")

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



class RedisInstance:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls.__instance = super(RedisInstance, cls).__new__(cls)
            db = redis.StrictRedis(
                host=os.getenv("REDIS_HOST"),
                port=os.getenv("REDIS_PORT"),
                decode_responses=True
            )
            cls._instance = db
        return cls._instance


class RabbitMQConn:
    __instance = None  # Singleton instance

    def __new__(cls):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(RabbitMQConn, cls).__new__(cls)

            cls.__instance.credentials = pika.PlainCredentials(
                os.getenv("RABBITMQ_USER", "user"),
                os.getenv("RABBITMQ_PASS", "password")
            )
            cls.__instance.parameters = pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "localhost"),
                credentials=cls.__instance.credentials
            )

        return cls.__instance

    def get_connection(self):
        """Create a new RabbitMQ connection (not shared)"""
        return pika.BlockingConnection(self.parameters)