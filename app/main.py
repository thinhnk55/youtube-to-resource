from contextlib import asynccontextmanager
from concurrent.futures.process import ProcessPoolExecutor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .src.api.routers import proto
from .src.db.models import Base
from .src.db.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.executor = ProcessPoolExecutor()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # Run seperately in another script if instatiate multiple uvicorn workers
    yield
    await engine.dispose()
    app.state.executor.shutdown()

app = FastAPI(lifespan=lifespan, docs_url="/nlp/api/docs", openapi_url="/nlp/openapi.json")

app.include_router(proto.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
