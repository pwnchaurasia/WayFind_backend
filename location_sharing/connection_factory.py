from location_sharing.in_memory_conn_manager import InMemoryConnectionManager
from location_sharing.redis_conn_manager import RedisConnectionManager


class ConnectionManagerFactory:
    def __init__(self, use_redis: bool = False):
        self.use_redis = use_redis

    def get_manager(self):
        if self.use_redis:
            return RedisConnectionManager()
        else:
            return InMemoryConnectionManager()