from typing import Any, Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient
import os

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "meditrack")

_client: Optional[MongoClient] = None
_db = None

try:
    _client = MongoClient(DATABASE_URL)
    _db = _client[DATABASE_NAME]
except Exception as e:
    _client = None
    _db = None


def db():
    return _db


def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if _db is None:
        raise RuntimeError("Database not initialized")
    now = datetime.utcnow()
    if "createdAt" not in data:
        data["createdAt"] = now
    data["updatedAt"] = now
    res = _db[collection_name].insert_one(data)
    data["_id"] = str(res.inserted_id)
    return data


def get_documents(collection_name: str, filter_dict: Dict[str, Any] | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    if _db is None:
        raise RuntimeError("Database not initialized")
    docs = []
    for d in _db[collection_name].find(filter_dict or {}).limit(limit).sort("createdAt", -1):
        d["_id"] = str(d["_id"])  # stringify ObjectId
        docs.append(d)
    return docs
