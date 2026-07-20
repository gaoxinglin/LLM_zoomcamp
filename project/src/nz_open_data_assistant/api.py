from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .config import get_settings
from .ingestion import ingest
from .models import (
    AnswerRequest,
    AnswerResponse,
    DataQueryPlan,
    DataQueryResult,
    FeedbackRequest,
    HealthResponse,
    SearchRequest,
    SearchResult,
)
from .service import AssistantService
from .storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    storage = Storage(settings.database_path)
    if storage.count_datasets() == 0:
        from pathlib import Path

        seed_path = Path(__file__).resolve().parents[2] / "data" / "seed_datasets.json"
        ingest(storage, seed_path, seed_only=True)
    app.state.storage = storage
    app.state.service = AssistantService(settings, storage)
    yield


app = FastAPI(
    title="NZ Regional Insights Assistant API",
    version="0.1.0",
    description="Independent student project; not an official New Zealand Government service.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", datasets=request.app.state.storage.count_datasets())


@app.post("/search", response_model=list[SearchResult])
def search(payload: SearchRequest, request: Request):
    return request.app.state.service.search(payload)


@app.post("/answer", response_model=AnswerResponse)
def answer(payload: AnswerRequest, request: Request):
    try:
        return request.app.state.service.answer(payload)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/data-query", response_model=DataQueryResult)
def data_query(payload: DataQueryPlan, request: Request):
    try:
        return request.app.state.service.execute_data_query(payload)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/feedback", status_code=204)
def feedback(payload: FeedbackRequest, request: Request) -> None:
    request.app.state.storage.save_feedback(payload)


@app.get("/metrics")
def metrics(request: Request):
    return request.app.state.storage.metrics()
