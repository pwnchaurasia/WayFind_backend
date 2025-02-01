import os
import redis


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



class RedisHelper:
    def __init__(self):
        self.redis = RedisInstance()

    def set(self, key, value, expire=None):
        """Set a key-value pair with optional expiration."""
        return self.redis.set(key, value, ex=expire)

    def get(self, key):
        """Retrieve a value from Redis."""
        return self.redis.get(key)

    def delete(self, key):
        """Delete a key."""
        return self.redis.delete(key)

    def exists(self, key):
        """Check if a key exists."""
        return self.redis.exists(key)

    def set_with_ttl(self, key, value, ttl_seconds):
        """Set a key with expiration (TTL)."""
        return self.redis.setex(key, ttl_seconds, value)

    def increment(self, key, amount=1):
        """Increment key's value."""
        return self.redis.incr(key, amount)

    def decrement(self, key, amount=1):
        """Decrement key's value."""
        return self.redis.decr(key, amount)

    def flush_all(self):
        """Flush all Redis keys (dangerous)."""
        return self.redis.flushall()