from typing import Annotated
import json

from fastapi import APIRouter, Query, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from ...db import schemas, crud, models
from ...components.extractor import extract_url, gpt
from ..dependencies import *
from ..broker import *

logger = logging.getLogger('uvicorn.error')

router = APIRouter(
    prefix='/nlp/api',
    tags=['prototype'],
    responses={404: {'description': 'Not Found'}}
)

async def test_depend(q: str):
    return {'q': q}

@router.get('/test')
async def test(et: Annotated[dict, Depends(test_depend)]):
    return et

async def start_video_insert_task(executor, vid, params, retry=False):
    if jobs[vid].states['subtitles'].status == Status.IN_PROGRESS or (jobs[vid].states['subtitles'].status == Status.FAILED and retry):
        try:
            jobs[vid].states['subtitles'].data = await run_in_process(executor, extract_subs, params['subs'])
        except Exception as e:
            jobs[vid].states['subtitles'].status = Status.FAILED
            logging.error(f'Failed task subtitles: {e}')
        else:
            jobs[vid].states['subtitles'].status = Status.COMPLETED

    if jobs[vid].states['topic_level'].status == Status.IN_PROGRESS or (jobs[vid].states['topic_level'].status == Status.FAILED and retry):
        try:
            jobs[vid].states['topic_level'].data = await run_in_process(executor, extract_topic_level, vid,  params['text'])
        except Exception as e:
            jobs[vid].states['topic_level'].status = Status.FAILED
            logging.error(f'Failed task topic_level: {e}')
        else:
            jobs[vid].states['topic_level'].status = Status.COMPLETED

    if jobs[vid].states['summarize'].status == Status.IN_PROGRESS or (jobs[vid].states['summarize'].status == Status.FAILED and retry):
        try:
            jobs[vid].states['summarize'].data = await run_in_process(executor, extract_summa, vid,  params['text'])
        except Exception as e:
            jobs[vid].states['summarize'].status = Status.FAILED
            logging.error(f'Failed task summarize: {e}')
        else:
            jobs[vid].states['summarize'].status = Status.COMPLETED

    if jobs[vid].states['vocabulary'].status == Status.IN_PROGRESS or (jobs[vid].states['vocabulary'].status == Status.FAILED and retry):
        try:
            jobs[vid].states['vocabulary'].data = await run_in_process(executor, extract_vocab, vid,  params['text'])
        except Exception as e:
            jobs[vid].states['vocabulary'].status = Status.FAILED
            logging.error(f'Failed task vocabulary: {e}')
        else:
            jobs[vid].states['vocabulary'].status = Status.COMPLETED

    if jobs[vid].states['questions'].status == Status.IN_PROGRESS or (jobs[vid].states['questions'].status == Status.FAILED and retry):
        try:
            jobs[vid].states['questions'].data = await run_in_process(executor, extract_questions, vid,  params['text'])
        except Exception as e:
            jobs[vid].states['questions'].status = Status.FAILED
            logging.error(f'Failed task questions: {e}')
        else:
            jobs[vid].states['questions'].status = Status.COMPLETED

    if jobs[vid].states['lessions'].status == Status.IN_PROGRESS or (jobs[vid].states['lessions'].status == Status.FAILED and retry):
        if jobs[vid].states['questions'].data:
            try:
                jobs[vid].states['lessions'].data = await run_in_process(executor, extract_lessions, vid, params['text'], jobs[vid].states['questions'].data['questions'])
            except Exception as e:
                jobs[vid].states['lessions'].status = Status.FAILED
                logging.error(f'Failed task lessions: {e}')
            else:
                jobs[vid].states['lessions'].status = Status.COMPLETED
        else:
            jobs[vid].states['lessions'].status = Status.FAILED
            logging.error(f'Failed task lessions: task questions failed')

    if jobs[vid].states['insert_video'].status == Status.IN_PROGRESS or (jobs[vid].states['insert_video'].status == Status.FAILED and retry):
        if jobs[vid].states['info'].status == Status.COMPLETED and jobs[vid].states['topic_level'].status == Status.COMPLETED and jobs[vid].states['summarize'].status == Status.COMPLETED:
            try:
                v = schemas.VideoCreate(
                    url_id=jobs[vid].states['info'].data['url_id'],
                    video_title=jobs[vid].states['info'].data['video_title'],
                    length=jobs[vid].states['info'].data['length'],
                    thumbnail=jobs[vid].states['info'].data['thumbnail'],
                    channel=jobs[vid].states['info'].data['channel'],
                    topic=jobs[vid].states['topic_level'].data['topic'],
                    level=jobs[vid].states['topic_level'].data['level'],
                    summa=jobs[vid].states['summarize'].data['summarize']
                )
                v_model: models.Videos | None = await crud.create_video(params['db'], v)
            except Exception as e:
                jobs[vid].states['insert_video'].status = Status.FAILED
                logging.error(f'Failed task insert_video: {traceback.format_exc()}')
            else:
                if not v_model:
                    jobs[vid].states['insert_video'].status = Status.FAILED
                    logging.error(f'Failed task insert_video: database failed')
                else:
                    jobs[vid].states['insert_video'].status = Status.COMPLETED
                    jobs[vid].states['insert_video'].data = schemas.Video(
                        url_id=v_model.url_id,
                        video_title=v_model.video_title,
                        length=v_model.length,
                        thumbnail=v_model.thumbnail,
                        channel=v_model.channel,
                        topic=v_model.topic,
                        summa=v_model.summa,
                        level=v_model.level,
                        id=v_model.id
                    ).model_dump()
        else:
            jobs[vid].states['insert_video'].status = Status.FAILED
            logging.error(f'Failed task insert_video: prerequisite tasks failed')
            
    if jobs[vid].states['insert_subs'].status == Status.IN_PROGRESS or (jobs[vid].states['insert_subs'].status == Status.FAILED and retry):
        if jobs[vid].states['subtitles'].status == Status.COMPLETED and jobs[vid].states['insert_video'].status == Status.COMPLETED:
            try:
                s = schemas.SubtitlesCreate(
                    auto=jobs[vid].states['subtitles'].data['auto'],
                    video_id=jobs[vid].states['insert_video'].data['id']
                )
                sub_model: models.Subtitles | None = await crud.create_subtitle(params['db'], s)
            except Exception as e:
                jobs[vid].states['insert_subs'].status = Status.FAILED
                logging.error(f'Failed task insert_subs: {traceback.format_exc()}')
            else:
                if not sub_model:
                    jobs[vid].states['insert_subs'].status = Status.FAILED
                    logging.error(f'Failed task insert_subs: database failed')
                else:
                    try:
                        sub_id = sub_model.id
                        jobs[vid].states['insert_subs'].data = {
                            'subtitle': schemas.Subtitles(auto=sub_model.auto, video_id=sub_model.video_id, id=sub_id)
                        }

                        l = [schemas.SubtitleLinesCreate(sub_id=sub_id, **s) for s in jobs[vid].states['subtitles'].data['lines']]
                        line_model: list[models.Lines] | None = await crud.create_sub_lines(params['db'], l)
                    except Exception as e:
                        jobs[vid].states['insert_subs'].status = Status.FAILED
                        logging.error(f'Failed task insert_subs: {traceback.format_exc()}')
                    else:
                        if not line_model:
                            jobs[vid].states['insert_subs'].status = Status.FAILED
                            logging.error(f'Failed task insert_subs: database failed')
                        else:
                            jobs[vid].states['insert_subs'].status = Status.COMPLETED
                            jobs[vid].states['insert_subs'].data['lines'] = [schemas.SubtitleLines(
                                sub_id=s.sub_id, start=s.start, end=s.end, text=s.text, id=s.id
                            ) for s in line_model]
        else:
            jobs[vid].states['insert_subs'].status = Status.FAILED
            logging.error(f'Failed task insert_subs: prerequisite tasks failed')

    if jobs[vid].states['insert_vocabs'].status == Status.IN_PROGRESS or (jobs[vid].states['insert_vocabs'].status == Status.FAILED and retry):
        if jobs[vid].states['vocabulary'].status == Status.COMPLETED and jobs[vid].states['insert_video'].status == Status.COMPLETED:
            res = []
            try:
                failed = False
                for v in jobs[vid].states['vocabulary'].data['vocab']:
                    vocab_model: models.Vocabs | None = await crud.create_vocab(params['db'], schemas.VocabCreate(**v['vocab']))
                    
                    if not vocab_model:
                        failed = True
                        break

                    vocab_id = vocab_model.id
                    word = vocab_model.word
                    ipa = vocab_model.ipa

                    sense_model: models.Senses | None = await crud.create_sense(params['db'], schemas.SenseCreate(
                        video_id=jobs[vid].states['insert_video'].data['id'],
                        vocab_id=vocab_id,
                        **v['sense']
                    ))

                    if not sense_model:
                        failed = True
                        break
                    
                    sense = sense_model.sense
                    pos = sense_model.pos
                    level = sense_model.level

                    res.append({
                        'word': word,
                        'ipa': ipa,
                        'sense': sense,
                        'pos': pos,
                        'level': level,
                    })

            except Exception as e:
                jobs[vid].states['insert_vocabs'].status = Status.FAILED
                logging.error(f'Failed task insert_vocabs: {traceback.format_exc()}')
            else:
                if failed:
                    jobs[vid].states['insert_vocabs'].status = Status.FAILED
                    logging.error(f'Failed task insert_vocabs: database failed')
                else:
                    jobs[vid].states['insert_vocabs'].status = Status.COMPLETED
                    jobs[vid].states['insert_vocabs'].data = res
        else:
            jobs[vid].states['insert_vocabs'].status = Status.FAILED
            logging.error(f'Failed task insert_vocabs: prerequisite tasks failed')

    if jobs[vid].states['insert_lessions'].status == Status.IN_PROGRESS or (jobs[vid].states['insert_lessions'].status == Status.FAILED and retry):
        if jobs[vid].states['lessions'].status == Status.COMPLETED and jobs[vid].states['insert_video'].status == Status.COMPLETED:
            res = {
                'reading': None,
                'listening': None
            }
            try:
                rl = schemas.LessionCreate(video_id=jobs[vid].states['insert_video'].data['id'], type=0)
                rl_model: models.Lessions | None = await crud.create_lession(params['db'], rl)
                
                if not rl_model:
                    raise Exception('Failed to insert reading')
                
                rl_id = rl_model.id
                rl_qs = []
                for q in jobs[vid].states['lessions'].data['reading']:
                    question = schemas.QuestionCreate(question=q['question'], type=q['type'], lession_id=rl_id)
                    question_model: models.Questions | None = await crud.create_question(params['db'], question)
                    if not rl_model:
                        raise Exception('Failed to insert reading')
                    question_id = question_model.id
                    question_content = question_model.question
                    q_type = question_model.type

                    choices = [schemas.ChoiceCreate(question_id=question_id, **c) for c in q['choices']]
                    choice_model: list[models.Choices] | None = await crud.create_choices(params['db'], choices)
                    if not choice_model:
                        raise Exception('Failed to insert reading')
                        
                    rl_qs.append({
                        'question': question_content,
                        'type': schemas.QuestionType(q_type),
                        'choices': [{
                            'choice': c.choice,
                            'correct': c.correct,
                            'explain': c.expl
                        } for c in choice_model]
                    })
                res['reading'] = rl_qs

                ll = schemas.LessionCreate(video_id=jobs[vid].states['insert_video'].data['id'], type=1)
                ll_model: models.Lessions | None = await crud.create_lession(params['db'], ll)
                
                if not ll_model:
                    raise Exception('Failed to insert listening')
                
                ll_id = ll_model.id
                ll_qs = []
                for q in jobs[vid].states['lessions'].data['listening']:
                    question = schemas.QuestionCreate(question=q['question'], type=q['type'], lession_id=ll_id)
                    question_model: models.Questions | None = await crud.create_question(params['db'], question)
                    if not question_model:
                        raise Exception('Failed to insert listening')
                    question_id = question_model.id
                    question_content = question_model.question
                    q_type = question_model.type

                    choices = [schemas.ChoiceCreate(question_id=question_id, **c) for c in q['choices']]
                    choice_model: list[models.Choices] | None = await crud.create_choices(params['db'], choices)
                    if not choice_model:
                        raise Exception('Failed to insert listening')
                    ll_qs.append({
                        'question': question_content,
                        'type': schemas.QuestionType(q_type),
                        'choices': [{
                            'choice': c.choice,
                            'correct': c.correct,
                            'explain': c.expl
                        } for c in choice_model]
                    })
                res['listening'] = ll_qs
            except Exception as e:
                jobs[vid].states['insert_lessions'].status = Status.FAILED
                jobs[vid].states['insert_lessions'].data = res
                logging.error(f'Failed task insert_lession: {traceback.format_exc()}')
            else:
                jobs[vid].states['insert_lessions'].status = Status.COMPLETED
                jobs[vid].states['insert_lessions'].data = res

        else:
            jobs[vid].states['insert_lessions'].status = Status.FAILED
            logging.error(f'Failed task insert_lession: prerequisite tasks failed')
    for k, s in jobs[vid].states.items():
        if s.status == Status.FAILED:
            jobs[vid].status = Status.FAILED
            logging.warning(f'Task {k}: Failed')
    if jobs[vid].status != Status.FAILED:
        jobs[vid].status = Status.COMPLETED
        logging.info('All tasks completed')

@router.post('/video/create')
async def start_task(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    req: Request,
    background_task: BackgroundTasks,
    url: schemas.RequestVideo
):
    """
    Input:
    :param url: Youtube video URL

    Output:
    - uid: Used for status checking
    - states: List of state of each step:
        - status: 0 -> COMPLETED | 1 -> IN_PROGRESS | 2 -> FAILED
        - data
    
    Create necessary entries to insert to db:
    - **info**: Extract basic video info
    - **subtitles**: Extract and parse subtitles
    - **topic_level**: Call to GPT API to extract topic and cefr level
    - **summarize**: Call to GPT API to extract summarization
    - **vocabulary**: Call to GPT API to extract vocabulary
    - **questions**: Call to GPT API to extract questions
    - **lessions**: Create reading/listening lessions from questions extracted
    - **insert_video**: Insert video entry to db
    - **insert_subs**: Insert subtitle entry to db
    - **insert_vocabs**: Insert vocabulary entry to db
    - **insert lessions**: Insert lession entry to db
    """
    vid_info, subs = extract_url(url.url)
    vid = vid_info['video_id']
    info = {
        'url_id': vid_info['video_id'],
        'video_title': vid_info['video_title'],
        'length': vid_info['length'],
        'thumbnail': vid_info['thumbnail'],
        'channel': vid_info['channel'],
    }
    new_task = Job(
        uid=vid,
        states= {
            'info': Result(
                status=Status.COMPLETED,
                data=info
            ),
            'subtitles': Result(),
            'topic_level': Result(),
            'summarize': Result(),
            'vocabulary': Result(),
            'questions': Result(),
            'lessions': Result(),
            'insert_video': Result(),
            'insert_subs': Result(),
            'insert_vocabs': Result(),
            'insert_lessions': Result()
        }
    )

    params = {
        'db': db,
        'subs': subs,
        'text': ' '.join([s['text'] for s in subs])
    }

    jobs[vid] = new_task
    background_task.add_task(start_video_insert_task, req.app.state.executor, vid, params)
    return JSONResponse(new_task.model_dump(), 202)

@router.get('/video/status')
async def task_status(
    uid: str = Query(description='task uid provided when starting the task')
):
    return jobs[uid]

@router.get('/video/retry')
async def retry_task(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    background_task: BackgroundTasks,
    req: Request,
    uid: str = Query(description='task uid provided when starting the task'),
):
    # Should not done this, fix later if have time

    # Need to re-extract for subtitles -> text to build prompt
    url = f'https://www.youtube.com/watch?v={uid}' 
    _, subs = extract_url(url)
    params = {
        'db': db,
        'subs': subs,
        'text': ' '.join([s['text'] for s in subs])
    }
    background_task.add_task(start_video_insert_task, req.app.state.executor, uid, params, True)
    return JSONResponse(jobs[uid].model_dump(), 202)
    

@router.post('/video', deprecated=True)
async def create_vid(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    d: Annotated[dict, Depends(extract_video_and_sub)]
) -> schemas.ResponseVideo:
    v_model = await crud.create_video(db, schemas.VideoCreate(**d['video']))
    if not v_model:
        raise HTTPException(520, 'Insertion failed')
    video_id = v_model.id
    url_id = v_model.url_id
    topic = v_model.topic
    summary = v_model.summa
    video_level = v_model.level
    
    sub_model = await crud.create_subtitle(db, schemas.SubtitlesCreate(video_id=video_id, auto=d['subtitles']['auto']))
    if not sub_model:
        raise HTTPException(520, 'Insertion failed')
    sub_id = sub_model.id

    lines_model = await crud.create_sub_lines(db, [schemas.SubtitleLinesCreate(sub_id=sub_id, **s) for s in d['subtitles']['lines']])
    if not lines_model:
        raise HTTPException(520, 'Insertion failed')

    res_vocabs = []

    for v in d['vocab']:
        vocab_model = await crud.create_vocab(db, schemas.VocabCreate(**v['vocab']))
        if not vocab_model:
            raise HTTPException(520, 'Insertion failed')
        vocab_id = vocab_model.id
        word = vocab_model.word
        ipa = vocab_model.ipa
        sense_model = await crud.create_sense(db, schemas.SenseCreate(vocab_id=vocab_id, video_id=video_id, **v['sense']))
        if not sense_model:
            raise HTTPException(520, 'Insertion failed')
        pos = sense_model.pos
        sense = sense_model.sense
        level = sense_model.level
        res_vocabs.append(schemas.ResponseVocab(word=word, ipa=ipa, pos=pos, sense=sense, level=schemas.Level(level)))
    
    #reading
    rl_model = await crud.create_lession(db, schemas.LessionCreate(video_id=video_id, type=0))
    if not rl_model:
        raise HTTPException(520, 'Insertion failed')
    rl_id = rl_model.id
    for q in d['reading']:
        question_model = await crud.create_question(db, schemas.QuestionCreate(question=q['question'], type=q['type'], lession_id=rl_id))
        if not question_model:
            raise HTTPException(520, 'Insertion failed')
        question_id = question_model.id
        
        choice_model = await crud.create_choices(db, [schemas.ChoiceCreate(question_id=question_id, **c) for c in q['choices']])
        if not choice_model:
            raise HTTPException(520, 'Insertion failed')
    
    #listening
    ll_model = await crud.create_lession(db, schemas.LessionCreate(video_id=video_id, type=1))
    if not ll_model:
        raise HTTPException(520, 'Insertion failed')
    ll_id = ll_model.id
    for q in d['listening']:
        question_model = await crud.create_question(db, schemas.QuestionCreate(question=q['question'], type=q['type'], lession_id=ll_id))
        if not question_model:
            raise HTTPException(520, 'Insertion failed')
        question_id = question_model.id
        
        choice_model = await crud.create_choices(db, [schemas.ChoiceCreate(question_id=question_id, **c) for c in q['choices']])
        if not choice_model:
            raise HTTPException(520, 'Insertion failed')
    
    return schemas.ResponseVideo(
        clip_id=video_id,
        clip=url_id,
        subtitle=sub_id,
        reading=rl_id,
        listening=ll_id,
        topic=topic,
        summary=summary,
        level=schemas.Level(video_level),
        vocabulary=res_vocabs
    )

async def extract_res_vid(video: models.Videos):
    clip_id = video.id
    clip = video.url_id
    topic = video.topic
    summary = video.summa
    level = schemas.Level(video.level)
    
    sub = await video.awaitable_attrs.sub
    sub_id = sub.id
    
    lessions = await video.awaitable_attrs.lessions
    rs = []
    ls = []
    if (lessions) or (len(lessions) != 0):
        for l in lessions:
            _t = l.type
            lid = l.id
            if _t == 0:
                rs.append(lid)
            if _t == 1:
                ls.append(lid)
    
    reading = 0 if len(rs) == 0 else rs[0]
    listening = 0 if len(ls) == 0 else ls[0]
    
    senses = await video.awaitable_attrs.vocab
    vocab = []
    for s in senses:
        hws = await s.awaitable_attrs.head_word
        vocab.append(schemas.ResponseVocab(word=hws.word, pos=s.pos, sense=s.sense, level=schemas.Level(s.level), ipa=hws.ipa))

    res = schemas.ResponseVideo(
        clip_id=clip_id,
        clip=clip,
        subtitle=sub_id,
        reading=reading,
        listening=listening,
        topic=topic,
        summary=summary,
        level=level,
        vocabulary=vocab
    )

    return res

@router.get('/video')
async def get_vid_by_id(
    id: int = Query(ge=1),
    db: AsyncSession = Depends(get_db_session)
) -> schemas.ResponseVideo:
    video = await crud.get_video(db, id)
    if not video:
        raise HTTPException(404, 'No video')
    
    res = await extract_res_vid(video)
    return res

@router.get('/video/level')
async def get_vid_by_level(
    level: schemas.Level = Query(),
    db: AsyncSession = Depends(get_db_session)
) -> list[schemas.ResponseVideo]:
    videos = await crud.get_videos_by_lv(db, level.value)
    if not videos:
        raise HTTPException(404, 'No video')

    res = [await extract_res_vid(v) for v in videos]

    return res

@router.get('/video/topic')
async def get_vid_by_topic(
    topic: str = Query(),
    db: AsyncSession = Depends(get_db_session)
) -> list[schemas.ResponseVideo]:
    videos = await crud.get_videos_by_topic(db, topic)
    if not videos:
        raise HTTPException(404, 'No video')
    
    res = [await extract_res_vid(v) for v in videos]
    return res

@router.get('/reading')
async def get_read(
    id: int = Query(ge=1),
    db: AsyncSession = Depends(get_db_session)
) -> schemas.ResponseReading:
    lession = await crud.get_lession_by_id(db, id)
    if not lession:
        raise HTTPException(404, 'No lession')
    
    reading = lession.id

    _type = lession.type
    if _type != 0:
        raise HTTPException(404, 'No lession')
    
    qs = await lession.awaitable_attrs.questions
    questions = []
    if (qs) or (len(qs) != 0):
        for q in qs:
            _t = q.type
            question = q.question
            choices = []
            ans = ''
            explain = ''
            cs = await q.awaitable_attrs.choices
            for c in cs:
                choice = c.choice
                correct = c.correct
                expl = c.expl
                choices.append(choice)
                if correct:
                    ans = choice
                    explain = expl
            questions.append(
                schemas.ResponseQuestion(question=question, q_type=schemas.QuestionType(_t), choices=choices, correct=ans, explain=explain)
            )
            
    return schemas.ResponseReading(
        reading=reading,
        questions=questions
    )

@router.get('/listening')
async def get_lis(
    id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db_session)
) -> schemas.ResponseListening:
    lession = await crud.get_lession_by_id(db, id)
    if not lession:
        raise HTTPException(404, 'No lession')
    
    listening = lession.id

    _type = lession.type
    if _type != 1:
        raise HTTPException(404, 'No lession')
    
    qs = await lession.awaitable_attrs.questions
    questions = []
    if (qs) or (len(qs) != 0):
        for q in qs:
            _t = q.type
            question = q.question
            choices = []
            ans = ''
            explain = ''
            cs = await q.awaitable_attrs.choices
            for c in cs:
                choice = c.choice
                correct = c.correct
                expl = c.expl
                choices.append(choice)
                if correct:
                    ans = choice
                    explain = expl
            questions.append(
                schemas.ResponseQuestion(question=question, q_type=schemas.QuestionType(_t), choices=choices, correct=ans, explain=explain)
            )
            
    return schemas.ResponseListening(
        listening=listening,
        questions=questions
    )

@router.get('/subtitle')
async def get_subtitle_by_id(
    id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db_session)
) -> schemas.ResponseSubtitles:
    subtitle = await crud.get_subtitle_by_id(db, id)
    if not subtitle:
        raise HTTPException(404, 'No subtitle')
    
    id = subtitle.id
    video = subtitle.video_id
    lines = await subtitle.awaitable_attrs.lines

    return schemas.ResponseSubtitles(
        id=id,
        video=video,
        lines=[schemas.ResponseSutitleLines(id=l.id, start=l.start, end=l.end, text=l.text) for l in lines]
    )
