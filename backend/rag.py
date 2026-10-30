"""Retrieval over the trek dataset. TF-IDF by default (no downloads);
set RAG_BACKEND=faiss to use Sentence Transformers + FAISS (falls back to TF-IDF on failure)."""
import logging
import os
import re
from functools import lru_cache

import numpy as np

from .data_loader import load_treks

logger = logging.getLogger(__name__)
_TOKEN = re.compile(r"[a-z0-9]+")

GENERAL_DOCS = [
    ("Acclimatisation", "Acclimatisation: above about 3000 m ascend gradually, take rest days, drink plenty of water, avoid alcohol and never ignore symptoms of altitude sickness such as headache, nausea and dizziness."),
    ("Monsoon trekking", "Monsoon trekking in June to September brings slippery trails, leeches and landslide risk in the Himalaya; Sahyadri fort treks are popular then but carry rain gear and avoid swollen streams."),
    ("Winter trekking", "Winter trekking in December to March needs insulated layers, waterproof boots, gaiters and microspikes for snow; days are short, so start early."),
    ("Fitness preparation", "Fitness preparation: build stamina with running, cycling or stair climbing for 4 to 6 weeks, add leg and core strength training and practise with a loaded backpack."),
]


STOP = set("a an the is are was be to of in on at for and or with what which how do does can i my me you your it this that from by as near about tell".split())


def _tok(text):
    return [w for w in _TOKEN.findall(text.lower()) if w not in STOP]


class _TfIdf:
    def __init__(self, texts):
        toks = [_tok(t) for t in texts]
        self.vocab = {}
        for ts in toks:
            for w in set(ts):
                self.vocab.setdefault(w, len(self.vocab))
        df = np.zeros(len(self.vocab))
        for ts in toks:
            for w in set(ts):
                df[self.vocab[w]] += 1
        self.idf = np.log((1 + len(texts)) / (1 + df)) + 1
        self.matrix = np.vstack([self._vec(ts) for ts in toks])

    def _vec(self, ts):
        v = np.zeros(len(self.vocab))
        for w in ts:
            i = self.vocab.get(w)
            if i is not None:
                v[i] += 1
        v = v * self.idf
        n = np.linalg.norm(v)
        return v / n if n else v

    def search(self, query, k):
        scores = self.matrix @ self._vec(_tok(query))
        return [(int(i), float(scores[i])) for i in np.argsort(-scores)[:k] if scores[i] > 0]


class _Faiss:
    def __init__(self, texts):
        import faiss
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2"))
        emb = self.model.encode(texts, normalize_embeddings=True).astype("float32")
        self.index = faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)

    def search(self, query, k):
        q = self.model.encode([query], normalize_embeddings=True).astype("float32")
        d, i = self.index.search(q, k)
        return [(int(a), float(b)) for b, a in zip(d[0], i[0]) if a >= 0]


class Retriever:
    def __init__(self):
        self.docs = []
        for t in load_treks():
            text = (f"{t['name']} ({t['state']}): {t['difficulty']} trek, {t['duration_days']} days, max altitude "
                    f"{t['max_altitude_m']} m, best season {t['best_season']}, approx cost INR {t['cost_inr']}. "
                    f"Highlights: {', '.join(t['highlights'])}. {t['description']}")
            self.docs.append({"title": t["name"], "text": text})
        self.docs += [{"title": a, "text": b} for a, b in GENERAL_DOCS]
        texts = [d["text"] for d in self.docs]
        self.mode = "tfidf"
        if os.getenv("RAG_BACKEND", "tfidf").lower() == "faiss":
            try:
                self.engine, self.mode = _Faiss(texts), "faiss"
            except Exception as exc:  # missing package / no model download
                logger.warning("FAISS backend unavailable (%s); using TF-IDF", exc)
        if self.mode == "tfidf":
            self.engine = _TfIdf(texts)

    def search(self, query, k=3):
        return [{**self.docs[i], "score": round(s, 3)} for i, s in self.engine.search(query, k)]


@lru_cache(maxsize=1)
def get_retriever():
    return Retriever()
