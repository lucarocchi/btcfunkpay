from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.parse import urlencode


class PaymentStatus(str, Enum):
    PENDING = "pending"
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    OVERPAID = "overpaid"


@dataclass
class Invoice:
    payment_id: str
    address: str
    xpub_index: int
    amount_sat: Optional[int]
    label: Optional[str]
    status: PaymentStatus
    created_at: datetime
    expires_at: Optional[datetime]
    txid: Optional[str]
    received_sat: int
    confirmations: int
    confirmed_at: Optional[datetime]

    @property
    def bip21_uri(self) -> str:
        uri = f"bitcoin:{self.address}"
        params: dict = {}
        if self.amount_sat:
            params["amount"] = f"{self.amount_sat / 1e8:.8f}"
        if self.label:
            params["label"] = self.label
        return uri + ("?" + urlencode(params) if params else "")


@dataclass
class PaymentEvent:
    payment_id: str
    address: str
    txid: Optional[str]
    amount_sat: Optional[int]
    received_sat: int
    confirmations: int
    status: PaymentStatus
    label: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]
    is_first_detection: bool
    is_first_confirmation: bool
