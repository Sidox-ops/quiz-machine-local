from __future__ import annotations

import json
import hmac
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .batch_jobs import BatchJobManager
from .certifications import certification
from .config import API_TOKEN, EMBEDDING_MODEL, USER_DATA_DIR
from .corpus import (
    MarkdownCorpusValidationError,
    MarkdownCorpusIssue,
    validate_corpus_payload,
    validate_markdown_corpus,
)
from .ollama_client import OllamaClient, OllamaError
from .progress import ProgressStore
from .question_store import QuestionStore
from .quiz_engine import QuizEngine, QuizGenerationError
from .rag import RagIndex
from .schemas import (
    AnswerRequest,
    AnswerResponse,
    BatchQuizRequest,
    BatchStartResponse,
    BatchStatusResponse,
    CorpusImportRequest,
    CorpusBatchImportResponse,
    CorpusValidationResponse,
    MarkdownCorpusImportRequest,
    MarkdownCorpusBatchImportRequest,
    ModelSelectionRequest,
    NextQuestionRequest,
    ProgressResetRequest,
    PublicQuestion,
    SetupStartResponse,
    SetupStatusResponse,
)
from .system_setup import SetupManager, diagnostics

client = OllamaClient()
rag = RagIndex(client)
progress = ProgressStore()
questions = QuestionStore()
engine = QuizEngine(client, rag, progress, questions)
batches = BatchJobManager(engine)
setup = SetupManager(client, rag)

app = FastAPI(title="Microsoft AI Certification Quiz Machine", version="0.5.0")


@app.middleware("http")
async def require_session_token(request: Request, call_next):
    supplied = request.headers.get("Authorization", "")
    if API_TOKEN and not hmac.compare_digest(supplied, f"Bearer {API_TOKEN}"):
        return JSONResponse(status_code=401, content={"detail": "Invalid session token."})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    try:
        models = client.list_model_details()
        selected = client.configured_model()
        return {
            "ok": True,
            "llm_model": selected,
            "recommended_llm_model": client.recommend_model(models) or "",
            "embedding_model": EMBEDDING_MODEL,
            "ollama_models": [model.name for model in models],
            "knowledge_provider": rag.knowledge_provider,
            "index_ready": rag.knowledge_ready,
            "indexed_chunks": rag.indexed_chunk_count,
        }
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/system/diagnostics")
def system_diagnostics() -> dict:
    return diagnostics(client, rag)


@app.post("/system/setup", response_model=SetupStartResponse)
def start_setup() -> SetupStartResponse:
    return SetupStartResponse.model_validate(setup.start())


@app.get("/system/setup", response_model=SetupStatusResponse)
def setup_status() -> SetupStatusResponse:
    return SetupStatusResponse.model_validate(setup.state())


@app.post("/system/model")
def select_system_model(request: ModelSelectionRequest) -> dict:
    if batches.has_active_jobs():
        raise HTTPException(
            status_code=409,
            detail="The local model cannot change while a quiz batch is running.",
        )
    try:
        inventory = client.list_model_details()
        client.set_selected_model(request.model.strip(), inventory)
        return diagnostics(client, rag)
    except OllamaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/corpus/validate", response_model=CorpusValidationResponse)
def validate_corpus(request: CorpusImportRequest) -> CorpusValidationResponse:
    if not request.rights_confirmed:
        raise HTTPException(status_code=400, detail="Content rights must be confirmed.")
    try:
        return CorpusValidationResponse.model_validate(validate_corpus_payload(request.corpus))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/corpus/import", response_model=CorpusValidationResponse)
def import_corpus(request: CorpusImportRequest) -> CorpusValidationResponse:
    if not request.rights_confirmed:
        raise HTTPException(status_code=400, detail="Content rights must be confirmed.")
    try:
        summary = validate_corpus_payload(request.corpus)
        serialized = json.dumps(request.corpus, ensure_ascii=False, indent=2)
        if len(serialized.encode("utf-8")) > 5 * 1024 * 1024:
            raise ValueError("The corpus exceeds the 5 MB import limit.")
        stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", request.filename).strip(".-")
        if not stem:
            stem = "imported-corpus"
        if not stem.lower().endswith(".json"):
            stem += ".json"
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        target = USER_DATA_DIR / stem
        previous_content = target.read_bytes() if target.exists() else None
        target.write_text(serialized, encoding="utf-8")
        try:
            client.assert_required_models()
            rag.build()
        except (OllamaError, RuntimeError, ValueError, OSError):
            if previous_content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous_content)
            raise
        return CorpusValidationResponse.model_validate(summary)
    except (OllamaError, RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/corpus/markdown/validate", response_model=CorpusValidationResponse)
def validate_markdown(
    request: MarkdownCorpusImportRequest,
) -> CorpusValidationResponse:
    if not request.rights_confirmed:
        raise HTTPException(status_code=400, detail="Content rights must be confirmed.")
    try:
        return CorpusValidationResponse.model_validate(
            validate_markdown_corpus(request.content, request.filename)
        )
    except MarkdownCorpusValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc


@app.post("/corpus/markdown/import", response_model=CorpusValidationResponse)
def import_markdown(
    request: MarkdownCorpusImportRequest,
) -> CorpusValidationResponse:
    if not request.rights_confirmed:
        raise HTTPException(status_code=400, detail="Content rights must be confirmed.")
    try:
        summary = validate_markdown_corpus(request.content, request.filename)
        target_name = f"{summary['document_id']}.md"
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        target = USER_DATA_DIR / target_name
        previous_content = target.read_bytes() if target.exists() else None
        temporary = target.with_suffix(".md.tmp")
        temporary.write_text(request.content, encoding="utf-8")
        temporary.replace(target)
        try:
            client.assert_required_models(require_embedding=True)
            rag.build()
            invalidate = getattr(rag, "invalidate_generation_corpus", None)
            if callable(invalidate):
                invalidate(summary["certification_code"])
        except (OllamaError, RuntimeError, ValueError, OSError):
            if previous_content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous_content)
            raise
        return CorpusValidationResponse.model_validate(summary)
    except MarkdownCorpusValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc
    except (OllamaError, RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/corpus/markdown/import-batch",
    response_model=CorpusBatchImportResponse,
)
def import_markdown_batch(
    request: MarkdownCorpusBatchImportRequest,
) -> CorpusBatchImportResponse:
    if not request.rights_confirmed:
        raise HTTPException(status_code=400, detail="Content rights must be confirmed.")
    try:
        summaries = [
            validate_markdown_corpus(item.content, item.filename)
            for item in request.files
        ]
        document_ids = [summary["document_id"] for summary in summaries]
        duplicates = sorted({
            value for value in document_ids if document_ids.count(value) > 1
        })
        if duplicates:
            raise MarkdownCorpusValidationError([
                MarkdownCorpusIssue(
                    code="duplicate_document_id",
                    field="document_id",
                    message=f"The document id `{value}` appears more than once.",
                    hint="Give every imported corpus a unique document_id.",
                )
                for value in duplicates
            ])

        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        targets = [
            USER_DATA_DIR / f"{summary['document_id']}.md"
            for summary in summaries
        ]
        previous = {
            target: target.read_bytes() if target.exists() else None
            for target in targets
        }
        temporary_paths: list = []
        try:
            for source, target in zip(request.files, targets):
                temporary = target.with_suffix(".md.tmp")
                temporary_paths.append(temporary)
                temporary.write_text(source.content, encoding="utf-8")
                temporary.replace(target)
            client.assert_required_models(require_embedding=True)
            rag.build()
            invalidate = getattr(rag, "invalidate_generation_corpus", None)
            for certification_code in {
                summary["certification_code"] for summary in summaries
            }:
                if callable(invalidate):
                    invalidate(certification_code)
        except (OllamaError, RuntimeError, ValueError, OSError):
            for temporary in temporary_paths:
                temporary.unlink(missing_ok=True)
            for target, content in previous.items():
                if content is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(content)
            raise
        return CorpusBatchImportResponse.model_validate({
            "files": summaries,
            "file_count": len(summaries),
            "chunk_count": sum(item["chunk_count"] for item in summaries),
        })
    except MarkdownCorpusValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.public_detail()) from exc
    except (OllamaError, RuntimeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/catalog")
def catalog(certification_code: str = "AI-103") -> dict:
    try:
        return rag.catalog(certification_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/index/rebuild")
def rebuild_index() -> dict:
    try:
        client.assert_required_models()
        count = rag.build()
        return {"ok": True, "indexed_chunks": count}
    except (OllamaError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/quiz/next", response_model=PublicQuestion)
def next_question(request: NextQuestionRequest) -> PublicQuestion:
    """Single-question endpoint kept for the terminal client and debugging."""
    try:
        client.assert_required_models(require_embedding=rag.requires_local_embeddings)
        return engine.generate(
            certification_code=request.certification_code,
            mode=request.mode,
            domain=request.domain,
            chapter_id=request.chapter_id,
            difficulty=request.difficulty,
            question_type=request.question_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OllamaError, QuizGenerationError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/quiz/batch", response_model=BatchStartResponse)
def start_batch(request: BatchQuizRequest) -> BatchStartResponse:
    try:
        certification(request.certification_code)
        client.assert_required_models(require_embedding=rag.requires_local_embeddings)
        if request.mode == "domain" and not request.domain:
            raise HTTPException(status_code=400, detail="Domain mode requires a domain.")
        if request.mode == "chapter" and not request.chapter_id:
            raise HTTPException(status_code=400, detail="Chapter mode requires a chapter_id.")
        job = batches.start(
            certification_code=request.certification_code,
            count=request.count,
            mode=request.mode,
            domain=request.domain,
            chapter_id=request.chapter_id,
            difficulty=request.difficulty,
            question_type=request.question_type,
        )
        return BatchStartResponse.model_validate(job)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/quiz/batch/{job_id}", response_model=BatchStatusResponse)
def batch_status(job_id: str) -> BatchStatusResponse:
    job = batches.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return BatchStatusResponse.model_validate(job)


@app.post("/quiz/batch/{job_id}/cancel", response_model=BatchStatusResponse)
def cancel_batch(job_id: str) -> BatchStatusResponse:
    job = batches.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return BatchStatusResponse.model_validate(job)


@app.post("/quiz/answer", response_model=AnswerResponse)
def answer(request: AnswerRequest) -> AnswerResponse:
    try:
        payload = engine.answer(
            request.question_id,
            request.selected_option_id,
            elapsed_seconds=request.elapsed_seconds,
        )
        return AnswerResponse.model_validate(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found") from exc


@app.get("/progress")
def get_progress(certification_code: str | None = None) -> dict:
    try:
        selected = certification(certification_code).code if certification_code else None
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return progress.report(selected)


@app.post("/progress/reset")
def reset_progress(request: ProgressResetRequest) -> dict:
    if request.scope == "certification" and not request.certification_code:
        raise HTTPException(
            status_code=422,
            detail="A certification code is required for this reset.",
        )
    try:
        selected = (
            certification(request.certification_code).code
            if request.certification_code
            else None
        )
        return progress.reset(request.scope, selected)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
