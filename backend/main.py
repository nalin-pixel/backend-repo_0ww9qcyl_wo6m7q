from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Draw, DrawOut, Prediction, PredictionOut, BulkDraws

app = FastAPI(title="EuroJackpot AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Utility matching and simple learning metadata ---

def count_matches(pred: dict, draw: dict) -> dict:
    main_matches = len(set(pred.get("main", [])) & set(draw.get("main", [])))
    euro_matches = len(set(pred.get("euro", [])) & set(draw.get("euro", [])))
    return {"main": main_matches, "euro": euro_matches, "total": main_matches + euro_matches}


# --- Draws Endpoints ---

@app.get("/test")
def test_root():
    # basic connectivity and counts
    return {
        "ok": True,
        "draws": db["draw"].count_documents({}),
        "predictions": db["prediction"].count_documents({}),
    }


@app.post("/draws", response_model=DrawOut)
def add_draw(draw: Draw):
    # prevent duplicates by date
    existing = db["draw"].find_one({"date": draw.date})
    if existing:
        raise HTTPException(status_code=409, detail="Draw for this date already exists")
    doc = create_document("draw", draw.model_dump())
    return DrawOut.model_validate(doc)


@app.get("/draws", response_model=List[DrawOut])
def list_draws(limit: Optional[int] = 200):
    docs = get_documents("draw", {}, limit=limit, sort=[("date", -1)])
    return [DrawOut.model_validate(d) for d in docs]


@app.put("/draws/{draw_id}", response_model=DrawOut)
def update_draw(draw_id: str, draw: Draw):
    try:
        oid = ObjectId(draw_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    res = db["draw"].find_one_and_update(
        {"_id": oid},
        {"$set": {**draw.model_dump(), "updated_at": datetime.utcnow()}},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Not found")
    return DrawOut.model_validate(res)


@app.delete("/draws/{draw_id}")
def delete_draw(draw_id: str):
    try:
        oid = ObjectId(draw_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    res = db["draw"].delete_one({"_id": oid})
    return {"deleted": res.deleted_count}


@app.delete("/draws")
def clear_draws():
    res = db["draw"].delete_many({})
    return {"deleted": res.deleted_count}


@app.post("/draws/bulk")
def add_draws_bulk(payload: BulkDraws):
    inserted = []
    errors = []

    # Parse CSV
    if payload.csv:
        import csv, io

        reader = csv.reader(io.StringIO(payload.csv))
        for i, row in enumerate(reader):
            if not row or row[0].strip().lower() in ("date", "data"):
                continue
            try:
                d = Draw(
                    date=row[0],
                    main=list(map(int, row[1:6])),
                    euro=list(map(int, row[6:8])),
                )
                doc = create_document("draw", d.model_dump())
                inserted.append(str(doc["_id"]))
            except Exception as e:
                errors.append({"row": i + 1, "error": str(e)})

    # Parse JSON
    if payload.json:
        for i, item in enumerate(payload.json):
            try:
                d = Draw(**item)
                doc = create_document("draw", d.model_dump())
                inserted.append(str(doc["_id"]))
            except Exception as e:
                errors.append({"json_index": i, "error": str(e)})

    # Parse free text
    if payload.text:
        for i, line in enumerate(payload.text.splitlines()):
            if not line.strip():
                continue
            try:
                # Format: YYYY-MM-DD; m1 m2 m3 m4 m5; e1 e2
                parts = [p.strip() for p in line.split(";")]
                d = Draw(
                    date=parts[0],
                    main=list(map(int, parts[1].split()[:5])),
                    euro=list(map(int, parts[2].split()[:2])),
                )
                doc = create_document("draw", d.model_dump())
                inserted.append(str(doc["_id"]))
            except Exception as e:
                errors.append({"line": i + 1, "error": str(e)})

    return {"inserted": inserted, "errors": errors}


# --- Predictions Endpoints ---

@app.post("/predictions", response_model=PredictionOut)
def save_prediction(pred: Prediction):
    # Attach match info against latest draw (if exists)
    latest = db["draw"].find_one(sort=[("date", -1)])
    matched = None
    if latest:
        matched = count_matches(pred.model_dump(), latest)
    doc = create_document("prediction", {**pred.model_dump(), "matched": {"latest_match": matched}})
    return PredictionOut.model_validate(doc)


@app.get("/predictions", response_model=List[PredictionOut])
def list_predictions(limit: Optional[int] = 200):
    docs = get_documents("prediction", {}, limit=limit, sort=[("created_at", -1)])
    return [PredictionOut.model_validate(d) for d in docs]


@app.delete("/predictions")
def clear_predictions():
    res = db["prediction"].delete_many({})
    return {"deleted": res.deleted_count}


# --- Simple insights endpoint ---

@app.get("/insights/latest")
def latest_insights():
    latest = db["draw"].find_one(sort=[("date", -1)])
    if not latest:
        return {"has_latest": False}

    # Count how many past predictions matched at least one number of latest draw
    matched_preds = []
    for p in db["prediction"].find().sort("created_at", -1):
        m = count_matches(p, latest)
        if m["total"] > 0:
            matched_preds.append({"_id": str(p["_id"]), "matches": m})

    return {
        "has_latest": True,
        "latest_date": str(latest.get("date")),
        "matched_predictions": matched_preds,
    }
