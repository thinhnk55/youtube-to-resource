from concurrent.futures import ThreadPoolExecutor
import os
import webvtt
import re
import json
import requests
from io import StringIO
from nltk.stem import WordNetLemmatizer

from yt_dlp import YoutubeDL

def get_channel_video_url(channel_id):
    return f'https://www.youtube.com/channel/{channel_id}/videos'

def lemmatize(word):
    return WordNetLemmatizer().lemmatize(word)

def get_channel_info(url):
    opts = {
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'no_warnings': True,
        'quiet': True,
    }
    with YoutubeDL(opts) as ydl:
        try:
            channel_dict = ydl.extract_info(url)
        except Exception as e:
            return None

    return {
        'channel_id': channel_dict['channel_id'],
        'channel_name': channel_dict['channel'],
        'channel_url': channel_dict['channel_url'],
        'playlist_url': get_channel_video_url(channel_dict['channel_id'])
    }

def subtitle_to_json(list_info):
    with open(f'./{list_info["video_id"]}.json' , 'w') as f:
        json.dump(list_info, f, indent= 4)

def get_id_from_playlist(url):
    list_id = []
    opts = {
        'skip_download': True,
        'extract_flat': 'in_playlist',
        # 'no_warnings': True,
        # 'quiet': True,
    }
    with YoutubeDL(opts) as ydl:
        try:
            playlist_dict = ydl.extract_info(url)
        except Exception as e:
            return None
    for video in playlist_dict['entries']:
        vid_id = video['id']
        list_id.append(vid_id)
    return list_id


def get_vid_info(url, download_video=False, vid_dir=None):
    """
        Params:
            - url: Youtube video url
            - download_video: Download video to local
            - vid_dir: Path to store video local if download_video is True
        info_fields:
            - id
            - title
            - formats
            - thumbnails
            - thumbnail
            - description
            - channel_id
            - channel_url
            - duration
            - view_count
            - average_rating
            - age_limit
            - webpage_url
            - categories
            - tags
            - playable_in_embed
            - live_status
            - release_timestamp
            - _format_sort_fields??
            - automatic_captions
            - subtitles
            - comment_count
            - chapters
            - heatmap
            - channel
            - channel_follower_count
            - uploader
            - uploader_id
            - uploader_url
            - upload_date
            - availability
            - original_url
            - webpage_url_basename
            - webpage_url_domain
            - extractor??
            - extractor_key: internal extractor class for yt_dlp
            - playlist
            - playlist_index
            - display_id
            - fulltitle
            - duration_string
            - is_live
            - was_live
            - requested_subtitles
            - _has_drm?
            - epoch
            - requested_downloads
            - requested_formats
            - format
            - format_id
            - ext
            - protocol
            - language
            - format_note
            - filesize_approx
            - tbr
            - width
            - height
            - resolution
            - fps
            - dynamic_range
            - vcodec
            - vbr
            - stretched_ratio
            - aspect_ratio
            - acodec
            - abr
            - asr
            - audio_channels
    """
    if download_video:
        vid_dir = vid_dir if vid_dir else './app/assets/videos'
        if not os.path.exists(vid_dir):
            os.makedirs(vid_dir)
    opts = {
        'skip_download': not download_video,
        # "format": "mp4[height<=1080]",
        # "format": "mp4",
        'outtmpl': f'{vid_dir}/%(id)s.%(ext)s',
        # 'quiet': True,
        # 'no_warnings': True,
    }
    with YoutubeDL(opts) as ydl:
        try:
            info_dict = ydl.extract_info(url)
        except Exception as e:
            return None
    return info_dict

def extract_vtt_info(info_dict):
    sub_info = []
    if len(info_dict['subtitles']) !=0:
        for k, v in info_dict['subtitles'].items():
            if k.startswith('en'):
                for sub in v:
                    if sub['ext'] == 'vtt':
                        sub_info.append({
                            'auto': False,
                            'sub_id': k,
                            'url': sub['url']
                        })
    if len(info_dict['automatic_captions']) != 0:
        for k, v in info_dict['automatic_captions'].items():
            if k == 'en':
                for sub in v:
                    if sub['ext'] == 'vtt' and 'name' in sub.keys():
                        sub_info.append({
                            'auto': True,
                            'sub_id': k,
                            'url': sub['url']
                        })

    return sub_info
                        

def extract_vtt(url):
    headers = {'user-agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise Exception(f"Status code {res.status_code} when asking for subtitle at {url}")
    return res.text

def get_subtitle(info_dict):
    video_id = info_dict['id']
    sub_info = extract_vtt_info(info_dict)
    subtitles = []
    for sub in sub_info:
        sub_id = sub['sub_id']
        auto = sub['auto']
        url = sub['url']
        payload = extract_vtt(url)
        sub_text = parse_vtt_from_text(payload)
        for t in sub_text:
            subtitles.append({
                'video_id': video_id,
                'sub_id': sub_id,
                'auto': auto,
                'start': t['start'],
                'end': t['end'],
                'text': ' '.join(t['text'].replace('&nbsp;', ' ').strip(' ').split(' '))
            })
    return subtitles

def parse_vtt_from_text(payload):
    """
    extracts start time and text from vtt text and return a list of dicts
    """
    result = []

    buffer = StringIO(payload)
    for caption in webvtt.read_buffer(buffer):
        if caption is not None:
            pass #TODO: raise exception?
        result.append({
            'start': caption.start,
            'end': caption.end,
            'text': caption.text.replace('\n', ' '),
        })

    return result 

def parse_vtt(file_path):
    """
    extracts start time and text from vtt file and return a list of dicts
    """
    result = []

    for caption in webvtt.read(file_path):
        if caption is not None:
            pass #TODO: Should clean the temp vtt file
        result.append({
            'vtt_id': os.path.basename(file_path),
            'start': caption.start,
            'end': caption.end,
            'text': caption.text,
        })

    return result 

def get_url_with_timestamp(video_id, starttime):
    def convert_to_second(time_str):
        time_split = time_str.split(':')
        hours = int(time_split[0]) * 3600 
        mins = int(time_split[1]) * 60
        secs = int(float(time_split[2]))
        total_secs =  hours + mins + secs
        return total_secs - 5
    return f'https://youtube.com/watch?v={video_id}&t={convert_to_second(starttime)}'