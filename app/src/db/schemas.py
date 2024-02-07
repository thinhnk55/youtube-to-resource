from __future__ import annotations

from enum import Enum
from random import randint

from pydantic import BaseModel, Field

class SubtitlesBase(BaseModel):
    auto: bool
    video_id: int
    
class Subtitles(SubtitlesBase):
    id: int

class SubtitlesCreate(SubtitlesBase):
    pass

class SubtitleLinesBase(BaseModel):
    sub_id: int
    start: str
    end: str
    text: str

class SubtitleLinesCreate(SubtitleLinesBase):
    pass

class SubtitleLines(SubtitleLinesBase):
    id: int

class VideoBase(BaseModel):
    url_id: str
    video_title: str
    length: int
    thumbnail: str = Field(title='url to thumbnail')
    channel: str = Field(title='channel id of video owner')
    topic: str
    summa: str
    level: int = Field(0)

class VideoCreate(VideoBase):
    pass

class Video(VideoBase):
    id: int

class SenseBase(BaseModel):
    sense: str
    pos: str
    level: int
    video_id: int
    vocab_id: int

class SenseCreate(SenseBase):
    pass

class Sense(SenseBase):
    id: int

class VocabBase(BaseModel):
    word: str
    ipa: str

class VocabCreate(VocabBase):
    pass

class Vocab(VocabBase):
    id: int

class LessionBase(BaseModel):
    video_id: int
    type: int

class LessionCreate(LessionBase):
    pass

class Lession(LessionBase):
    id: int

class QuestionBase(BaseModel):
    question: str
    type: int
    lession_id: int

class QuestionCreate(QuestionBase):
    pass

class Question(QuestionBase):
    id: int

class ChoiceBase(BaseModel):
    choice: str
    correct: bool
    expl: str
    question_id: int

class ChoiceCreate(ChoiceBase):
    pass

class Choice(ChoiceBase):
    id: int

def randLevel():
    mapping = {i:level for i, level in enumerate(Level)}
    return mapping[randint(0, len(mapping) - 1)]

class Level(int, Enum):
    a1 = 0
    a2 = 1
    b1 = 2
    b2 = 3
    c1 = 4
    c2 = 5

class VideoInfo(VideoBase):
    favourite: bool = bool(randint(0, 1))
    level: Level = randLevel()

class ResponseVocab(BaseModel):
    word: str = Field(default='none')
    ipa: str = Field(default='', description='URL to phons file')
    pos: str = Field(default='', description='Part of speech')
    sense: str = Field(default='', description='definition??')
    level: Level = Field(default=Level.a1, description='Level')

class RequestVideo(BaseModel):
    url: str =  Field(min_length=30, max_length=50, pattern=r'^https://www\.youtube\.com/watch\?v=.')

class ResponseVideo(BaseModel):
    clip_id: int = Field(default='', description='Video id')
    clip: str = Field(default='', description='Youtube url/id')
    subtitle: int = Field(default=0, description='Subtitle id')
    reading: int = Field(default=0, description='Reading id')
    listening: int = Field(default=0, description='Listening id')
    topic: str = Field(default='', description='Topic of video')
    summary: str = Field(default='', description='Summary')
    level: Level = Field(default=Level.a1, description='Level')
    vocabulary: list[ResponseVocab] = Field(default=[ResponseVocab()])

class QuestionType(int, Enum):
    MCSA = 0
    MCMA = 1
    SCSA = 2

class ResponseQuestion(BaseModel):
    question: str = Field(default='')
    q_type: QuestionType = Field(default=QuestionType.MCSA)
    choices: list[str] | None = Field(default=['hello'])
    correct: int | list[int] | str = Field(default=0)
    explain: str = Field(default='')

class ResponseReading(BaseModel):
    reading: int = Field(default='', description='Reading id')
    questions: list[ResponseQuestion] = Field(default=ResponseQuestion())

class ResponseListening(BaseModel):
    listening: int = Field(default='', description='Listening id')
    questions: list[ResponseQuestion] = Field(default=ResponseQuestion())

class ResponseSutitleLines(BaseModel):
    id: int = Field(default=0, description='line id')
    start: str = Field(description='start timestamp')
    end: str = Field(description='end timestamp')
    text: str = Field(description='line text')

class ResponseSubtitles(BaseModel):
    id: int = Field(default=0, description='subtitle id')
    video: int = Field(default=0, description='video id')
    lines: list[ResponseSutitleLines]