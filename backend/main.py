from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from datetime import datetime
import csv
import io

from schemas import Patient, Bill, BillItem
from database import db, create_document, get_documents

app = FastAPI(title="MediTrack API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_patient_id(name: str) -> str:
    base = "PT-" + datetime.utcnow().strftime("%y%m%d")
    suffix = str(abs(hash(name + str(datetime.utcnow().timestamp()))) % 100000).zfill(5)
    return f"{base}-{suffix}"


def upsert_inventory(items: List[BillItem]):
    database = db()
    if database is None:
        return
    for it in items:
        # Increase qty, update avg_price with simple blend
        existing = database["inventory"].find_one({"name": it.name})
        if existing:
            new_qty = int(existing.get("qty", 0)) + int(it.qty)
            new_price = float(it.price)
            database["inventory"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"qty": new_qty, "avg_price": new_price, "updatedAt": datetime.utcnow()}},
            )
        else:
            database["inventory"].insert_one({
                "name": it.name,
                "qty": int(it.qty),
                "avg_price": float(it.price),
                "updatedAt": datetime.utcnow(),
                "createdAt": datetime.utcnow(),
            })


@app.get("/test")
async def test():
    try:
        _ = db()
        return {"ok": True, "message": "DB connected"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/patients", response_model=Patient)
async def create_patient(p: Patient):
    if not p.patient_id:
        p.patient_id = generate_patient_id(p.name)
    payload = p.dict()
    payload["createdAt"] = payload.get("createdAt") or datetime.utcnow()
    saved = create_document("patient", payload)
    return Patient(**saved)


@app.get("/patients/{patient_id}", response_model=Patient)
async def get_patient(patient_id: str):
    docs = get_documents("patient", {"patient_id": patient_id}, limit=1)
    if not docs:
        raise HTTPException(status_code=404, detail="Patient not found")
    return Patient(**docs[0])


@app.post("/bills", response_model=Bill)
async def create_bill(b: Bill):
    if not b.patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")
    payload = b.dict()
    payload["bill_id"] = payload.get("bill_id") or ("B-" + datetime.utcnow().strftime("%y%m%d%H%M%S"))
    payload["createdAt"] = payload.get("createdAt") or datetime.utcnow()
    saved = create_document("bill", payload)
    # Update inventory from billed items
    upsert_inventory(b.items)
    return Bill(**saved)


@app.get("/bills/by-patient/{patient_id}")
async def bills_by_patient(patient_id: str):
    docs = get_documents("bill", {"patient_id": patient_id}, limit=100)
    return docs


@app.get("/inventory")
async def list_inventory(limit: int = 100):
    docs = get_documents("inventory", {}, limit=limit)
    return docs


@app.post("/bills/upload-csv")
async def upload_bill_csv(file: UploadFile = File(...)):
    # Expect CSV with headers: name,qty,price,patient_id,patient_name,patient_phone,doctor,mrn
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except Exception:
        raise HTTPException(400, detail="Invalid file encoding")

    reader = csv.DictReader(io.StringIO(text))
    items: List[BillItem] = []
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor: Optional[str] = None
    mrn: Optional[str] = None

    subtotal = 0.0
    for row in reader:
        if "name" in row and row["name"]:
            qty = int(float(row.get("qty", 1)))
            price = float(row.get("price", 0))
            items.append(BillItem(name=row["name"], qty=qty, price=price))
            subtotal += qty * price
        # capture patient/meta fields if present per-row or just first row
        patient_id = patient_id or row.get("patient_id")
        patient_name = patient_name or row.get("patient_name")
        patient_phone = patient_phone or row.get("patient_phone")
        doctor = doctor or row.get("doctor")
        mrn = mrn or row.get("mrn")

    if not items:
        raise HTTPException(400, detail="CSV contains no items")

    if not patient_id:
        # If not provided, auto-create a patient with given name/phone
        if not patient_name:
            raise HTTPException(400, detail="CSV missing patient_id or patient_name")
        new_patient = Patient(name=patient_name, phone=patient_phone, mrn=mrn)
        new_patient.patient_id = generate_patient_id(patient_name)
        created = create_document("patient", new_patient.dict())
        patient_id = new_patient.patient_id

    tax = round(subtotal * 0.12, 2)
    total = round(subtotal + tax, 2)

    bill = Bill(
        patient_id=patient_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        doctor=doctor,
        mrn=mrn,
        items=items,
        subtotal=subtotal,
        tax=tax,
        total=total,
    )

    saved = create_document("bill", bill.dict())
    # Update inventory
    upsert_inventory(items)
    return saved
