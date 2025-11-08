from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import MongoClient, ASCENDING, DESCENDING

# Environment variables are provided by the platform
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "appdb")

_client = MongoClient(DATABASE_URL, uuidRepresentation="standard")
db = _client[DATABASE_NAME]

# Ensure basic indexes for our collections when module is imported
# This is idempotent; safe to call on every startup
_db_inited = False

def _ensure_indexes() -> None:
    global _db_inited
    if _db_inited:
        return
    db["draw"].create_index([("date", DESCENDING)])
    db["prediction"].create_index([("created_at", DESCENDING)])
    db["prediction"].create_index([("matched.latest_match", DESCENDING)])
    _db_inited = True

_ensure_indexes()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a document adding created_at/updated_at timestamps.

    Returns the inserted document with _id.
    """
    coll = db[collection_name]
    doc = {**data, "created_at": _now(), "updated_at": _now()}
    res = coll.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: Optional[int] = None, sort: Optional[list] = None) -> list[Dict[str, Any]]:
    """Query documents with optional filter, limit and sort."""
    coll = db[collection_name]
    cursor = coll.find(filter_dict or {})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(int(limit))
    return list(cursor)
