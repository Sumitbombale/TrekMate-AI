# TrekMate AI

Trekking assistant: FastAPI backend + HTML/CSS/JS frontend.

Features: AI chat (Gemini + retrieval), Find a Trek (TrekMatch score), Trek Planner, Compare, Packing, Safety, Live Weather (OpenWeatherMap).

## Run (Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then add your keys
uvicorn backend.main:app --reload
```
Open http://127.0.0.1:8000 (API docs: /docs). Run from the project root, not from inside `backend/`.

## Keys (all optional)
- `GEMINI_API_KEY` - without it, chat answers from the local knowledge base only.
- `OPENWEATHER_API_KEY` - without it, the Weather tab says it is disabled.
- `GEMINI_MODEL` - check valid names at `GET /api/models`.
- `RAG_BACKEND=faiss` - after `pip install sentence-transformers faiss-cpu`; default is TF-IDF.

## Structure
backend/ (main, chatbot, rag, recommender, trek_planner, packing, safety, weather, data_loader, database) · frontend/ · data/treks.csv

## Notes
- `data/treks.csv` is sample data (altitudes, costs, seasons are approximate). Replace with your verified dataset using the same columns; seasons use `Mar-Jun;Sep-Nov` format.
- Itineraries are generic templates, not verified stage-by-stage routes.
- Chat questions/answers are logged to `data/trekmate.db` (SQLite).
