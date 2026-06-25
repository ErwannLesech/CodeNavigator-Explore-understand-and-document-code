from dataclasses import dataclass, field


@dataclass
class DatasetItem:
    id: str
    question: str
    expected_answer: str
    expected_chunks: list[str]
    type: str
    difficulty: str
    module: str
    dataset_version: str


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_file: str
    chunk_type: str
    score: float
    content_excerpt: str


@dataclass
class ChatbotRun:
    id: str
    question: str
    expected_answer: str
    expected_chunks: list[str]
    answer: str
    retrieved_chunks: list[RetrievedChunk]
    duration_ms: float
    tokens: dict[str, int | None]
    model: str
    error: str | None = None


@dataclass
class MetricResult:
    value: float
    details: dict = field(default_factory=dict)
