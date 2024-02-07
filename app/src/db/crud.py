import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas

logger = logging.getLogger('uvicorn.error')

async def get_video(db: AsyncSession, id: int) -> (models.Videos | None):
    prefix = f'Select video id [{id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        video = await db.get(models.Videos, id)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        if not video:
            logger.warn(f'{prefix}: Not found')
        else:
            logger.info(f'{prefix}: Found')
        return video

async def get_videos(db: AsyncSession, skip: int = 0, limit: int = 10) -> (list[models.Videos] | None):
    prefix = f'Select {limit} videos with offset {skip}'
    logger.info(f'{prefix}: Initiated')
    try:
        statement = select(models.Videos).offset(skip).limit(limit) if limit > 0 else select(models.Videos).offset(skip)
        videos = (await db.scalars(statement)).all()
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: Found {len(videos)}')
        return videos
    
async def get_videos_by_lv(db: AsyncSession, level: int) -> (list[models.Videos] | None):
    prefix = f'Select videos with level of {level}'
    logger.info(f'{prefix}: Initiated')
    try:
        statement = select(models.Videos).filter_by(level=level)
        videos = (await db.scalars(statement)).all()
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: Found {len(videos)}')
        return videos
    
async def get_videos_by_topic(db: AsyncSession, topic: str) -> (list[models.Videos] | None):
    prefix = f'Select videos in {topic}'
    logger.info(f'{prefix}: Initiated')
    try:
        statement = select(models.Videos).filter_by(topic=topic)
        videos = (await db.scalars(statement)).all()
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: Found {len(videos)}')
        return videos

async def create_video(db: AsyncSession, video: schemas.VideoCreate) -> (models.Videos | None):
    prefix = f'Insert {video.video_title}-[{video.url_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        queried = (await db.scalars(select(models.Videos).filter_by(url_id=video.url_id))).one()
    except Exception as e:
        queried = None
    if not queried:
        try:
            db_vid = models.Videos(**video.model_dump())
            db.add(db_vid)
            await db.commit()
            await db.refresh(db_vid)
        except Exception as e:
            logger.error(f'{prefix}: {e}')
            return None
        else:
            logger.info(f'{prefix}: success')
            return db_vid
    else:
        logging.warning(f'{prefix}: Found existing entry')
        return queried
    
async def get_subtitle_by_id(db: AsyncSession, id: int) -> (models.Subtitles | None):
    prefix = f'Select subtitle [{id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_sub = await db.get(models.Subtitles, id)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_sub
    
async def create_subtitle(db: AsyncSession, subtitle: schemas.SubtitlesCreate) -> (models.Subtitles | None):
    prefix = f'Insert {'not auto' if subtitle.auto else 'auto'} subtitle of video [{subtitle.video_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_sub = models.Subtitles(**subtitle.model_dump())
        db.add(db_sub)
        await db.commit()
        await db.refresh(db_sub)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_sub
    
async def create_sub_lines(db: AsyncSession, sub_lines: list[schemas.SubtitleLinesCreate]) -> (list[models.Lines] | None):
    prefix = f'Insert subtitle lines for subtitle [{sub_lines[0].sub_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_lines = [
            models.Lines(**l.model_dump()) for l in sub_lines
        ]
        db.add_all(db_lines)
        await db.commit()
        for l in db_lines:
            await db.refresh(l)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_lines

async def create_vocab(db: AsyncSession, vocab: schemas.VocabCreate) -> (models.Vocabs | None):
    prefix = f'Insert {vocab.word}'
    logger.info(f'{prefix}: Initiated')
    try:
        db_vocab = models.Vocabs(**vocab.model_dump())
        db.add(db_vocab)
        await db.commit()
        await db.refresh(db_vocab)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else: 
        logger.info(f'{prefix}: success')
        return db_vocab

async def create_sense(db: AsyncSession, sense: schemas.SenseCreate) -> (models.Senses | None):
    prefix = f'Insert [{sense.sense}] of vocab {sense.vocab_id} from video {sense.video_id}'
    logger.info(f'{prefix}: Initiated')
    try: 
        db_sense = models.Senses(**sense.model_dump())
        db.add(db_sense)
        await db.commit()
        await db.refresh(db_sense)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_sense

async def get_lession_by_id(db: AsyncSession, id: int) -> (models.Lessions | None):
    prefix = f'Select lession [{id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_lession = await db.get(models.Lessions, id)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_lession

async def create_lession(db: AsyncSession, lession: schemas.LessionCreate) -> (models.Lessions | None):
    prefix = f'Insert lession for video [{lession.video_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_lession = models.Lessions(**lession.model_dump())
        db.add(db_lession)
        await db.commit()
        await db.refresh(db_lession)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_lession

async def create_question(db: AsyncSession, question: schemas.QuestionCreate) -> (models.Questions | None):
    prefix = f'Insert question for lession [{question.lession_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_question = models.Questions(**question.model_dump())
        db.add(db_question)
        await db.commit()
        await db.refresh(db_question)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_question

async def create_choices(db: AsyncSession, choices: list[schemas.ChoiceCreate]) -> (list[models.Choices] | None):
    prefix = f'Insert choice for question [{choices[0].question_id}]'
    logger.info(f'{prefix}: Initiated')
    try:
        db_choices = [models.Choices(**c.model_dump()) for c in choices]
        db.add_all(db_choices)
        await db.commit()
        for db_choice in db_choices:
            await db.refresh(db_choice)
    except Exception as e:
        logger.error(f'{prefix}: {e}')
        return None
    else:
        logger.info(f'{prefix}: success')
        return db_choices
