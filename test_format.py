import yt_dlp
import json

url = "https://www.youtube.com/watch?v=Sy6emSOKlQY"

# M4A audio selector used in the bot
audio_sel_mp4 = "bestaudio[ext=m4a]/bestaudio"
audio_sel_webm = "bestaudio[ext=webm]/bestaudio"

def test_selector(format_id, ext):
    if ext == "mp4":
        selector = f"{format_id}+{audio_sel_mp4}"
    else:
        selector = f"{format_id}+{audio_sel_webm}"
    
    print(f"Testing selector: {selector}")
    
    opts = {
        'format': selector,
        'simulate': True,
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"Selected format: {info.get('format_id')}")
            print(f"Ext: {info.get('ext')}")
    except Exception as e:
        print(f"Error: {e}")

# First extract info to get a valid format_id
opts_info = {'quiet': True}
with yt_dlp.YoutubeDL(opts_info) as ydl:
    info = ydl.extract_info(url, download=False)
    formats = info.get('formats', [])
    
    # Check for a video-only format (e.g. 480p)
    target_fmt = None
    for f in formats:
        if f.get('height') == 480 and f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
            target_fmt = f
            break
            
    if target_fmt:
        print(f"Found 480p format: {target_fmt['format_id']}")
        test_selector(target_fmt['format_id'], 'mp4')
    else:
        print("No 480p mp4 format found.")
