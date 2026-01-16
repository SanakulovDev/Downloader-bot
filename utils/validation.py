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
