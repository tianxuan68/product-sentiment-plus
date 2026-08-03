from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ProductBody(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    categoryId: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = None
    originalPrice: Optional[Decimal] = None
    currency: Optional[str] = "CNY"
    coverUrl: Optional[str] = None
    rating: Optional[Decimal] = None
    stock: Optional[int] = 0
    unit: Optional[str] = None
    status: Optional[int] = 1
    description: Optional[str] = None
    note: Optional[str] = None
