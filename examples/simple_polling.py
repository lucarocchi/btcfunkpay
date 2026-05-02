"""
Minimal example: create an invoice and wait for payment in a background thread.
Requires a Bitcoin Core node with RPC enabled.
"""

import signal
import time
from btcfunkpay import PaymentProcessor, PaymentEvent, PaymentStatus

XPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
RPC_URL = "http://btcrpc:password@127.0.0.1:8332"

proc = PaymentProcessor(
    xpub=XPUB,
    rpc_url=RPC_URL,
    required_confirmations=1,
    poll_interval=30,
)
proc.setup()


@proc.on_payment
def on_payment(event: PaymentEvent):
    if event.status == PaymentStatus.DETECTED and event.is_first_detection:
        print(f"[mempool] {event.received_sat} sats → {event.address} (txid: {event.txid})")
    elif event.status == PaymentStatus.CONFIRMED and event.is_first_confirmation:
        print(f"[confirmed] {event.received_sat} sats → {event.address} label={event.label}")
    elif event.status == PaymentStatus.EXPIRED:
        print(f"[expired] {event.address}")
    elif event.status == PaymentStatus.OVERPAID:
        print(f"[overpaid] received {event.received_sat} sat, expected {event.amount_sat}")


inv = proc.create_invoice(amount_sat=50_000, label="demo-order")
print(f"Invoice created:")
print(f"  Address : {inv.address}")
print(f"  BIP21   : {inv.bip21_uri}")
print(f"  Expires : {inv.expires_at}")
print()

proc.start()
print("Monitoring... press Ctrl+C to stop.")

signal.signal(signal.SIGINT, lambda *_: proc.stop())
proc.run_forever()
