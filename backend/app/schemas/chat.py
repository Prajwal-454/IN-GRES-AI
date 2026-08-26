from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    language: str = "en"


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    language: str
    created_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    language: str | None
    intent: str | None
    location: str | None
    sources: list | None
    response_type: str | None
    is_demo: bool

    @field_validator("is_demo", mode="before")
    @classmethod
    def _no_demo_tag(cls, v):
        return False

    sections: dict | None = None
    rating: int | None = None
    rating_note: str | None = None
    followups: list | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    intent: str | None
    language: str | None
    location: str | None
    latency_ms: int | None = None


class ChatVoiceResponse(ChatResponse):
    transcript: str
    detected_language: str
    stt_confidence: float = 0.0
    stt_provider: str = "mock"
    tts_provider: str = "mock"
    tts_has_audio: bool = False
    audio_format: str | None = None
    audio_base64: str | None = None


class FeedbackRequest(BaseModel):
    rating: int
    note: str | None = Field(default=None, max_length=500)

    @field_validator("rating")
    @classmethod
    def _valid_rating(cls, v: int) -> int:
        if v not in (-1, 1):
            raise ValueError("rating must be 1 (helpful) or -1 (not helpful)")
        return v


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class RegenerateResponse(BaseModel):
    conversation_id: int
    assistant_message: ChatMessageOut
    intent: str | None
    language: str | None
    location: str | None
    latency_ms: int | None = None