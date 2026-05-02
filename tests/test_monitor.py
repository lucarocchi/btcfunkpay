import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from btcfunkpay._db import PaymentStore
from btcfunkpay._models import PaymentStatus
from btcfunkpay._monitor import Monitor
from btcfunkpay._rpc import BitcoinRPC


def _make_store():
    return PaymentStore(":memory:")


def _make_rpc():
    return MagicMock(spec=BitcoinRPC)


def _make_monitor(store, rpc, callbacks=None, required_confirmations=1):
    mon = Monitor(rpc, store, callbacks or [], poll_interval=1, required_confirmations=required_confirmations)
    mon._stop_event = asyncio.Event()
    return mon


def _make_listsinceblock(transactions=None, removed=None, lastblock="abc"):
    return {
        "transactions": transactions or [],
        "removed": removed or [],
        "lastblock": lastblock,
    }


def _receive_tx(address, amount_btc, txid="tx1", confirmations=0):
    return {
        "category": "receive",
        "address": address,
        "amount": amount_btc,
        "txid": txid,
        "confirmations": confirmations,
    }


@pytest.fixture
def store():
    return _make_store()


@pytest.fixture
def rpc():
    return _make_rpc()


@pytest.mark.asyncio
async def test_pending_to_detected(store, rpc):
    inv = store.create_payment("bc1qtest", 0, 50000, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qtest", 0.0005, confirmations=0)]
    )

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)])
    with patch.object(asyncio.get_event_loop(), "run_in_executor", side_effect=lambda _, f: asyncio.coroutine(lambda: f())()) if False else pytest.MonkeyPatch().context() as mp:
        pass

    await mon._poll_once("")

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.DETECTED
    assert updated.txid == "tx1"
    assert len(events) == 1
    assert events[0].is_first_detection is True
    assert events[0].is_first_confirmation is False


@pytest.mark.asyncio
async def test_detected_to_confirmed(store, rpc):
    inv = store.create_payment("bc1qtest2", 0, 50000, None, None)
    store.update_payment(inv.payment_id, status=PaymentStatus.DETECTED.value, txid="tx1", received_sat=50000, confirmations=0)

    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qtest2", 0.0005, txid="tx1", confirmations=1)]
    )

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)])
    await mon._poll_once("")

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.CONFIRMED
    assert updated.confirmations == 1
    assert len(events) == 1
    assert events[0].is_first_confirmation is True
    assert events[0].is_first_detection is False


@pytest.mark.asyncio
async def test_pending_to_confirmed_directly(store, rpc):
    inv = store.create_payment("bc1qdirect", 0, None, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qdirect", 0.001, txid="tx2", confirmations=3)]
    )

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)], required_confirmations=1)
    await mon._poll_once("")

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.CONFIRMED
    assert events[0].is_first_detection is True
    assert events[0].is_first_confirmation is True


@pytest.mark.asyncio
async def test_overpaid(store, rpc):
    inv = store.create_payment("bc1qover", 0, 50000, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qover", 0.001, txid="tx3", confirmations=1)]  # 100k sat vs 50k expected
    )

    mon = _make_monitor(store, rpc)
    await mon._poll_once("")

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.OVERPAID
    assert updated.received_sat == 100000


@pytest.mark.asyncio
async def test_confirmed_reorg_reverts_to_detected(store, rpc):
    inv = store.create_payment("bc1qreorg", 0, None, None, None)
    store.update_payment(inv.payment_id, status=PaymentStatus.CONFIRMED.value, txid="tx4", received_sat=50000, confirmations=3)

    rpc.listsinceblock.return_value = _make_listsinceblock(
        removed=[_receive_tx("bc1qreorg", 0.0005, txid="tx4", confirmations=3)],
        transactions=[],
    )

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)])
    await mon._poll_once("")

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.DETECTED
    assert updated.confirmations == 0
    assert len(events) == 1


@pytest.mark.asyncio
async def test_expired_invoice(store, rpc):
    from datetime import timedelta
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    inv = store.create_payment("bc1qexpired", 0, None, None, past)

    rpc.listsinceblock.return_value = _make_listsinceblock()

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)])
    await mon._poll_once("")
    await mon._check_expired()

    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.EXPIRED
    assert any(e.status == PaymentStatus.EXPIRED for e in events)


@pytest.mark.asyncio
async def test_callback_exception_does_not_stop_loop(store, rpc):
    inv = store.create_payment("bc1qerr", 0, None, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qerr", 0.001, confirmations=1)]
    )

    def bad_callback(event):
        raise RuntimeError("callback error")

    mon = _make_monitor(store, rpc, callbacks=[bad_callback])
    # Should not raise
    await mon._poll_once("")
    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.CONFIRMED


@pytest.mark.asyncio
async def test_async_callback(store, rpc):
    inv = store.create_payment("bc1qasync", 0, None, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qasync", 0.001, confirmations=1)]
    )

    events = []

    async def async_cb(event):
        events.append(event)

    mon = _make_monitor(store, rpc, callbacks=[async_cb])
    await mon._poll_once("")

    assert len(events) == 1
    assert events[0].is_first_confirmation is True


@pytest.mark.asyncio
async def test_unrelated_addresses_ignored(store, rpc):
    store.create_payment("bc1qwatched", 0, None, None, None)
    rpc.listsinceblock.return_value = _make_listsinceblock(
        transactions=[_receive_tx("bc1qother", 0.001, confirmations=1)]
    )

    events = []
    mon = _make_monitor(store, rpc, callbacks=[lambda e: events.append(e)])
    await mon._poll_once("")

    assert events == []
