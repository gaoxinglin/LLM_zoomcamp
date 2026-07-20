import time
import uuid

from .answering import AnswerGenerator, citations_for
from .catalogue import CatalogueClient
from .config import Settings
from .models import AnswerRequest, AnswerResponse, DataQueryPlan, DataQueryResult, SearchRequest
from .retrieval import Retriever
from .storage import Storage


class AssistantService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.retriever = Retriever(storage)
        self.generator = AnswerGenerator(settings)

    def search(self, request: SearchRequest):
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            results = self.retriever.search(request)
            self.storage.log_event(
                request_id=request_id,
                event_type="search",
                query=request.query,
                mode=request.mode.value,
                latency_ms=(time.perf_counter() - started) * 1000,
                result_count=len(results),
            )
            return results
        except Exception as error:
            self.storage.log_event(
                request_id=request_id,
                event_type="search",
                query=request.query,
                mode=request.mode.value,
                latency_ms=(time.perf_counter() - started) * 1000,
                result_count=0,
                error=str(error),
            )
            raise

    def answer(self, request: AnswerRequest) -> AnswerResponse:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            results = self.retriever.search(request)
            generation = self.generator.generate(request.query, results, request.use_llm)
            latency_ms = (time.perf_counter() - started) * 1000
            self.storage.log_event(
                request_id=request_id,
                event_type="answer",
                query=request.query,
                mode=request.mode.value,
                latency_ms=latency_ms,
                result_count=len(results),
                used_llm=int(generation.used_llm),
                prompt_tokens=generation.prompt_tokens,
                completion_tokens=generation.completion_tokens,
            )
            return AnswerResponse(
                answer=generation.text,
                citations=citations_for(results),
                results=results,
                used_llm=generation.used_llm,
                request_id=request_id,
                latency_ms=latency_ms,
            )
        except Exception as error:
            self.storage.log_event(
                request_id=request_id,
                event_type="answer",
                query=request.query,
                mode=request.mode.value,
                latency_ms=(time.perf_counter() - started) * 1000,
                result_count=0,
                error=str(error),
            )
            raise

    def execute_data_query(self, plan: DataQueryPlan) -> DataQueryResult:
        if not self.settings.enable_data_tools:
            raise PermissionError("Data-query tools are disabled. Set ENABLE_DATA_TOOLS=true.")
        dataset = self.storage.get_dataset(plan.dataset_id)
        if dataset is None:
            raise ValueError("Unknown dataset")
        with CatalogueClient(
            self.settings.catalogue_base_url, self.settings.request_timeout_seconds
        ) as catalogue:
            return catalogue.execute_query(plan, dataset)
