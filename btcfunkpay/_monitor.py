from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from ._db import PaymentStore
from ._models import Invoice, PaymentEvent, PaymentStatus
from ._rpc import BitcoinRPC, RPCError

log = logging.getLogger("btcfunkpay.monitor")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invoice_to_event(inv: Invoice, is_first_detection: bool, is_first_confirmation: bool) -> PaymentEvent:
    return PaymentEvent(
        payment_id=inv.payment_id,
        address=inv.address,
        txid=inv.txid,
        amount_sat=inv.amount_sat,
        received_sat=inv.received_sat,
        confirmations=inv.confirmations,
        status=inv.status,
        label=inv.label,
        created_at=inv.created_at,
        confirmed_at=inv.confirmed_at,
        is_first_detection=is_first_detection,
        is_first_confirmation=is_first_confirmation,
    )


class Monitor:
    def __init__(
        self,
        rpc: BitcoinRPC,
        store: PaymentStore,
        callbacks: list[Callable],
        poll_interval: int,
        required_confirmations: int,
    ):
        self._rpc = rpc
        self._store = store
        self._callbacks = callbacks
        self._poll_interval = poll_interval
        self._required_confirmations = required_confirmations
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        last_hash = self._store.get_monitor_state("last_block_hash") or ""
        while not self._stop_event.is_set():
            try:
                last_hash = await self._poll_once(last_hash)
                await self._check_expired()
            except RPCError as e:
                if e.code == -28:
                    log.info("Node warming up, retrying in %ds", self._poll_interval)
                else:
                    log.warning("RPC error during poll: %s", e)
            except Exception:
                log.exception("Unexpected error in monitor loop")
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._stop_event.wait()),
                    timeout=self._poll_interval,
                )
                break
            except asyncio.TimeoutError:
                pass

    async def _poll_once(self, last_hash: str) -> str:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._rpc.listsinceblock(last_hash, 0)
            )
        except RPCError as e:
            if e.code in (-5, -8):
                log.warning("last_block_hash invalid (reorg/pruned?), falling back")
                height = await asyncio.get_event_loop().run_in_executor(
                    None, self._rpc.getblockcount
                )
                fallback_height = max(0, height - 144)
                fallback_hash = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._rpc.getblockhash(fallback_height)
                )
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._rpc.listsinceblock(fallback_hash, 0)
                )
            else:
                raise

        watched = self._store.get_watched_addresses()

        for tx in result.get("removed", []):
            addr = tx.get("address")
            inv = self._store.get_payment_by_address(addr)
            if inv is None or inv.status not in (PaymentStatus.CONFIRMED, PaymentStatus.OVERPAID):
                continue
            self._store.update_payment(
                inv.payment_id,
                status=PaymentStatus.DETECTED.value,
                confirmations=0,
                confirmed_at=None,
            )
            inv = self._store.get_payment(inv.payment_id)
            await self._fire_callbacks(_invoice_to_event(inv, False, False))

        for tx in result.get("transactions", []):
            if tx.get("category") != "receive":
                continue
            addr = tx.get("address")
            if addr not in watched:
                continue
            amount_sat = round(tx["amount"] * 1e8)
            confs = max(0, tx.get("confirmations", 0))
            txid = tx.get("txid")
            await self._process_tx(watched[addr], addr, txid, amount_sat, confs)

        new_hash = result.get("lastblock", last_hash)
        self._store.set_monitor_state("last_block_hash", new_hash)
        return new_hash

    async def _process_tx(
        self,
        payment_id: str,
        address: str,
        txid: str,
        amount_sat: int,
        confirmations: int,
    ) -> None:
        inv = self._store.get_payment(payment_id)
        if inv is None or inv.status in (PaymentStatus.EXPIRED,):
            return

        old_status = inv.status
        new_status = old_status
        now = _now()
        confirmed_at = None

        if confirmations >= self._required_confirmations:
            new_status = PaymentStatus.CONFIRMED
            confirmed_at = now
            if inv.amount_sat and amount_sat > inv.amount_sat:
                new_status = PaymentStatus.OVERPAID
        elif confirmations == 0 and old_status == PaymentStatus.PENDING:
            new_status = PaymentStatus.DETECTED

        updates: dict = {
            "txid": txid,
            "received_sat": amount_sat,
            "confirmations": confirmations,
            "status": new_status.value,
        }
        if confirmed_at and not inv.confirmed_at:
            updates["confirmed_at"] = int(confirmed_at.timestamp())

        self._store.update_payment(payment_id, **updates)
        inv = self._store.get_payment(payment_id)

        is_first_detection = (
            old_status == PaymentStatus.PENDING
            and new_status in (PaymentStatus.DETECTED, PaymentStatus.CONFIRMED, PaymentStatus.OVERPAID)
        )
        is_first_confirmation = (
            old_status not in (PaymentStatus.CONFIRMED, PaymentStatus.OVERPAID)
            and new_status in (PaymentStatus.CONFIRMED, PaymentStatus.OVERPAID)
        )

        if new_status != old_status or is_first_detection or is_first_confirmation:
            await self._fire_callbacks(
                _invoice_to_event(inv, is_first_detection, is_first_confirmation)
            )

    async def _check_expired(self) -> None:
        for inv in self._store.list_expired():
            self._store.update_payment(
                inv.payment_id, status=PaymentStatus.EXPIRED.value
            )
            inv = self._store.get_payment(inv.payment_id)
            await self._fire_callbacks(_invoice_to_event(inv, False, False))

    async def _fire_callbacks(self, event: PaymentEvent) -> None:
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    await asyncio.get_event_loop().run_in_executor(None, cb, event)
            except Exception:
                log.exception("Exception in payment callback %s", cb)

    def stop(self) -> None:
        self._stop_event.set()
