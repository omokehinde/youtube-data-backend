from urllib.parse import urlparse
import redis
import os
from config import Config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    _instance = None
    _redis_client = None

    @classmethod
    def get_client(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._redis_client

    def __init__(self):
        if RedisClient._redis_client is not None:
            return

        try:
            # Try to use REDIS_URL from environment (Render deployment)
            if Config.REDIS_URL and 'redis://' not in Config.REDIS_URL:
                # Parse Redis URL for Render
                url = urlparse(Config.REDIS_URL)
                RedisClient._redis_client = redis.Redis(
                    host=url.hostname,
                    port=url.port,
                    username=url.username,
                    password=url.password,
                    ssl=True,
                    ssl_cert_reqs=None,
                    decode_responses=True
                )
            else:
                # Local development configuration with connection pooling
                pool = redis.ConnectionPool(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
                RedisClient._redis_client = redis.Redis(connection_pool=pool)
            
            # Test the connection
            RedisClient._redis_client.ping()
            logger.info("Redis connection established successfully")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise