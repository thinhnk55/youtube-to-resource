#TODO: Migrate to more powerful lib (Celery, RabbitMQ, Redis for caching messages, etc)

import asyncio
from enum import Enum

from pydantic import BaseModel

class Status(int, Enum):
    COMPLETED = 0
    IN_PROGRESS = 1
    FAILED = 2

class Result(BaseModel):
    status: Status = Status.IN_PROGRESS
    data: dict | list | None = None

class Job(BaseModel):
    uid: str
    status: Status = Status.IN_PROGRESS
    states: dict[str, Result]

jobs: dict[str, Job] = {}

async def run_in_process(executor, fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fn, *args)