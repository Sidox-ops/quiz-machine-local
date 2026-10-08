from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


Difficulty = Literal["easy", "medium", "hard"]
RequestedDifficulty = Literal["random", "easy", "medium", "hard"]
SelectionMode = Literal["shuffle", "domain", "chapter"]
QuestionType = Literal["standard", "case_study"]
RequestedQuestionType = Literal["mixed", "standard", "case_study"]
BatchStatus = Literal[
    "queued",
    "generating",
    "retrying",
    "completed",
    "cancelled",
    "failed",
]
BatchPhase = Literal["queued", "preparing_corpus", "generating_questions", "done"]
ProgressResetScope = Literal[
    "recent_activity",
    "adaptive_profile",
    "certification",
    "all",
]
CaseStudyRequirement = Annotated[str, Field(min_length=1, max_length=500)]
StableOptionId = Annotated[str, Field(pattern=r"^opt_[1-9][0-9]*$")]
SourceId = Annotated[str, Field(min_length=1, max_length=200)]


class QuizOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StableOptionId
    text: str = Field(min_length=1, max_length=500)


class OptionExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: StableOptionId
    explanation: str = Field(min_length=1, max_length=1200)


class ExplanationRationale(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: StableOptionId
    rationale: str = Field(min_length=1, max_length=900)


class OptionEvidenceAssessment(BaseModel):
    """Evidence verdict for one frozen candidate option."""

    model_config = ConfigDict(extra="forbid")

    option_id: StableOptionId
    verdict: Literal["supported", "contradicted", "not_established", "equivalent"]
    supporting_source_ids: list[SourceId]


class BlueprintSourceMapping(BaseModel):
    """Official objective and Learn unit that ground a persisted question."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    exam_domain: str = Field(min_length=1, max_length=300)
    skill_objective: str = Field(min_length=1, max_length=500)
    learn_source_id: SourceId
    learn_url: str = Field(pattern=r"^https://learn\.microsoft\.com/")
    learn_unit: str | None = Field(default=None, max_length=300)
    blueprint_url: str = Field(
        pattern=r"^https://learn\.microsoft\.com/credentials/certifications/resources/study-guides/"
    )


class CaseStudyContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=120)
    scenario: str = Field(min_length=80, max_length=3000)
    requirements: tuple[CaseStudyRequirement, ...] = Field(min_length=2, max_length=5)


class QuestionCandidate(BaseModel):
    """Untrusted output of the isolated question-generation call."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "insufficient_context"]
    question_type: QuestionType
    case_study: CaseStudyContext | None = None
    question: str = Field(min_length=1, max_length=1200)
    options: list[QuizOption]
    correct_option_id: StableOptionId
    supporting_source_ids: list[SourceId]
    topic: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=300)
    difficulty: Difficulty
    confidence: float = Field(ge=0.0, le=1.0)


class QuestionValidation(BaseModel):
    """Untrusted output of the evidence-only validation call."""

    model_config = ConfigDict(extra="forbid")

    question_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["accept", "reject"]
    correct_option_id: StableOptionId
    supported_option_ids: list[StableOptionId]
    option_assessments: list[OptionEvidenceAssessment]
    supporting_source_ids: list[SourceId]
    issues: list[str] = Field(max_length=10)


class CanonicalQuestion(BaseModel):
    """Validated and immutable question facts. Presentation order is separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    certification_code: str = Field(pattern=r"^AI-[0-9]{3}$")
    learning_objective: str = Field(min_length=1, max_length=300)
    question_type: QuestionType
    case_study: CaseStudyContext | None = None
    question: str
    options: tuple[QuizOption, ...]
    correct_option_id: StableOptionId
    supporting_source_ids: tuple[SourceId, ...]
    blueprint_mappings: tuple[BlueprintSourceMapping, ...]
    topic: str
    domain: str
    difficulty: Difficulty


class ExplanationDraft(BaseModel):
    """ID-bound rationales; the server, not the model, names the options."""

    model_config = ConfigDict(extra="forbid")

    question_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    correct_option_id: StableOptionId
    rationales: list[ExplanationRationale]
    decisive_clue: str = Field(min_length=10, max_length=500)
    learning_rule: str = Field(min_length=10, max_length=700)
    takeaway: str = Field(min_length=5, max_length=400)


class GeneratedQuiz(BaseModel):
    """Final deterministic artifact stored locally after every quality gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical: CanonicalQuestion
    presentation_option_ids: tuple[StableOptionId, ...]
    explanation: str
    option_explanations: tuple[OptionExplanation, ...]
    source_urls: tuple[str, ...] = ()
    decisive_clue: str = ""
    learning_rule: str = ""
    takeaway: str = ""


class PublicQuestion(BaseModel):
    question_id: str
    certification_code: str = "AI-103"
    question_type: QuestionType
    case_study: CaseStudyContext | None = None
    question: str
    options: list[QuizOption]
    learning_objective: str
    blueprint_mappings: list[BlueprintSourceMapping]
    topic: str
    domain: str
    difficulty: Difficulty
    supporting_source_ids: list[str]


class NextQuestionRequest(BaseModel):
    certification_code: str = Field(default="AI-103", pattern=r"^AI-[0-9]{3}$")
    mode: SelectionMode = "shuffle"
    domain: str | None = None
    chapter_id: str | None = None
    difficulty: RequestedDifficulty = "random"
    question_type: RequestedQuestionType = "mixed"


class BatchQuizRequest(NextQuestionRequest):
    count: int = Field(default=5, ge=1, le=50)


class BatchStartResponse(BaseModel):
    job_id: str
    status: BatchStatus
    total: int
    completed: int
    attempts: int = 0
    rejected: int = 0
    reused: int = 0
    phase: BatchPhase = "queued"
    corpus_completed: int = 0
    corpus_total: int = 0
    corpus_attempts: int = 0
    corpus_retries: int = 0
    message: str = ""


class BatchStatusResponse(BaseModel):
    job_id: str
    status: BatchStatus
    total: int
    completed: int
    attempts: int = 0
    rejected: int = 0
    reused: int = 0
    phase: BatchPhase = "queued"
    corpus_completed: int = 0
    corpus_total: int = 0
    corpus_attempts: int = 0
    corpus_retries: int = 0
    questions: list[PublicQuestion] = Field(default_factory=list)
    error: str | None = None
    last_error: str | None = None
    message: str = ""


class AnswerRequest(BaseModel):
    question_id: str
    selected_option_id: StableOptionId
    elapsed_seconds: float | None = Field(default=None, ge=0, le=86400)


class AnswerResponse(BaseModel):
    correct: bool
    selected_option_id: str
    correct_option_id: str
    explanation: str
    option_explanations: list[OptionExplanation]
    topic: str
    domain: str
    supporting_source_ids: list[str]
    source_urls: list[str] = Field(default_factory=list)
    decisive_clue: str = ""
    learning_rule: str = ""
    selected_option_feedback: str = ""
    correct_option_feedback: str = ""
    takeaway: str = ""
    next_focus: str | None = None
    progress: dict


class ProgressResetRequest(BaseModel):
    scope: ProgressResetScope
    certification_code: str | None = Field(
        default=None,
        pattern=r"^AI-[0-9]{3}$",
    )


class CorpusImportRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    corpus: dict
    rights_confirmed: bool


class MarkdownCorpusImportRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    rights_confirmed: bool


class MarkdownCorpusFile(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5 * 1024 * 1024)


class MarkdownCorpusBatchImportRequest(BaseModel):
    files: list[MarkdownCorpusFile] = Field(min_length=1, max_length=50)
    rights_confirmed: bool


class CorpusValidationResponse(BaseModel):
    title: str
    language: str
    chunk_count: int
    document_id: str | None = None
    certification_code: str | None = None
    domain: str | None = None
    source_url: str | None = None


class CorpusBatchImportResponse(BaseModel):
    files: list[CorpusValidationResponse]
    file_count: int
    chunk_count: int


class SetupStartResponse(BaseModel):
    status: str


class SetupStatusResponse(BaseModel):
    status: Literal["idle", "running", "completed", "failed"]
    stage: str
    message: str


class ModelSelectionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
