from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

import redis
from config import Config
import googleapiclient.discovery
import googleapiclient.errors
import logging
from datetime import datetime
from redis_config import RedisClient
import time
import json

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# YouTube API configuration
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
API_KEY = Config.YOUTUBE_API_KEY
YOUTUBE_QUOTA_PER_DAY = 10000
QUOTA_COSTS = {
    "videos.list": 1,
    "commentThreads.list": 1
}

# Initialize YouTube API client
youtube = googleapiclient.discovery.build(
    API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)

class QuotaExceededError(Exception):
    pass

def track_quota(func_name):
    """Decorator to track API quota usage"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            redis_client = RedisClient.get_client()
            current_date = datetime.now().strftime("%Y-%m-%d")
            quota_key = f"youtube_quota:{current_date}"
            
            # Get current quota usage
            current_quota = int(redis_client.get(quota_key) or 0)
            quota_cost = QUOTA_COSTS.get(func_name, 1)
            
            if current_quota + quota_cost > YOUTUBE_QUOTA_PER_DAY:
                raise QuotaExceededError("Daily API quota exceeded")
            
            # Update quota usage
            pipe = redis_client.pipeline()
            pipe.incrby(quota_key, quota_cost)
            pipe.expire(quota_key, 86400)  # Expire after 24 hours
            pipe.execute()
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def cache_response(expiration=3600):
    """Enhanced caching decorator with error handling"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cache_key = f"{f.__name__}:{':'.join(str(arg) for arg in args)}:{':'.join(f'{k}={v}' for k, v in kwargs.items())}"
            redis_client = RedisClient.get_client()
            
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
                
                result = f(*args, **kwargs)
                redis_client.setex(cache_key, expiration, json.dumps(result))
                return result
                
            except redis.RedisError as e:
                logger.error(f"Redis error in cache_response: {str(e)}")
                return f(*args, **kwargs)
                
        return wrapper
    return decorator

@app.route('/api/video/<video_id>', methods=['GET'])
@cache_response(3600)
@track_quota("videos.list")
def get_video_details(video_id):
    try:
        request = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            return {"error": "Video not found"}, 404
            
        video_data = {
            "title": response['items'][0]['snippet']['title'],
            "description": response['items'][0]['snippet']['description'],
            "viewCount": response['items'][0]['statistics']['viewCount'],
            "likeCount": response['items'][0]['statistics'].get('likeCount', 0),
            "publishedAt": response['items'][0]['snippet']['publishedAt']
        }
        
        return video_data
        
    except googleapiclient.errors.HttpError as e:
        error_message = f"YouTube API error: {str(e)}"
        logger.error(error_message)
        return {"error": error_message}, 503
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(error_message)
        return {"error": error_message}, 500

@app.route('/api/comments/<video_id>', methods=['GET'])
@cache_response(1800)  # 30 minutes cache for comments
@track_quota("commentThreads.list")
def get_video_comments(video_id):
    try:
        page_token = request.args.get('pageToken', '')
        page_size = min(int(request.args.get('pageSize', 100)), 100)  # Limit page size
        
        request_obj = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=page_size,
            pageToken=page_token if page_token else None,
            textFormat="plainText"  # Optimize response size
        )
        response = request_obj.execute()
        
        comments_data = {
            "comments": [{
                "id": item['id'],
                "text": item['snippet']['topLevelComment']['snippet']['textDisplay'],
                "author": item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                "likeCount": item['snippet']['topLevelComment']['snippet']['likeCount'],
                "publishedAt": item['snippet']['topLevelComment']['snippet']['publishedAt']
            } for item in response['items']],
            "nextPageToken": response.get('nextPageToken', ''),
            "totalResults": response['pageInfo']['totalResults']
        }
        
        return comments_data
        
    except googleapiclient.errors.HttpError as e:
        error_message = f"YouTube API error: {str(e)}"
        logger.error(error_message)
        return {"error": error_message}, 503
    except QuotaExceededError as e:
        error_message = str(e)
        logger.error(error_message)
        return {"error": error_message}, 429
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(error_message)
        return {"error": error_message}, 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        redis_client = RedisClient.get_client()
        redis_client.ping()
        return {"status": "healthy"}, 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}, 503

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)