import yt_dlp
import json
print(f"yt-dlp version: {yt_dlp.version.__version__}")

COMMON_OPTS = {
    'cachedir': False,
    'quiet': True,
    # 'cookiefile': '/app/cookies.txt', 
    'force_ipv4': True, 
    'force_ipv6': False,
    # 'extractor_args': {
    #     'youtube': {
    #         'player_client': ['android', 'ios'],
    #     }
    # },
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'no_warnings': True,
    'ignoreerrors': False, # Xatoni ko'rish uchun vaqtincha False qiling
    'nocheckcertificate': True,
    'youtube_include_dash_manifest': True, # DASH manifestini majburan yuklash
    'youtube_include_hls_manifest': True,
}

# Use a local path for cookies if /app/cookies.txt doesn't exist
import os
if not os.path.exists('/app/cookies.txt'):
    if os.path.exists('app/cookies.txt'):
        COMMON_OPTS['cookiefile'] = 'app/cookies.txt'
    elif os.path.exists('cookies.txt'):
        COMMON_OPTS['cookiefile'] = 'cookies.txt'
    else:
        print("Warning: cookies.txt not found")
        # del COMMON_OPTS['cookiefile'] # Don't delete, let it error if critical or just print warning
# https://youtu.be/E0-Q5l60aQM?si=SODzuRCgB-akkoqY
url = "https://www.youtube.com/watch?v=E0-Q5l60aQM" # 4K video

print(f"Checking formats for {url}...")
with yt_dlp.YoutubeDL(COMMON_OPTS) as ydl:
    info = ydl.extract_info(url, download=False)
    if not info:
        print("Failed to extract info")
        exit(1)
        
    formats = info.get('formats', [])
    print(f"Found {len(formats)} formats.")
    
    print(f"{'ID':<10} {'EXT':<5} {'RES':<10} {'NOTE'}")
    print("-" * 40)
    for f in formats:
        fid = f.get('format_id')
        ext = f.get('ext')
        res = f"{f.get('width')}x{f.get('height')}" if f.get('height') else "audio only"
        note = f.get('format_note', '')
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        
        # Soddalashtirilgan ko'rinish
        print(f"{fid:<10} {ext:<5} {res:<10} {note} | v:{vcodec} a:{acodec}")

    # 1080p formatini qidirish
    target_format = None
    for f in formats:
        if f.get('height') == 1080 and f.get('vcodec') != 'none':
            target_format = f
            break
            
    if target_format:
        print(f"\nFound 1080p video (ID: {target_format['format_id']}).")
    else:
        print("\n1080p format not found.")

