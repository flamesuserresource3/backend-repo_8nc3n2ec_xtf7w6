import csv
import io
import os
import uuid
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware

from database import db, create_document, get_documents
from schemas import Patient, Bill, BillItem

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers

def generate_patient_id() -> str:
    return f"P-{uuid.uuid4().hex[:8].upper()}"


def upsert_inventory(items: List[BillItem]):
    for it in items:
        coll = db["inventory"]
        existing = coll.find_one({"name": it.name})
        if existing:
            new_qty = int(existing.get("qty", 0)) + int(it.qty)
            current_total_value = float(existing.get("avg_price", 0)) * int(existing.get("qty", 0))
            added_value = float(it.price) * int(it.qty)
            new_avg = (current_total_value + added_value) / max(1, new_qty)
            coll.update_one({"_id": existing["_id"]}, {"$set": {"qty": new_qty, "avg_price": round(new_avg, 2)}})
        else:
            coll.insert_one({"name": it.name, "qty": int(it.qty), "avg_price": float(it.price)})


def require_doctor_or_manager(request: Request):
    role = request.headers.get("X-Role", "").lower()
    if role not in {"doctor", "manager"}:
        raise HTTPException(status_code=403, detail="Only Doctor or Manager can modify billing/medicines")


# Endpoints

@app.get("/")
async def root():
    return {"status": "ok", "service": "MediTrack API"}


@app.post("/patients", response_model=Patient)
async def create_patient(patient: Patient):
    if not patient.patient_id:
        patient.patient_id = generate_patient_id()
    if db["patient"].find_one({"patient_id": patient.patient_id}):
        raise HTTPException(status_code=400, detail="Patient ID already exists")
    create_document("patient", patient)
    return patient


@app.get("/patients/{patient_id}", response_model=Patient)
async def get_patient(patient_id: str):
    doc = db["patient"].find_one({"patient_id": patient_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Patient not found")
    doc.pop("_id", None)
    return doc


@app.post("/bills", response_model=Bill)
async def create_bill(request: Request, bill: Bill):
    require_doctor_or_manager(request)
    p = db["patient"].find_one({"patient_id": bill.patient_id})
    if not p:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    bill.bill_id = f"B-{uuid.uuid4().hex[:8].upper()}"
    bill.total = sum([i.qty * i.price for i in bill.items])
    create_document("bill", bill)
    upsert_inventory(bill.items)
    return bill


@app.get("/bills/by-patient/{patient_id}")
async def bills_by_patient(patient_id: str):
    bills = get_documents("bill", {"patient_id": patient_id})
    for b in bills:
        b["_id"] = str(b["_id"])  # serialize
    return bills


@app.get("/inventory")
async def get_inventory():
    items = get_documents("inventory", {})
    for it in items:
        it["_id"] = str(it["_id"])  # serialize
    return items


@app.post("/bills/upload-csv", response_model=Bill)
async def upload_bill_csv(request: Request, file: UploadFile = File(...), patient_id: Optional[str] = Form(None)):
    require_doctor_or_manager(request)
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    items: List[BillItem] = []

    temp_patient = None
    for row in reader:
        name = row.get("name") or row.get("item")
        qty = int(row.get("qty") or 1)
        price = float(row.get("price") or 0)
        if not name:
            continue
        items.append(BillItem(name=name, qty=qty, price=price))
        if not patient_id:
            pname = row.get("patient_name")
            pphone = row.get("patient_phone")
            mrn = row.get("mrn")
            doctor = row.get("doctor")
            if pname:
                temp_patient = Patient(name=pname, phone=pphone, mrn=mrn, doctor=doctor)

    if not items:
        raise HTTPException(status_code=400, detail="No items found in CSV")

    if not patient_id:
        if temp_patient is None:
            raise HTTPException(status_code=400, detail="CSV must include patient_id or patient_name")
        temp_patient.patient_id = generate_patient_id()
        create_document("patient", temp_patient)
        patient_id = temp_patient.patient_id

    bill = Bill(patient_id=patient_id, items=items)
    bill.bill_id = f"B-{uuid.uuid4().hex[:8].upper()}"
    bill.total = sum([i.qty * i.price for i in bill.items])
    create_document("bill", bill)

    upsert_inventory(items)
    return bill


@app.post("/bills/upload-image", response_model=Bill)
async def upload_bill_image(request: Request, file: UploadFile = File(...), patient_id: Optional[str] = Form(None)):
    require_doctor_or_manager(request)
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required for image uploads")

    items = [BillItem(name=f"Image: {file.filename}", qty=1, price=0.0)]

    bill = Bill(patient_id=patient_id, items=items)
    bill.bill_id = f"B-{uuid.uuid4().hex[:8].upper()}"
    bill.total = sum([i.qty * i.price for i in bill.items])
    create_document("bill", bill)

    upsert_inventory(items)
    return bill


@app.get("/test")
async def test():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
