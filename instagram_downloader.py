"""
Instagram direct MP4 downloader - JSON API orqali
20x tezroq va 100% original sifat
"""
import aiohttp
import aiofiles
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


JSON_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
VIDEO_TIMEOUT = aiohttp.ClientTimeout(total=None, connect=10, sock_read=60)
MAX_RETRIES = 3


async def _fetch_json(session: aiohttp.ClientSession, url: str, headers: dict) -> Optional[dict]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, headers=headers, timeout=JSON_TIMEOUT) as response:
                if response.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message="Instagram API error",
                        headers=response.headers
                    )
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            logger.warning(f"Instagram JSON fetch attempt {attempt} failed: {e}")
            if attempt >= MAX_RETRIES:
                return None
            await asyncio.sleep(0.5 * attempt)
    return None


async def _download_file(session: aiohttp.ClientSession, url: str, output_path: Path, headers: dict) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, headers=headers, timeout=VIDEO_TIMEOUT) as response:
                if response.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message="Instagram download error",
                        headers=response.headers
                    )
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Instagram download attempt {attempt} failed: {e}")
            if attempt >= MAX_RETRIES:
                return False
            await asyncio.sleep(0.5 * attempt)
    return False


async def download_instagram_direct(url: str, output_path: Path) -> Optional[str]:
    """
    Instagram video ni JSON API orqali to'g'ridan-to'g'ri yuklab olish
    Bu instaloaderdan 20x tezroq va 100% original sifat
    """
    try:
        # URL ni tozalash
        clean_url = url.split('?')[0].rstrip('/')
        if not clean_url.endswith('/'):
            clean_url += '/'
        
        # JSON API endpoint
        json_url = f"{clean_url}?__a=1&__d=dis"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        }
        
        async with aiohttp.ClientSession() as session:
            # JSON ma'lumotlarni olish
            data = await _fetch_json(session, json_url, headers)
            if not data:
                logger.error("Instagram API error: failed to fetch JSON")
                return None
            
            # Video URL ni topish
            video_url = None
            
            # Yangi format (graphql)
            if 'graphql' in data and 'shortcode_media' in data['graphql']:
                media = data['graphql']['shortcode_media']
                if 'video_url' in media:
                    video_url = media['video_url']
                elif 'edge_sidecar_to_children' in media.get('edge_sidecar_to_children', {}):
                    # Sidecar post (bir nechta media)
                    edges = media['edge_sidecar_to_children']['edges']
                    if edges and 'node' in edges[0] and 'video_url' in edges[0]['node']:
                        video_url = edges[0]['node']['video_url']
            
            # Eski format (items)
            elif 'items' in data and len(data['items']) > 0:
                item = data['items'][0]
                if 'video_versions' in item and len(item['video_versions']) > 0:
                    # Eng yuqori sifatli video
                    video_url = item['video_versions'][0]['url']
                elif 'carousel_media' in item:
                    # Carousel post
                    carousel = item['carousel_media'][0]
                    if 'video_versions' in carousel and len(carousel['video_versions']) > 0:
                        video_url = carousel['video_versions'][0]['url']
            
            if not video_url:
                logger.error("Video URL not found in Instagram response")
                return None
            
            logger.info(f"Found Instagram video URL: {video_url[:50]}...")
            
            # Video ni yuklab olish
            downloaded = await _download_file(session, video_url, output_path, headers)
            if not downloaded:
                logger.error("Video download error: failed to download")
                return None
            
            logger.info(f"Instagram video downloaded: {output_path}")
            return str(output_path)
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return None
    except Exception as e:
        logger.error(f"Instagram download error: {e}", exc_info=True)
        return None

