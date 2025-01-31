import os

import redis


class RedisInstance:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            db = redis.StrictRedis(
                host=os.getenv("REDIS_HOST"),
                port=os.getenv("REDIS_PORT"),
                decode_responses=True
            )
            cls._instance = db
        return cls._instance




# Store a test key
red = RedisInstance()
red.set("ping", "pong")

# Retrieve and print it
print(red.get("ping"))  # Expected Output: "pong"