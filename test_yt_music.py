import asyncio
import logging
from utils.yt_music import yt_music_service

# Configure logging to see errors
logging.basicConfig(level=logging.INFO)

async def main():
    query = "Linkin Park Numb"
    print(f"Searching for: {query}")
    
    results = await yt_music_service.search_songs(query, limit=5)
    
    if not results:
        print("No results found!")
        return

    print(f"Found {len(results)} results:")
    for i, res in enumerate(results):
        print(f"{i+1}. {res['artist']} - {res['title']} ({res['duration']}s)")
        print(f"   ID: {res['id']}")
        print(f"   Thumb: {res['thumbnail']}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
