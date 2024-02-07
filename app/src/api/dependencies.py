import logging
import json
from typing import Annotated
from random import sample
import traceback
import os

from fastapi import Body, HTTPException

from ..db.database import SessionLocal
from ..components.extractor import *
from ..components.textrankv3 import Doc
from ..components.utils import lemmatize
from ..db.schemas import Level, RequestVideo

logger = logging.getLogger('uvicorn.error')

async def get_db_session():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f'Create database session failed: {e}')
    finally:
        await db.close()

def dump_temp_json(vid, fname, obj):
    if not os.path.exists(f'./app/temp/{vid}'):
        os.makedirs(f'./app/temp/{vid}')
    with open(f'./app/temp/{vid}/{fname}.json', 'w') as f:
        json.dump(obj, f, indent=4)
    
def load_temp_file(vid, fname):
    if os.path.exists(f'./app/temp/{vid}/{fname}.json'):
        with open(f'./app/temp/{vid}/{fname}.json', 'r') as f:
            data = json.load(f)
        return data
    else:
        return None
    
def clear_temp_file(vid):
    """
    called when task finished
    """
    if os.path.exists(f'./app/temp/{vid}'):
        os.rmdir(f'./app/temp/{vid}')

def extract_topic_level(vid, text):
    try:
        processed = load_temp_file(vid, 'topic_level')
        if not processed:
            res = gpt_topic_level(text)
            processed = {
                'topic': res['topic'],
                'level': Level[format_cefr_key(res['level'])].value
            }
    except Exception as e:
        raise e
    else:
        dump_temp_json(vid, 'topic_level', processed)
        return processed
    
def extract_summa(vid, text):
    try:
        processed = load_temp_file(vid, 'summa')
        if not processed:
            processed = gpt_summa(text)
    except Exception as e:
        raise e
    else:
        dump_temp_json(vid, 'summa', processed)
        return processed
    
def extract_vocab(vid, text):
    try:
        processed = load_temp_file(vid, 'vocab')
        if not processed:
            processed = {'vocab': process_list_vocabs(gpt_vocab(text)['vocab_list'])}
    except Exception as e:
        raise e
    else:
        dump_temp_json(vid, 'vocab', processed)
        return processed
    
def extract_questions(vid, text):
    try:
        processed = load_temp_file(vid, 'questions')
        if not processed:
            processed = gpt_questions(text)
    except Exception as e:
        raise e
    else:
        dump_temp_json(vid, 'questions', processed)
        return processed
    
def extract_lessions(vid, text, gpt_qs):
    try:
        doc = Doc(4, 15)
        doc.fit(text)
        syn_questions = doc.gen_questions()
        t3 = [q for _, q in syn_questions.items()][:6]
        reading = create_lession((gpt_qs[:3], [], t3))
        listening = create_lession((gpt_qs[3:], [], t3))
        processed = {
            'reading': reading,
            'listening': listening
        }
    except Exception as e:
        raise e
    else:
        return processed
    
def extract_subs(subs):
    try:
        auto = False
        for s in subs:
            s.pop('video_id')
            s.pop('sub_id')
            auto = s.pop('auto')
        processed = {
            'auto': auto,
            'lines': subs
        }
    except Exception as e:
        raise e
    else:
        return processed

def extract_video_and_sub(url: RequestVideo):
    vid_info, subs = extract_url(url.url)
    text = ' '.join([s['text'] for s in subs])
    # subs extracted contains video_id, sub_id key that link to ytb video id (might need later for matching)
    # need to pop it to avoid validation error later
    auto = False
    for s in subs:
        s.pop('video_id')
        s.pop('sub_id')
        auto = s.pop('auto')
    try:
        # Check if the gpt-3 generated response has already been acquired else make a api call (This is to preserve API call token)
        temp_file = f'./app/temp/{vid_info['video_id']}.json'
        if not os.path.exists(temp_file):
            logging.info('Making API calls to GPT-3')
            gpt_processed = gpt(text)
            with open(temp_file, 'w') as f:
                json.dump(gpt_processed, f, indent=4)
        else:
            logging.info('Loading temp preprocessed file')
            with open(temp_file, 'r') as f:
                gpt_processed = json.load(f)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(525, f'Preprocessing text failed due to call to gpt api: {e}, please try again later')
    try:
        doc = Doc(4, 15)
        doc.fit(text)
        syn_questions = doc.gen_questions()
        t3 = [q for _, q in syn_questions.items()][:6]
        reading = create_lession((gpt_processed['questions'][:3], [], t3))
        listening = create_lession((gpt_processed['questions'][3:], [], t3))
        result = {
            'video': {
                'url_id': vid_info['video_id'],
                'video_title': vid_info['video_title'],
                'length': vid_info['length'],
                'thumbnail': vid_info['thumbnail'],
                'channel': vid_info['channel'],
                'topic': gpt_processed['topic'],
                'summa': gpt_processed['summarize'],
                'level': Level[format_cefr_key(gpt_processed['level'])].value
            },
            'subtitles': {
                'auto': auto,
                'lines': subs
            },
            'vocab': process_list_vocabs(gpt_processed['vocab_list']),
            'reading': reading,
            'listening': listening
        }
    except KeyError as e:
        # Some time gpt generated weird output format, check json file in temp folder
        print(traceback.format_exc())
        logging.error(f'{e} | Please check temp file for gpt mismatch format')
        raise HTTPException(525, f'Preprocessing text failed | please try again later')
    return result

def process_list_vocabs(vocabs):
    res = []
    for v in vocabs:
        head_w = v['vocabulary']
        try:
            f = {
                'vocab': {
                    'word': head_w,
                    'ipa': v['ipa']
                },
                'sense': {
                    'sense': v['meaning'],
                    'pos': v['pos'],
                    'level': Level[format_cefr_key(v['level'])].value,
                }
            }
        except KeyError as e:
            print(traceback.format_exc())
            logging.error(f'{e} | Please check temp file for gpt mismatch format')
        else:
            # In case gpt failed to generate ipa, crawl oxford dictionary web to acquire ipa
            if f['vocab']['ipa'] == '':
                infos = extract_info(head_w)
                # If not found, lemmatize and retry
                if infos is None:
                    infos = extract_info(lemmatize(head_w))
                    if infos is not None:
                        f['vocab']['ipa'] = list(infos[0]['phons'].values())[0]['phon']
            res.append(f)
    return res

def create_lession(questions):
    try:
        t1, t2, t3 = questions
        t3_final = [q for q in sample_t3_q(sample(t3, 4))]
        res = []
        for q in t1:
            res.append({'type': 0, **process_t1_question_format(q)})
        for q in t2:
            res.append(q)
        for q in t3_final:
            res.append(process_t3_question_format(q))
    except Exception as e:
        raise e
    else:
        return res

def process_t1_question_format(question):
    # Make sure to convert correct answer index to int in case ast.literal_eval failed for some obnoxious reason
    def reformat_to_int(q):
        if type(q) is int:
            return q
        if type(q) is str:
            if q.isdigit():
                return int(q)
        raise KeyError('Correct answer is not integer')
    try:
        res = {
            'question': question['question'],
            'choices': [
                {
                    'choice': c,
                    'correct': True if i == reformat_to_int(question['correct']) else False,
                    'expl': question['explanation'] if i == reformat_to_int(question['correct']) else '',
                } for i, c in enumerate(question['choices'])
            ]
        }
    except Exception as e:
        logging.error(f'{e} | Please check temp file for gpt mismatch format')
        raise e
    else:
        return res 

def process_t3_question_format(question):
    return {
        'question': question[0],
        'type': 2,
        'choices': [
            {
                'choice': question[1],
                'correct': True,
                'expl': ''
            }
        ],
    }

def sample_t3_q(questions: list[tuple[str, str, str]]):
    return [sample(q, 1)[0] for q in questions]

def format_cefr_key(txt):
    cefr = ['a1', 'a2', 'b1', 'b2', 'c1', 'c2']
    for c in cefr:
        if txt.lower().find(c) != -1:
            return c
    return txt