"""Gemini chatbot with RAG context. Works offline (retrieval-only) when no API key is set."""
import logging
import os

from .rag import get_retriever

logger = logging.getLogger(__name__)

# Default model. Override with GEMINI_MODEL in .env (the .env value wins over this default).
# If a model is rejected, open http://127.0.0.1:8000/api/models to see which models your key can use.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_PROMPT = """You are TrekMate AI, a friendly and knowledgeable trekking assistant.
Help with trekking routes, gear, fitness, safety, permits, budgets, itineraries and seasons,
especially for Indian treks. Reply in the same language as the user (Hindi or English).
Use the KNOWLEDGE BASE below when relevant, and say so if it does not cover the question.
Never invent live weather or claim trail conditions are verified. For dangerous conditions,
prioritise safety and official local guidance. Keep answers practical and clear."""


class ChatError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def _history_contents(types, history):
    out = []
    for item in history[-12:]:
        role, msg = item.get("role"), (item.get("content") or "").strip()
        if role in ("user", "assistant") and msg:
            out.append(types.Content(role="user" if role == "user" else "model",
                                     parts=[types.Part.from_text(text=msg[:4000])]))
    return out


def _gemini_error(exc: Exception, what: str) -> ChatError:
    """Turn a raw Gemini exception into a friendly ChatError (used by chat and photo)."""
    msg = str(exc)
    if "404" in msg or "NOT_FOUND" in msg:
        return ChatError(502, f"Model '{MODEL_NAME}' is unavailable. Check GET /api/models and set GEMINI_MODEL in .env.")
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return ChatError(502, "Gemini quota or rate limit reached. Try again later.")
    if "403" in msg or "PERMISSION_DENIED" in msg or "API key" in msg:
        return ChatError(502, "Gemini access denied. Check your API key and permissions.")
    return ChatError(502, f"{what} failed: {msg[:300]}")


def answer(question: str, history: list) -> dict:
    hits = get_retriever().search(question, k=3)
    sources = [h["title"] for h in hits]
    try:
        client = get_client()
    except Exception as exc:
        raise ChatError(500, f"Could not initialise Gemini client: {str(exc)[:200]}")
    if client is None:
        text = ("Gemini is not configured (add GEMINI_API_KEY to .env), so here is what the local "
                "knowledge base says:\n\n" + "\n\n".join(h["text"] for h in hits)) if hits else \
               "Gemini is not configured and the local knowledge base has nothing on that. Add GEMINI_API_KEY to .env."
        return {"answer": text, "model": None, "mode": "offline", "sources": sources}

    from google.genai import types
    context = "\n".join(f"- {h['text']}" for h in hits) or "(no matching entries)"
    contents = _history_contents(types, history)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
    try:
        resp = client.models.generate_content(
            model=MODEL_NAME, contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=f"{SYSTEM_PROMPT}\n\nKNOWLEDGE BASE:\n{context}",
                max_output_tokens=1200))
        text = (resp.text or "").strip()
        if not text:
            raise ChatError(502, "Gemini returned an empty response. Try again.")
        return {"answer": text, "model": MODEL_NAME, "mode": "gemini", "sources": sources}
    except ChatError:
        raise
    except Exception as exc:
        logger.exception("Chat generation failed")
        raise _gemini_error(exc, "Gemini request")


def health() -> dict:
    client = get_client()
    if client is None:
        raise ChatError(500, "GEMINI_API_KEY is missing in .env.")
    try:
        info = client.models.get(model=MODEL_NAME)
        return {"status": "ok", "model": info.name or MODEL_NAME}
    except Exception as exc:
        raise ChatError(502, f"Gemini model check failed: {str(exc)[:300]}")


def list_models() -> list:
    client = get_client()
    if client is None:
        raise ChatError(500, "GEMINI_API_KEY is missing in .env.")
    try:
        return [m.name for m in client.models.list()
                if "generateContent" in (getattr(m, "supported_actions", None) or [])]
    except Exception as exc:
        raise ChatError(502, str(exc)[:300])


def identify_image(image_bytes: bytes, mime_type: str, note: str = "") -> dict:
    """Ask Gemini (vision) which trek / place a photo most likely shows."""
    try:
        client = get_client()
    except Exception as exc:
        raise ChatError(500, f"Could not initialise Gemini client: {str(exc)[:200]}")
    if client is None:
        raise ChatError(400, "Gemini is not configured (add GEMINI_API_KEY to .env).")

    from google.genai import types

    # Let Gemini prefer treks that exist in your own database when the photo matches one.
    try:
        from .data_loader import load_treks
        known = ", ".join(t["name"] for t in load_treks())
    except Exception:
        known = ""

    prompt = (
        "You are TrekMate, an expert in mountains and trekking trails worldwide. "
        "Look at this photo and predict which trek, trail, peak or place it most likely shows.\n\n"
        "Reply in markdown with:\n"
        "1. **Top 3 guesses**: name, country/state, confidence (High / Medium / Low).\n"
        "2. **Visual clues** you used (peak shape, terrain, vegetation, snow, landmarks, signboards, any text).\n"
        "3. **Quick facts** for the best guess (difficulty, typical duration, best season).\n"
        "4. **What would help confirm it** (another angle, location tag, nearby landmark).\n\n"
        + (f"If the photo plausibly matches one of these treks from our database, use that exact name: {known}.\n\n"
           if known else "")
        + "Be honest: if the photo is too generic to identify, say so instead of guessing confidently. "
        "Never claim certainty. Remind the user to verify route, permits and conditions officially. "
        "Reply in the same language as the user's note if one is given, otherwise English."
        + (f"\n\nUser's note about the photo: {note}" if note else "")
    )
    try:
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
        )
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise _gemini_error(exc, "Gemini image analysis")

    text = (resp.text or "").strip()
    if not text:
        raise ChatError(502, "Gemini returned no answer for this photo. Try a clearer image.")
    return {"answer": text, "model": MODEL_NAME, "mode": "vision", "sources": []}