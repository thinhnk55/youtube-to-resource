import logging

import requests
from bs4 import BeautifulSoup

from ast import literal_eval
import os

from datetime import datetime

from .utils import *

logger = logging.getLogger('uvicorn.error')

def extract_url(url, download=False):
    info_dict = get_vid_info(url, download)
    vid_info = {
        'video_id': info_dict['id'],
        'video_title': info_dict['title'],
        'length': info_dict['duration'],
        'thumbnail': info_dict['thumbnail'],
        'channel': info_dict['channel_url'],
    }
    subtitles = get_subtitle(info_dict)
    if len(subtitles) == 0:
        logger.warn(f'Video: {info_dict['title']}-[{info_dict['id']}] missing subtitle')
    return vid_info, subtitles

def extract_meaning(list_spans):
    meanings = []
    for s in list_spans:
        try:
            definition = s.findChild('span', {'class': 'def'}).text
        except Exception as e:
            continue
        else:
            cefr = extract_cefr(s)
            if s.findChild('span', {'class': 'topic-g'}) is None:
                topic = ''
                t_cefr = ''
            else:
                topic = '' if s.findChild('span', {'class': 'topic-g'}).findChild('span', {'class': 'topic_name'}) is None else s.findChild('span', {'class': 'topic-g'}).findChild('span', {'class': 'topic_name'}).text
                t_cefr = '' if s.findChild('span', {'class': 'topic-g'}).findChild('span', {'class': 'topic_cefr'}) is None else s.findChild('span', {'class': 'topic-g'}).findChild('span', {'class': 'topic_cefr'}).text

            meanings.append({
                'def': definition,
                'cefr': cefr,
                'topic': topic,
                'topic_cefr': t_cefr
            })
    return meanings

def extract_info(vocab):
    url = f'https://www.oxfordlearnersdictionaries.com/definition/english/{vocab}'
    res = send_get(url)
    info = []
    if res.status_code != 200:
        return None
    if res.url != url:
        i = 1
        while True:
            new_url = f'{url}_{i}'
            res = send_get(new_url)
            if res.status_code != 200:
                break
            html = parse_html(res.text)
            info.append(extract_all(html))
            i += 1
    else:
        html = parse_html(res.text)
        info.append(extract_all(html))
    return info

def send_get(url):
    return requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

def parse_html(text):
    return BeautifulSoup(text, 'html.parser')

def extract_all(html):
    main_div = html.find_all(attrs={'class': 'entry'})[0]
    res = {
        'head_w': extract_head_w(main_div),
        'cefr': extract_head_cefr(main_div),
        'pos': extract_pos(main_div),
        'phons': extract_phons(main_div),
        'senses': extract_senses(main_div)
    }
    return res

def extract_head_cefr(main_div):
    try:
        top_con = main_div.findChild('div', {'class': 'top-container'})
    except Exception as e:
        return ''
    else:
        return extract_cefr(top_con)

def extract_cefr(div):
    try:
        cefr = div.findChild('div', {'class': 'symbols'}).findChild('a').findChild('span')['class'][0]
    except Exception as e:
        return ''
    else:
        sp = cefr.split('_')
        return sp[-1] if len(sp) > 1 else ''

def extract_head_w(main_div):
    try:
        res = main_div.findChild('h1', {'class': 'headword'}).text
    except Exception as e:
        return ''
    else:
        return res

def extract_phons(main_div):
    try:
        res = {d['class'][0]: {'phon': d.findChild('span', {'class': 'phon'}).text, 'mp3': d.findChild('div')['data-src-mp3'], 'ogg': d.findChild('div')['data-src-ogg']}
            for d in main_div.findChild('span', {'class': 'phonetics'}).findChildren('div', recursive=False)
        }
    except Exception as e:
        return {}
    else:
        return res

def extract_pos(main_div):
    try:
        res = main_div.findChild('span', {'class': 'pos'}).text
    except Exception as e:
        return ''
    else:
        return res

def extract_senses(main_div):
    try:
        list_spans = main_div.findChild('ol').findChildren('li', {'class': 'sense'})
    except Exception as e:
        return []
    else:
        if list_spans is None:
            return []
        return extract_meaning(list_spans)
    
def gpt_topic_level(text, token=None):
    if token is None:
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjgyODAsInVzZXJuYW1lIjpudWxsLCJlbWFpbCI6ImJvcm9zdHVkaW8yMDE4QGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQWNIVHRlV0VsRXhsR2VDMFJDaElDRFFWZlRXWmJrVFpBZlltaXFQQTlLcFVPYUQ9czk2LWMiLCJmaXJzdE5hbWUiOiJCb3JvIiwibGFzdE5hbWUiOiJTdHVkaW8iLCJpYXQiOjE3MDUzOTQ3OTQsImV4cCI6MTcwNzk4Njc5NH0.JcBq3H7PMmySGKpFj220aNU6-OTrr_90aj0au48GopE'
    
    PROMPT = """Given the following text, your jobs are of following: First, categorize into the following topics 'Animals', 'Appearance', 'Communication', 'Culture', 'Food and drink', 'Functions', 'Health', 'Homes and buildings', 'Leisure', 'Notions', 'People', 'Politics and society', 'Science and technology', 'Sport', 'The natural world', 'Time and space', 'Travel', 'Work and business', then categorize to cefr level based on difficulty.
    The output should strictly be in provided format: {"topic": "", "level":""}. Text: """ + text
    payload = {
        "end_point":"https://s.aginnov.com/openai/fsse/chat/completions/",
        "token": token,
        "prompt": PROMPT
    }

    res = requests.post('https://api.meepogames.com/ai/ag/completion/', json=payload)

    if res.status_code != 200:
        raise Exception(f'{res.status_code}: Sending request to GPT API failed')
    
    body = res.json()
    if body['error'] != 0:
        raise Exception(f'GPT API return error {body['error']}')
    
    try:
        data = literal_eval(body['data'])
    except Exception as e:
        raise Exception(f'[Failed to parse response] {e}')
    else:
        return data
    
def gpt_vocab(text, token=None):
    if token is None:
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjgyODAsInVzZXJuYW1lIjpudWxsLCJlbWFpbCI6ImJvcm9zdHVkaW8yMDE4QGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQWNIVHRlV0VsRXhsR2VDMFJDaElDRFFWZlRXWmJrVFpBZlltaXFQQTlLcFVPYUQ9czk2LWMiLCJmaXJzdE5hbWUiOiJCb3JvIiwibGFzdE5hbWUiOiJTdHVkaW8iLCJpYXQiOjE3MDUzOTQ3OTQsImV4cCI6MTcwNzk4Njc5NH0.JcBq3H7PMmySGKpFj220aNU6-OTrr_90aj0au48GopE'
    
    PROMPT = """Given the following text, your jobs are: extract 20 important vocabulary, explain its meaning, its part of speech tag, its ipa and categorize to cefr level based on difficulty. The output should strictly be in provided format: {"vocab_list": [{"vocabulary": "", "meaning": "", "pos":"", "ipa":"", "level":""}]}.  Text: """ + text
    payload = {
        "end_point":"https://s.aginnov.com/openai/fsse/chat/completions/",
        "token": token,
        "prompt": PROMPT
    }

    res = requests.post('https://api.meepogames.com/ai/ag/completion/', json=payload)

    if res.status_code != 200:
        raise Exception(f'{res.status_code}: Sending request to GPT API failed')
    
    body = res.json()
    if body['error'] != 0:
        raise Exception(f'GPT API return error {body['error']}')
    
    try:
        data = literal_eval(body['data'])
    except Exception as e:
        raise Exception(f'[Failed to parse response] {e}')
    else:
        return data
    
def gpt_summa(text, token=None):
    if token is None:
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjgyODAsInVzZXJuYW1lIjpudWxsLCJlbWFpbCI6ImJvcm9zdHVkaW8yMDE4QGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQWNIVHRlV0VsRXhsR2VDMFJDaElDRFFWZlRXWmJrVFpBZlltaXFQQTlLcFVPYUQ9czk2LWMiLCJmaXJzdE5hbWUiOiJCb3JvIiwibGFzdE5hbWUiOiJTdHVkaW8iLCJpYXQiOjE3MDUzOTQ3OTQsImV4cCI6MTcwNzk4Njc5NH0.JcBq3H7PMmySGKpFj220aNU6-OTrr_90aj0au48GopE'
    
    PROMPT = """Given the following text, your job is to summarize the text. The output should be only the summarization, nothing else. Text: """ + text
    payload = {
        "end_point":"https://s.aginnov.com/openai/fsse/chat/completions/",
        "token": token,
        "prompt": PROMPT
    }

    res = requests.post('https://api.meepogames.com/ai/ag/completion/', json=payload)

    if res.status_code != 200:
        raise Exception(f'{res.status_code}: Sending request to GPT API failed')
    
    body = res.json()
    if body['error'] != 0:
        raise Exception(f'GPT API return error {body['error']}')
    
    try:
        data = {'summarize': body['data']}
    except Exception as e:
        raise Exception(f'[Failed to parse response] {e}')
    else:
        return data
    
def gpt_questions(text, token=None):
    if token is None:
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjgyODAsInVzZXJuYW1lIjpudWxsLCJlbWFpbCI6ImJvcm9zdHVkaW8yMDE4QGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQWNIVHRlV0VsRXhsR2VDMFJDaElDRFFWZlRXWmJrVFpBZlltaXFQQTlLcFVPYUQ9czk2LWMiLCJmaXJzdE5hbWUiOiJCb3JvIiwibGFzdE5hbWUiOiJTdHVkaW8iLCJpYXQiOjE3MDUzOTQ3OTQsImV4cCI6MTcwNzk4Njc5NH0.JcBq3H7PMmySGKpFj220aNU6-OTrr_90aj0au48GopE'
    
    PROMPT = """Given the following text, your jobs are of following. Create exactly 6 comprehension questions that has multiple choices, correct choice should be the index in the array of choices starting from 0, explain the correct one.
    The output should strictly be in provided format: {"questions": [{"question":"", "choices":[], "correct":"", "explanation":""}]}. Text provided:""" + text

    payload = {
        "end_point":"https://s.aginnov.com/openai/fsse/chat/completions/",
        "token": token,
        "prompt": PROMPT
    }

    res = requests.post('https://api.meepogames.com/ai/ag/completion/', json=payload)

    if res.status_code != 200:
        raise Exception(f'{res.status_code}: Sending request to GPT API failed')
    
    body = res.json()
    if body['error'] != 0:
        raise Exception(f'GPT API return error {body['error']}')
    
    try:
        data = literal_eval(body['data'])
    except Exception as e:
        raise Exception(f'[Failed to parse response] {e}')
    else:
        return data
    
def gpt(text, token=None):
    if token is None:
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjgyODAsInVzZXJuYW1lIjpudWxsLCJlbWFpbCI6ImJvcm9zdHVkaW8yMDE4QGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQWNIVHRlV0VsRXhsR2VDMFJDaElDRFFWZlRXWmJrVFpBZlltaXFQQTlLcFVPYUQ9czk2LWMiLCJmaXJzdE5hbWUiOiJCb3JvIiwibGFzdE5hbWUiOiJTdHVkaW8iLCJpYXQiOjE3MDUzOTQ3OTQsImV4cCI6MTcwNzk4Njc5NH0.JcBq3H7PMmySGKpFj220aNU6-OTrr_90aj0au48GopE'
    
    PROMPT_1 = """Given the following text, your jobs are of following: First, categorize into the following topics 'Animals', 'Appearance', 'Communication', 'Culture', 'Food and drink', 'Functions', 'Health', 'Homes and buildings', 'Leisure', 'Notions', 'People', 'Politics and society', 'Science and technology', 'Sport', 'The natural world', 'Time and space', 'Travel', 'Work and business', then categorize to cefr level based on difficulty.
    The output should be in provided format: {"topic": "", "level":""}. Text: """ + text

    PROMPT_2 = """Given the following text, your job is to summarize the text. The output should be only the summarization, nothing else. Text: """ + text

    PROMPT_3 = """Given the following text, your jobs are: extract 10 important vocabulary, explain its meaning, its part of speech tag, its ipa and categorize to cefr level based on difficulty. The output should strictly be in provided format: {"vocab_list": [{"vocabulary": "", "meaning": "", "pos":"", "ipa":"", "level":""}]}.  Text: """ + text

    PROMPT_4 = """Given the following text, your jobs are of following. Create exactly 6 comprehension questions that has multiple choices, correct choice should be the index in the array of choices starting from 0, explain the correct one.
    The output should strictly be in provided format: {"questions": [{"question":"", "choices":[], "correct":"", "explanation":""}]}. Text provided:""" + text

    promp_list = [PROMPT_1, PROMPT_2, PROMPT_3, PROMPT_4]

    ret = []

    for i, p in enumerate(promp_list):
        payload = {
            "end_point":"https://s.aginnov.com/openai/fsse/chat/completions/",
            "token": token,
            "prompt": p
        }

        res = requests.post('https://api.meepogames.com/ai/ag/completion/', json=payload)

        if res.status_code != 200:
            raise Exception(f'{res.status_code}: Request failed')
        
        body = res.json()
        if body['error'] != 0:
            raise Exception(f'Error calling gpt api')
        
        try:
            if i == 1:
                data = {'summarize': body['data']}
            else:
                data = literal_eval(body['data'])
        except Exception as e:
            if not os.path.exists('./failed_attemp'):
                os.mkdir('./failed_attemp')
            with open(f'./failed_attemp/{datetime.now().strftime('%d_%m_%Y_%H_%M_%S') + f'_PROMT{i}'}.txt', 'w') as f:
                f.write(body['data'])
            raise e
        else:
            ret.append(data)
    

    
    ret_dict = {}
    for r in ret:
        ret_dict.update(r)
    return ret_dict
