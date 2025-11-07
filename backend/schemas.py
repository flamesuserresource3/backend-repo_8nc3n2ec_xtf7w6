from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

# Each class here maps to a MongoDB collection with the class name lowercased

class Patient(BaseModel):
    patient_id: Optional[str] = Field(None, description="System-generated unique patient id")
    name: str
    age: Optional[int] = 0
    gender: Optional[str] = "Other"
    phone: Optional[str] = None
    mrn: Optional[str] = None
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    doctor: Optional[str] = None
    createdAt: Optional[datetime] = None

class BillItem(BaseModel):
    name: str
    qty: int = 1
    price: float = 0.0

class Bill(BaseModel):
    bill_id: Optional[str] = None
    patient_id: str
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor: Optional[str] = None
    mrn: Optional[str] = None
    items: List[BillItem]
    subtotal: float
    tax: float
    total: float
    createdAt: Optional[datetime] = None

class Inventory(BaseModel):
    name: str
    qty: int = 0
    avg_price: float = 0.0
    updatedAt: Optional[datetime] = None
