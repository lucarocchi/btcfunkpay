from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ._bip32 import derive_address
from ._db import PaymentStore
from ._models import Invoice, PaymentEvent
from ._monitor import Monitor
from ._rpc import BitcoinRPC, RPCError

log = logging.getLogger("btcfunkpay")

_DESCRIPTOR_RANGE = 1000


class PaymentProcessor:
    def __init__(
        self,
        xpub: str,
        rpc_url: str,
        *,
        db_path: str = "btcfunkpay.sqlite",
        required_confirmations: int = 1,
        poll_interval: int = 30,
        expiry_seconds: Optional[int] = 3600,
        mainnet: bool = True,
        wallet_name: str = "btcfunkpay",
    ):
        self._xpub = xpub
        self._mainnet = mainnet
        self._expiry_seconds = expiry_seconds
        self._wallet_name = wallet_name

        rpc_base = rpc_url.rstrip("/")
        # Strip wallet path if present so we can reconstruct both URLs
        if "/wallet/" in rpc_base:
            rpc_base = rpc_base.split("/wallet/")[0]

        self._rpc_base = BitcoinRPC(rpc_base)              # for wallet management
        self._rpc = BitcoinRPC(f"{rpc_base}/wallet/{wallet_name}")  # for wallet ops
        self._store = PaymentStore(db_path)
        self._callbacks: list[Callable] = []
        self._monitor = Monitor(
            self._rpc,
            self._store,
            self._callbacks,
            poll_interval,
            required_confirmations,
        )
        self._thread: Optional[threading.Thread] = None
        self._task: Optional[asyncio.Task] = None

    def _setup_wallet(self) -> None:
        try:
            self._rpc_base.createwallet(self._wallet_name, disable_private_keys=True, blank=True)
        except RPCError as e:
            if e.code not in (-4, -35):
                raise
            try:
                self._rpc_base.loadwallet(self._wallet_name)
            except RPCError as le:
                if le.code != -35:
                    raise

        network = "0h/0h" if self._mainnet else "0h/1h"
        desc = f"wpkh([00000000/84h/{network}]{self._xpub}/0/*)"
        desc_change = f"wpkh([00000000/84h/{network}]{self._xpub}/1/*)"
        try:
            self._rpc.importdescriptors([
                {
                    "desc": desc,
                    "timestamp": "now",
                    "range": [0, _DESCRIPTOR_RANGE],
                    "watchonly": True,
                    "active": True,
                    "internal": False,
                },
                {
                    "desc": desc_change,
                    "timestamp": "now",
                    "range": [0, _DESCRIPTOR_RANGE],
                    "watchonly": True,
                    "active": True,
                    "internal": True,
                },
            ])
        except RPCError as e:
            if e.code == -4:
                # Wallet is rescanning from a previous import — descriptors are already loaded.
                log.info("Wallet rescan already in progress, skipping importdescriptors")
            else:
                raise

    def setup(self) -> None:
        self._setup_wallet()

    def on_payment(self, fn: Callable) -> Callable:
        self._callbacks.append(fn)
        return fn

    def create_invoice(
        self,
        amount_sat: Optional[int] = None,
        label: Optional[str] = None,
        expires_in: Optional[int] = None,
        shipping: Optional[dict[str, Any]] = None,
        billing: Optional[dict[str, Any]] = None,
    ) -> Invoice:
        expiry_secs = expires_in if expires_in is not None else self._expiry_seconds
        expires_at: Optional[datetime] = None
        if expiry_secs is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_secs)

        def _derive(index: int) -> str:
            return derive_address(self._xpub, change=0, index=index, mainnet=self._mainnet)

        return self._store.allocate_and_create_payment(
            self._xpub, _derive, amount_sat, label, expires_at, shipping, billing
        )

    def get_invoice(self, payment_id: str) -> Optional[Invoice]:
        return self._store.get_payment(payment_id)

    def list_invoices(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ):
        return self._store.list_payments(status=status, limit=limit, offset=offset)

    def start(self) -> None:
        """Start the monitoring loop in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            return

        def _run():
            asyncio.run(self._monitor.run())

        self._thread = threading.Thread(target=_run, daemon=True, name="btcfunkpay-monitor")
        self._thread.start()

    async def astart(self) -> asyncio.Task:
        """Create an asyncio Task — use inside an existing event loop (e.g. FastAPI)."""
        self._task = asyncio.create_task(self._monitor.run())
        return self._task

    def stop(self) -> None:
        self._monitor.stop()

    async def astop(self) -> None:
        self.stop()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    def run_forever(self) -> None:
        """Block the calling thread until stop() is called."""
        if self._thread:
            self._thread.join()
