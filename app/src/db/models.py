from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base

#TODO: Fix the schemas | contraints too weak need an overhaul asap

class BaseModel(Base):
    __abstract__ = True

    def model_dump(self):
        return {field.name:getattr(self, field.name) for field in self.__table__.c}

class Videos(BaseModel):
    __tablename__ = 'videos'

    id: Mapped[int] = mapped_column(primary_key=True, index= True)
    url_id: Mapped[str] = mapped_column(index=True, unique=True)
    video_title: Mapped[str]
    length: Mapped[int]
    thumbnail: Mapped[str]
    channel: Mapped[str]
    topic: Mapped[str] = mapped_column(index=True)
    summa: Mapped[str]
    level: Mapped[int] = mapped_column(index=True)

    sub: Mapped['Subtitles'] = relationship(back_populates='video')
    vocab: Mapped[list['Senses']] = relationship(back_populates='video')
    lessions: Mapped[list['Lessions']] = relationship(back_populates='video')

class Senses(BaseModel):
    __tablename__ = 'senses'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sense: Mapped[str]
    pos: Mapped[str]
    level: Mapped[int] = mapped_column(index=True)

    video_id = mapped_column(ForeignKey('videos.id'))
    vocab_id = mapped_column(ForeignKey('vocabs.id'))

    head_word: Mapped['Vocabs'] = relationship(back_populates='senses')
    video: Mapped['Videos'] = relationship(back_populates='vocab')

class Vocabs(BaseModel):
    __tablename__ = 'vocabs'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    word: Mapped[str]
    ipa: Mapped[str]

    senses: Mapped[list['Senses']] = relationship(back_populates='head_word')

class Lessions(BaseModel):
    __tablename__ = 'lessions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type: Mapped[int] = mapped_column(index=True)

    video_id = mapped_column(ForeignKey("videos.id"))

    video: Mapped['Videos'] = relationship(back_populates='lessions')
    questions: Mapped[list['Questions']] = relationship(back_populates='lession')

class Questions(BaseModel):
    __tablename__ = 'questions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question: Mapped[str]
    type: Mapped[int] = mapped_column(index=True)

    lession_id = mapped_column(ForeignKey('lessions.id'))

    lession: Mapped['Lessions'] = relationship(back_populates='questions')
    choices: Mapped[list['Choices']] = relationship(back_populates='question')

class Choices(BaseModel):
    __tablename__ = 'choices'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    choice: Mapped[str]
    correct: Mapped[bool]
    expl: Mapped[str]

    question_id = mapped_column(ForeignKey('questions.id'))

    question: Mapped['Questions'] = relationship(back_populates='choices')

class Subtitles(BaseModel):
    __tablename__ = 'subtitles'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    auto: Mapped[bool]

    video_id = mapped_column(ForeignKey("videos.id"))

    video: Mapped['Videos'] = relationship(back_populates="sub")
    lines: Mapped[list['Lines']] = relationship(back_populates='subtitle')

class Lines(BaseModel):
    __tablename__ = 'lines'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    start: Mapped[str]
    end: Mapped[str]
    text: Mapped[str]

    sub_id = mapped_column(ForeignKey('subtitles.id'))

    subtitle: Mapped['Subtitles'] = relationship(back_populates='lines')
