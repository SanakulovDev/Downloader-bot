import re
from typing import Optional

def is_youtube_url(url: str) -> bool:
    """YouTube URL ni tekshirish"""
    return 'youtube.com' in url or 'youtu.be' in url

def is_instagram_url(url: str) -> bool:
    """Instagram URL ni tekshirish"""
    return 'instagram.com' in url and ('/p/' in url or '/reel/' in url or '/tv/' in url)

def extract_url(text: str) -> Optional[str]:
    """Matndan URL ni ajratib olish"""
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None

def extract_youtube_id(url: str) -> Optional[str]:
    """YouTube video ID ni ajratib olish"""
    # Short URL (youtu.be/ID)
    match = re.search(r'youtu\.be/([^?&]+)', url)
    if match: return match.group(1)
    
    # Standard URL (v=ID)
    match = re.search(r'v=([^&]+)', url)
    if match: return match.group(1)
    
    # Embed URL
    match = re.search(r'embed/([^?&]+)', url)
    if match: return match.group(1)
    
    return None
