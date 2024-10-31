import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    DEBUG = False
    PORT = int(os.getenv('PORT', 5000))