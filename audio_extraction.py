from moviepy.editor import *
import re
import os
import time

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

def extract_audio(video_file_path: str, output_path: str) -> str:
    start = time.time()
    video = VideoFileClip(video_file_path)
    sanitized_filename = sanitize_filename(video_file_path.split('/')[-1].split('.')[0])
    audio_file_path = f"{output_path}/{sanitized_filename}.mp3"

    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)

    video.audio.write_audiofile(audio_file_path)

    end = time.time()
    print(end-start, "audio-extraction\n")


    return audio_file_path
