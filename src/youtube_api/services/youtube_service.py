import os
from typing import Dict, List, Optional, TypedDict
from datetime import datetime
import logging
from ratelimit import limits, sleep_and_retry
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cachetools import TTLCache
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='youtube_processor.log'
)
logger = logging.getLogger(__name__)

# Custom exception classes
class YouTubeAPIError(Exception):
    """Base exception class for YouTube API errors"""
    pass

class QuotaExceededError(YouTubeAPIError):
    """Raised when the YouTube API quota has been exceeded"""
    pass

@dataclass
class VideoDetails:
    title: str
    description: str
    view_count: int
    like_count: int

@dataclass
class Comment:
    id: str
    text: str
    author: str
    like_count: int
    published_at: str

@dataclass
class CommentsResponse:
    comments: List[Comment]
    next_page_token: Optional[str]
    total_results: int

class YouTubeService:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the YouTube service with an API key.
        
        Args:
            api_key: Optional API key. If not provided, will try to read from YOUTUBE_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API key not provided and not found in environment variables")
            
        self.youtube = build(
            "youtube", "v3", 
            developerKey=self.api_key,
            cache_discovery=False
        )
        
        # In-memory cache with 1-hour TTL
        self.cache = TTLCache(maxsize=100, ttl=3600)
        
    @sleep_and_retry
    @limits(calls=10000, period=86400)  # YouTube API daily quota limit
    def _make_api_call(self):
        """Rate limiter wrapper for API calls"""
        pass

    async def get_video_details(self, video_id: str) -> VideoDetails:
        """Fetch video details from YouTube API with caching and error handling"""
        cache_key = f"video:{video_id}"
        
        # Check cache first
        if cache_key in self.cache:
            logger.info(f"Cache hit for video {video_id}")
            return self.cache[cache_key]
            
        try:
            self._make_api_call()
            
            request = self.youtube.videos().list(
                part="snippet,statistics",
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                logger.error(f"Video not found: {video_id}")
                raise ValueError(f"Video with ID {video_id} not found")
                
            item = response['items'][0]
            video_details = VideoDetails(
                title=item['snippet']['title'],
                description=item['snippet']['description'],
                view_count=int(item['statistics']['viewCount']),
                like_count=int(item['statistics'].get('likeCount', 0))
            )
            
            # Cache the result
            self.cache[cache_key] = video_details
            logger.info(f"Successfully fetched and cached details for video {video_id}")
            
            return video_details
            
        except HttpError as e:
            logger.error(f"YouTube API error for video {video_id}: {str(e)}")
            if e.resp.status == 403 and 'quota' in str(e).lower():
                raise QuotaExceededError("YouTube API quota has been exceeded")
            raise YouTubeAPIError(f"YouTube API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching video {video_id}: {str(e)}")
            raise

    async def get_video_comments(
        self, 
        video_id: str, 
        page_token: Optional[str] = None
    ) -> CommentsResponse:
        """Fetch video comments from YouTube API with pagination support"""
        cache_key = f"comments:{video_id}:{page_token or 'first'}"
        
        if cache_key in self.cache:
            logger.info(f"Cache hit for comments {cache_key}")
            return self.cache[cache_key]
            
        try:
            self._make_api_call()
            
            request = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=page_token
            )
            response = request.execute()
            
            comments = [
                Comment(
                    id=item['id'],
                    text=item['snippet']['topLevelComment']['snippet']['textDisplay'],
                    author=item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                    like_count=int(item['snippet']['topLevelComment']['snippet']['likeCount']),
                    published_at=item['snippet']['topLevelComment']['snippet']['publishedAt']
                )
                for item in response.get('items', [])
            ]
            
            comments_response = CommentsResponse(
                comments=comments,
                next_page_token=response.get('nextPageToken'),
                total_results=response['pageInfo']['totalResults']
            )
            
            # Cache the result
            self.cache[cache_key] = comments_response
            logger.info(f"Successfully fetched and cached comments for {cache_key}")
            
            return comments_response
            
        except HttpError as e:
            logger.error(f"YouTube API error fetching comments for video {video_id}: {str(e)}")
            if e.resp.status == 403 and 'quota' in str(e).lower():
                raise QuotaExceededError("YouTube API quota has been exceeded")
            raise YouTubeAPIError(f"YouTube API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching comments for video {video_id}: {str(e)}")
            raise