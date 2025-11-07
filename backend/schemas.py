from typing import List, Optional
from pydantic import BaseModel, Field

class Patient(BaseModel):
    name: str
    phone: Optional[str] = None
    mrn: Optional[str] = None
    department: Optional[str] = None
    doctor: Optional[str] = None
    patient_id: Optional[str] = Field(default=None, description="Auto-generated unique patient id")

class BillItem(BaseModel):
    name: str
    qty: int = Field(ge=1)
    price: float = Field(ge=0)

class Bill(BaseModel):
    patient_id: str
    items: List[BillItem] = []
    bill_id: Optional[str] = None
    total: Optional[float] = 0.0

class Inventory(BaseModel):
    name: str
    qty: int = Field(ge=0)
    avg_price: float = Field(ge=0)
