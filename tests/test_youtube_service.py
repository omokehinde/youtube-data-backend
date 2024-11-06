import pytest
import os
from unittest.mock import Mock, patch
from datetime import datetime
from googleapiclient.errors import HttpError

from youtube_api.services.youtube_service import (
    YouTubeService,
    VideoDetails,
    Comment,
    YouTubeAPIError,
    QuotaExceededError
)

@pytest.fixture
def youtube_service():
    service = YouTubeService(api_key="test_key")
    return service

@pytest.fixture
def mock_video_response():
    return {
        'items': [{
            'id': 'test_video_id',
            'snippet': {
                'title': 'Test Video',
                'description': 'Test Description',
                'publishedAt': '2024-01-01T00:00:00Z'
            },
            'statistics': {
                'viewCount': '1000',
                'likeCount': '100',
                'commentCount': '50'
            },
            'contentDetails': {
                'duration': 'PT5M30S'
            }
        }]
    }

@pytest.fixture
def mock_comments_response():
    return {
        'items': [
            {
                'id': f'comment_{i}',
                'snippet': {
                    'topLevelComment': {
                        'snippet': {
                            'textDisplay': f'Comment {i}',
                            'authorDisplayName': f'Author {i}',
                            'authorChannelId': {'value': f'channel_{i}'},
                            'likeCount': i,
                            'publishedAt': '2024-01-01T00:00:00Z',
                            'updatedAt': '2024-01-01T00:00:00Z'
                        }
                    }
                }
            }
            for i in range(5)
        ],
        'nextPageToken': 'next_token',
        'pageInfo': {'totalResults': 100}
    }

class MockResponse:
    def __init__(self, status):
        self.status = status

@pytest.mark.asyncio
async def test_get_video_details(youtube_service, mock_video_response):
    with patch.object(youtube_service.youtube.videos(), 'list') as mock_list:
        mock_list.return_value.execute.return_value = mock_video_response
        
        video_details = await youtube_service.get_video_details('test_video_id')
        
        assert isinstance(video_details, VideoDetails)
        assert video_details.title == 'Test Video'
        assert video_details.view_count == 1000
        assert video_details.comment_count == 50

@pytest.mark.asyncio
async def test_get_comments_page(youtube_service, mock_comments_response):
    with patch.object(youtube_service.youtube.commentThreads(), 'list') as mock_list:
        mock_list.return_value.execute.return_value = mock_comments_response
        
        comments_page = await youtube_service.get_comments_page('test_video_id')
        
        assert len(comments_page.comments) == 5
        assert comments_page.next_page_token == 'next_token'
        assert comments_page.total_results == 100

@pytest.mark.asyncio
async def test_quota_exceeded(youtube_service):
    with patch.object(youtube_service.youtube.videos(), 'list') as mock_list:
        mock_list.return_value.execute.side_effect = HttpError(
            resp=MockResponse(403),
            content=b'Quota exceeded'
        )
        
        with pytest.raises(QuotaExceededError):
            await youtube_service.get_video_details('test_video_id')

@pytest.mark.asyncio
async def test_get_all_comments(youtube_service, mock_comments_response):
    with patch.object(youtube_service.youtube.commentThreads(), 'list') as mock_list:
        # Simulate 3 pages of comments
        responses = [
            mock_comments_response,
            {**mock_comments_response, 'nextPageToken': 'next_token_2'},
            {**mock_comments_response, 'nextPageToken': None}
        ]
        mock_list.return_value.execute.side_effect = responses
        
        comments = await youtube_service.get_all_comments('test_video_id', max_comments=12)
        
        assert len(comments) == 12
        assert all(isinstance(comment, Comment) for comment in comments)

@pytest.mark.asyncio
async def test_rate_limiting(youtube_service, mock_video_response):
    with patch.object(youtube_service.youtube.videos(), 'list') as mock_list:
        mock_list.return_value.execute.return_value = mock_video_response
        
        # Make multiple requests in quick succession
        results = await asyncio.gather(
            *[youtube_service.get_video_details('test_video_id') for _ in range(5)]
        )
        
        assert len(results) == 5
        assert all(isinstance(result, VideoDetails) for result in results)

@pytest.mark.asyncio
async def test_video_not_found(youtube_service):
    with patch.object(youtube_service.youtube.videos(), 'list') as mock_list:
        mock_list.return_value.execute.return_value = {'items': []}
        
        with pytest.raises(ValueError, match="Video test_video_id not found"):
            await youtube_service.get_video_details('test_video_id')

@pytest.mark.asyncio
async def test_cache_hit(youtube_service, mock_video_response):
    with patch.object(youtube_service.youtube.videos(), 'list') as mock_list:
        mock_list.return_value.execute.return_value = mock_video_response
        
        # First call should hit the API
        video1 = await youtube_service.get_video_details('test_video_id')
        
        # Second call should use cache
        video2 = await youtube_service.get_video_details('test_video_id')
        
        assert mock_list.call_count == 1
        assert video1 == video2