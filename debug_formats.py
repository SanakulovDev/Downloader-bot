import yt_dlp
import json

COMMON_OPTS = {
    'quiet': True,
    'cookiefile': '/app/cookies.txt', 
    'force_ipv4': True, 
    'force_ipv6': False,
    'extractor_args': {
        'youtube': {
            # 'tv' va 'tvembed' klientlari eng ko'p formatni beradi
            'player_client': ['tv', 'web', 'android'],
            'player_skip': ['webpage', 'configs'],
        }
    },
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

url = "https://www.youtube.com/watch?v=LXb3EKWsInQ" # 4K video

print(f"Checking formats for {url}...")
with yt_dlp.YoutubeDL(COMMON_OPTS) as ydl:
    info = ydl.extract_info(url, download=False)
    if not info:
        print("Failed to extract info")
        exit(1)
        
    formats = info.get('formats', [])
    print(f"Found {len(formats)} formats.")
    
    # 1080p formatini qidirish
    target_format = None
    for f in formats:
        if f.get('height') == 1080 and f.get('vcodec') != 'none':
            target_format = f
            break
            
    if target_format:
        print(f"Downloading 1080p video (ID: {target_format['format_id']})...")
        # Video + Audio birlashtirish
        ydl_opts = {
            **COMMON_OPTS,
            'format': f"{target_format['format_id']}+bestaudio/best",
            'outtmpl': 'test_1080p.%(ext)s',
            'merge_output_format': 'mp4',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl_down:
            ydl_down.download([url])
            print("Download complete: test_1080p.mp4")
    else:
        print("1080p format not found.")

