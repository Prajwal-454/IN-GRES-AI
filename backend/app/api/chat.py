import re
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.followups import build_followups
from app.ai.orchestrator import run as run_orchestrator
from app.ai.assistant import detect_language
from app.ai.rich import build_sections
from app.api.deps import get_current_user
from app.config import get_settings
from app.core.security import decode_token
from app.database import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    BulkDeleteRequest,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatVoiceResponse,
    ConversationCreate,
    ConversationOut,
    FeedbackRequest,
    RegenerateResponse,
)
from app.voice.stt import get_stt_provider
from app.voice.tts import get_tts_provider

router = APIRouter(prefix="/chat", tags=["chat"])

DATA_INTENTS = ("data_query", "forecast", "scenario", "recommend")


def _get_owned_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = Conversation(user_id=user.id, title=data.title, language=data.language)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_owned_conversation(db, conversation_id, user)
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    )


def _conversation_history(db: Session, conv: Conversation, limit: int | None = None) -> list[dict]:
    """Recent messages (oldest first) for multi-turn context carry-over."""
    limit = limit if limit is not None else get_settings().CHAT_MEMORY_TURNS
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return [
        {"role": m.role, "content": m.content, "location": m.location}
        for m in rows
    ]


def _generate_assistant_reply(
    db: Session,
    conv: Conversation,
    message: str,
    language: str,
) -> tuple[Message, int | None]:
    """Run the orchestrator for ``message`` and persist the assistant Message."""
    history = _conversation_history(db, conv)
    graph_answer = run_orchestrator(db, message, language, history=history)
    result = graph_answer.result

    sections = build_sections(db, message, result, graph_answer.context)
    followups = None
    if result.intent in DATA_INTENTS or result.intent == "terminology":
        followups = build_followups(
            graph_answer.context.get("state_name"),
            graph_answer.context.get("district"),
            graph_answer.context.get("village"),
            graph_answer.context.get("metric"),
            result.intent,
        )

    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=result.content,
        language=result.language,
        intent=result.intent,
        location=result.location,
        sources=result.sources or None,
        response_type=result.response_type,
        is_demo=result.is_demo,
        sections=sections,
        followups=followups or None,
    )
    db.add(assistant_msg)
    return assistant_msg, graph_answer.latency_ms


def _answer_message(
    db: Session,
    conv: Conversation,
    message: str,
    language: str | None = None,
) -> ChatResponse:
    language = language or detect_language(message)

    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=message,
        language=language,
    )
    db.add(user_msg)

    assistant_msg, latency_ms = _generate_assistant_reply(db, conv, message, language)

    if not conv.title or conv.title == message[:60]:
        conv.title = message[:60]
    conv.language = language
    db.commit()
    db.refresh(conv)
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return ChatResponse(
        conversation_id=conv.id,
        user_message=ChatMessageOut.model_validate(user_msg),
        assistant_message=ChatMessageOut.model_validate(assistant_msg),
        intent=assistant_msg.intent,
        language=language,
        location=assistant_msg.location,
        latency_ms=latency_ms,
    )


@router.post("/messages", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    data: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.conversation_id is not None:
        conv = _get_owned_conversation(db, data.conversation_id, user)
    else:
        conv = Conversation(user_id=user.id, title=data.message[:60])
        db.add(conv)
        db.flush()

    return _answer_message(db, conv, data.message)


@router.post("/messages/{message_id}/feedback", response_model=ChatMessageOut)
def rate_message(
    message_id: int,
    data: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Thumb up / thumb down an assistant answer (Phase 22 feedback loop)."""
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    conv = db.get(Conversation, msg.conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    if msg.role != "assistant":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Only assistant messages can be rated",
        )
    msg.rating = data.rating
    msg.rating_note = (data.note or "").strip() or None
    db.commit()
    db.refresh(msg)
    return msg


@router.post(
    "/conversations/{conversation_id}/regenerate",
    response_model=RegenerateResponse,
)
def regenerate_answer(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-answer the latest question in the conversation (replaces the reply)."""
    conv = _get_owned_conversation(db, conversation_id, user)
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.asc())
        )
    )
    last_user = next((m for m in reversed(rows) if m.role == "user"), None)
    if last_user is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Conversation has no question to re-answer",
        )
    # Drop every reply produced after that question so the answer is replaced.
    for m in rows:
        if m.id > last_user.id and m.role == "assistant":
            db.delete(m)

    language = last_user.language or detect_language(last_user.content)
    assistant_msg, latency_ms = _generate_assistant_reply(
        db, conv, last_user.content, language
    )
    db.commit()
    db.refresh(assistant_msg)

    return RegenerateResponse(
        conversation_id=conv.id,
        assistant_message=ChatMessageOut.model_validate(assistant_msg),
        intent=assistant_msg.intent,
        language=assistant_msg.language or language,
        location=assistant_msg.location,
        latency_ms=latency_ms,
    )


def _export_markdown(conv: Conversation, messages: list[Message]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {conv.title or 'IN-GRES AI conversation'}",
        "",
        f"_Exported from IN-GRES AI on {now} · {len(messages)} messages_",
        "",
    ]
    for m in messages:
        who = "**You**" if m.role == "user" else "**IN-GRES Assistant**"
        meta = [m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else ""]
        if m.role == "assistant":
            if m.intent:
                meta.append(m.intent)
            if m.location:
                meta.append(m.location)
        stamp = " · ".join(x for x in meta if x)
        lines += [f"### {who} — {stamp}" if stamp else f"### {who}", "", m.content, ""]
        if m.sources:
            lines += ["Sources: " + "; ".join(m.sources), ""]
        if m.followups:
            lines += ["Suggested follow-ups:"]
            lines += [f"- {q}" for q in m.followups]
            lines.append("")
    lines += [
        "---",
        "",
        "Groundwater figures come from the IN-GRES assessment dataset in use.",
        "",
    ]
    return "\n".join(lines)


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the whole conversation as a Markdown transcript."""
    conv = _get_owned_conversation(db, conversation_id, user)
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.asc())
        )
    )
    md = _export_markdown(conv, messages)
    safe_title = re.sub(r"[^A-Za-z0-9]+", "-", (conv.title or "conversation")).strip("-")[:40]
    filename = f"ingres-{safe_title or 'conversation'}-{conv.id}.md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/transcribe")
def transcribe_audio(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Speech-to-text only: mic dictation fills the chat input box.

    The client then sends the recognised text through the normal message flow,
    so the user can see (and correct) what was recognised before the answer is
    produced.
    """
    audio_bytes = audio.file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty audio payload")

    stt = get_stt_provider().transcribe(audio_bytes)
    if not stt.text or not re.search(r"\w", stt.text):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No speech was detected in the audio. Please speak clearly and try again.",
        )
    return {
        "text": stt.text,
        "language": stt.language,
        "confidence": stt.confidence,
        "provider": stt.provider,
    }


@router.post("/voice", response_model=ChatVoiceResponse, status_code=status.HTTP_201_CREATED)
def chat_voice(
    audio: UploadFile = File(...),
    conversation_id: int | None = Form(default=None),
    voice: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mic audio -> speech-to-text (auto-detects language) -> assistant answer
    in that language -> spoken audio (text-to-speech)."""
    if voice not in (None, "male", "female"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "voice must be male or female")
    audio_bytes = audio.file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty audio payload")

    stt = get_stt_provider().transcribe(audio_bytes)
    if not stt.text or not re.search(r"\w", stt.text):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No speech was detected in the audio. Please speak clearly and try again.",
        )

    if conversation_id is not None:
        conv = _get_owned_conversation(db, conversation_id, user)
    else:
        conv = Conversation(user_id=user.id, title=stt.text[:60])
        db.add(conv)
        db.flush()

    response = _answer_message(db, conv, stt.text, language=stt.language)

    tts = get_tts_provider().synthesize(
        response.assistant_message.content,
        response.assistant_message.language or "en",
        voice=voice,
    )
    tts_has_audio = tts.provider not in ("mock", "browser")

    return ChatVoiceResponse(
        conversation_id=response.conversation_id,
        user_message=response.user_message,
        assistant_message=response.assistant_message,
        intent=response.intent,
        language=response.language,
        location=response.location,
        latency_ms=response.latency_ms,
        transcript=stt.text,
        detected_language=stt.language,
        stt_confidence=stt.confidence,
        stt_provider=stt.provider,
        tts_provider=tts.provider,
        tts_has_audio=tts_has_audio,
        audio_format="audio/mpeg" if tts_has_audio else None,
        audio_base64=tts.audio_base64,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = _get_owned_conversation(db, conversation_id, user)
    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    db.delete(conv)
    db.commit()
    return None


@router.post("/conversations/bulk-delete")
def bulk_delete_conversations(
    data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete many conversations at once; foreign ids are silently skipped."""
    deleted: list[int] = []
    for cid in dict.fromkeys(data.ids):
        conv = db.get(Conversation, cid)
        if not conv or conv.user_id != user.id:
            continue
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
        db.delete(conv)
        deleted.append(cid)
    db.commit()
    return {"deleted": deleted, "count": len(deleted)}


async def _ws_auth_user(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, db: Session = Depends(get_db)):
    token = websocket.query_params.get("token")
    user = await _ws_auth_user(token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            message = (payload.get("message") or "").strip()
            if not message:
                continue
            conversation_id = payload.get("conversation_id")
            if conversation_id:
                conv = db.get(Conversation, conversation_id)
                if not conv or conv.user_id != user.id:
                    await websocket.send_json({"error": "conversation not found"})
                    continue
            else:
                conv = Conversation(user_id=user.id, title=message[:60])
                db.add(conv)
                db.flush()

            response = _answer_message(db, conv, message)
            await websocket.send_json(
                {
                    "conversation_id": response.conversation_id,
                    "content": response.assistant_message.content,
                    "intent": response.intent,
                    "language": response.language,
                    "location": response.location,
                    "response_type": response.assistant_message.response_type,
                    "is_demo": response.assistant_message.is_demo,
                    "sections": response.assistant_message.sections,
                    "latency_ms": response.latency_ms,
                }
            )
    except WebSocketDisconnect:
        return