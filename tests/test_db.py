from datetime import datetime, timedelta, timezone

import pytest
from btcfunkpay._db import PaymentStore
from btcfunkpay._models import PaymentStatus


@pytest.fixture
def store():
    return PaymentStore(":memory:")


def test_get_next_index_increments(store):
    assert store.get_next_index("xpub1") == 0
    assert store.get_next_index("xpub1") == 1
    assert store.get_next_index("xpub1") == 2


def test_get_next_index_independent_per_xpub(store):
    assert store.get_next_index("xpubA") == 0
    assert store.get_next_index("xpubB") == 0
    assert store.get_next_index("xpubA") == 1


def test_create_and_get_payment(store):
    inv = store.create_payment("bc1qtest", 0, 50000, "order-1", None)
    assert inv.payment_id is not None
    assert inv.address == "bc1qtest"
    assert inv.amount_sat == 50000
    assert inv.label == "order-1"
    assert inv.status == PaymentStatus.PENDING
    assert inv.received_sat == 0
    assert inv.confirmations == 0
    assert inv.txid is None

    fetched = store.get_payment(inv.payment_id)
    assert fetched.payment_id == inv.payment_id
    assert fetched.address == "bc1qtest"


def test_create_payment_no_amount(store):
    inv = store.create_payment("bc1qtest2", 1, None, None, None)
    assert inv.amount_sat is None
    assert inv.label is None


def test_update_payment(store):
    inv = store.create_payment("bc1qtest3", 0, 10000, None, None)
    store.update_payment(inv.payment_id, status=PaymentStatus.DETECTED.value, txid="abc123", received_sat=10000, confirmations=0)
    updated = store.get_payment(inv.payment_id)
    assert updated.status == PaymentStatus.DETECTED
    assert updated.txid == "abc123"
    assert updated.received_sat == 10000


def test_list_pending_includes_detected(store):
    inv1 = store.create_payment("bc1qa", 0, None, None, None)
    inv2 = store.create_payment("bc1qb", 1, None, None, None)
    store.update_payment(inv2.payment_id, status=PaymentStatus.DETECTED.value)

    pending = store.list_pending()
    ids = [p.payment_id for p in pending]
    assert inv1.payment_id in ids
    assert inv2.payment_id in ids


def test_list_pending_excludes_confirmed(store):
    inv = store.create_payment("bc1qc", 0, None, None, None)
    store.update_payment(inv.payment_id, status=PaymentStatus.CONFIRMED.value)
    assert store.list_pending() == []


def test_list_expired(store):
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    inv = store.create_payment("bc1qd", 0, None, None, past)
    expired = store.list_expired()
    assert any(e.payment_id == inv.payment_id for e in expired)


def test_list_expired_excludes_future(store):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    store.create_payment("bc1qe", 0, None, None, future)
    assert store.list_expired() == []


def test_get_watched_addresses(store):
    inv1 = store.create_payment("bc1qf", 0, None, None, None)
    inv2 = store.create_payment("bc1qg", 1, None, None, None)
    store.update_payment(inv2.payment_id, status=PaymentStatus.CONFIRMED.value)
    watched = store.get_watched_addresses()
    assert "bc1qf" in watched
    assert "bc1qg" not in watched


def test_monitor_state(store):
    assert store.get_monitor_state("last_block_hash") is None
    store.set_monitor_state("last_block_hash", "000000abc")
    assert store.get_monitor_state("last_block_hash") == "000000abc"
    store.set_monitor_state("last_block_hash", "000000def")
    assert store.get_monitor_state("last_block_hash") == "000000def"
