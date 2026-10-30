"""TrekMate AI - FastAPI backend. Run from the project root:  uvicorn backend.main:app --reload"""
import difflib
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Literal, Optional, Union

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import chatbot, database, packing, photos, recommender, safety, trek_planner, weather  # noqa: E402
from .data_loader import get_trek, load_treks  # noqa: E402

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

# Words that mean "the user wants pictures"
PHOTO_WORDS = {"image", "images", "photo", "photos", "picture", "pictures", "pic", "pics",
               "photograph", "photographs", "dikhao", "tasveer", "tasveerein", "foto"}
# Filler words removed when we extract the place name from a photo request
FILLER_WORDS = PHOTO_WORDS | {
    "give", "show", "me", "send", "see", "get", "find", "some", "of", "the", "a", "an", "please",
    "pls", "can", "you", "i", "want", "to", "for", "any", "view", "views", "about", "and", "with",
    "info", "information", "details", "tell", "its", "it", "my", "also", "plus", "kindly", "do",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="TrekMate AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(","),
    allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

Month = Optional[Union[int, str]]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: List[dict] = Field(default_factory=list, max_length=12)


class RecommendRequest(BaseModel):
    difficulty: Optional[Literal["Easy", "Moderate", "Difficult"]] = None
    max_days: Optional[int] = Field(None, ge=1, le=30)
    max_budget: Optional[int] = Field(None, ge=0)
    month: Month = None
    state: Optional[str] = None
    top_n: int = Field(5, ge=1, le=15)


class PlanRequest(BaseModel):
    trek: str
    days: Optional[int] = Field(None, ge=1, le=30)
    month: Month = None
    group_size: int = Field(1, ge=1, le=100)


class CompareRequest(BaseModel):
    treks: List[str] = Field(min_length=2, max_length=4)


class PackingRequest(BaseModel):
    trek: str
    month: Month = None


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except chatbot.ChatError as e:
        raise HTTPException(e.status, e.detail)


def _match_trek(question: str):
    """Find which trek (from your database) a question is about. Tolerates small
    spelling differences, e.g. 'raigad' still matches 'Rajgad'."""
    q = question.lower()
    treks_list = load_treks()
    # 1) exact: full trek name, or its first word, appears in the question
    for t in treks_list:
        name = t["name"].lower()
        if name in q or (len(name.split()[0]) >= 5 and name.split()[0] in q):
            return t
    # 2) fuzzy: a word in the question is very close to a trek's first word
    firsts = {t["name"].lower().split()[0]: t for t in treks_list}
    for word in re.findall(r"[a-z']+", q):
        if len(word) >= 5:
            close = difflib.get_close_matches(word, list(firsts), n=1, cutoff=0.78)
            if close:
                return firsts[close[0]]
    return None


def _wants_photos(question: str) -> bool:
    return any(w in PHOTO_WORDS for w in re.findall(r"[a-zA-Z]+", question.lower()))


def _photo_subject(question: str) -> str:
    """'give raigad images' -> 'raigad'. Used when the place is not in the database."""
    words = [w for w in re.findall(r"[a-zA-Z']+", question) if w.lower() not in FILLER_WORDS]
    return " ".join(words).strip()[:80]


def _find_photos(*queries: str, n: int = 2) -> list:
    """Try several search texts in order until one returns photos."""
    for q in queries:
        if q and q.strip():
            found = photos.search_photos(q, n)
            if found:
                return found
    return []


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/status")
def status():
    return {"gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "weather_configured": bool(os.getenv("OPENWEATHER_API_KEY")),
            "model": chatbot.MODEL_NAME, "treks": len(load_treks())}


@app.get("/api/health")
def health():
    return _run(chatbot.health)


@app.get("/api/models")
def models():
    return {"models": _run(chatbot.list_models)}


@app.get("/api/treks")
def treks():
    return load_treks()


@app.get("/api/photos")
def trek_photos(q: str = Query(..., min_length=2, max_length=100), n: int = Query(2, ge=1, le=4)):
    """Free photos (Wikimedia Commons) for any search text."""
    return {"photos": photos.search_photos(q, n)}


@app.post("/api/chat")
def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        raise HTTPException(400, "Please enter a question.")

    trek = _match_trek(q)
    wants = _wants_photos(q)

    # Decide what to search photos for
    pics, subject = [], ""
    if trek:
        subject = trek["name"]
        place = f"{trek['name']} {trek.get('state', '')}".strip()
        pics = _find_photos(place, trek["name"], f"{trek['name']} fort")
    elif wants:
        subject = _photo_subject(q)
        pics = _find_photos(subject, f"{subject} fort", f"{subject} trek")

    # If photos will be shown, tell Gemini so it does not say "I can't show images"
    q_for_ai = q
    if pics and wants:
        q_for_ai = (q + "\n\n[Note to assistant: the app automatically shows photos below your reply, "
                    "so never say you cannot show images. Just give a short, helpful description with key facts.]")

    result = _run(chatbot.answer, q_for_ai, req.history)

    if pics:
        result["photos"] = pics
        result["trek"] = subject
    elif wants and subject:
        result["answer"] += f"\n\n(I couldn't find free photos for \"{subject}\" on Wikimedia Commons.)"

    database.log_chat(q, result["answer"], result["mode"])
    return result


@app.post("/api/identify-image")
def identify_image_route(image: UploadFile = File(...), note: str = Form("")):
    """Photo upload -> Gemini vision predicts which trek/place it shows."""
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Upload a JPG, PNG or WebP image.")
    data = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 5 MB).")
    if not data:
        raise HTTPException(400, "The uploaded image is empty.")
    note = note.strip()[:300]
    result = _run(chatbot.identify_image, data, image.content_type, note)
    database.log_chat("[photo] " + note, result["answer"], result["mode"])
    return result


@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    return {"results": recommender.recommend(**req.model_dump())}


@app.post("/api/plan")
def plan(req: PlanRequest):
    return _run(trek_planner.plan, req.trek, req.days, req.month, req.group_size)


@app.post("/api/compare")
def compare(req: CompareRequest):
    return _run(recommender.compare, req.treks)


@app.post("/api/packing")
def packing_list(req: PackingRequest):
    return _run(packing.packing_list, req.trek, req.month)


@app.get("/api/safety")
def safety_info(trek: Optional[str] = None, topic: Optional[str] = None):
    return _run(safety.get_safety, trek, topic)


@app.get("/api/weather")
def weather_info(trek: str):
    t = get_trek(trek)
    if not t:
        raise HTTPException(404, f"Unknown trek: {trek}")
    return {"trek": t["name"], **weather.get_weather(t["lat"], t["lon"])}