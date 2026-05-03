"""
standalone.py — terminal payment monitor

Run this script when a customer wants to pay. It:
  1. Asks for an amount and a label (e.g. customer email or order ID)
  2. Creates a Bitcoin invoice and prints the address + BIP21 link
  3. Waits in the background until payment arrives on-chain
  4. Prints a confirmation and exits

Usage:
  python3 examples/standalone.py

Requires btcfunkpay.conf in the current directory (or set BTCFUNKPAY_CONFIG).
"""

import signal
import sys

from btcfunkpay import PaymentProcessor, PaymentEvent, PaymentStatus, load_config

cfg = load_config()

# --- ask for order details ---
print("=== FunkPay — new invoice ===")
try:
    amount_input = input("Amount in satoshis (leave blank for open amount): ").strip()
    label = input("Label (customer email, order ID, ...): ").strip() or None
except (KeyboardInterrupt, EOFError):
    print("\nAborted.")
    sys.exit(0)

amount_sat = int(amount_input) if amount_input else None

# --- setup processor ---
proc = PaymentProcessor(
    xpub=cfg.xpub,
    rpc_url=cfg.rpc_url,
    db_path=cfg.db_path,
    required_confirmations=cfg.required_confirmations,
    poll_interval=cfg.poll_interval,
    expiry_seconds=cfg.expiry_seconds,
    mainnet=cfg.mainnet,
    wallet_name=cfg.wallet_name,
)
proc.setup()

@proc.on_payment
def on_payment(event: PaymentEvent):
    if event.status == PaymentStatus.DETECTED and event.is_first_detection:
        print(f"\n[mempool] Transaction detected — {event.received_sat} sat (txid: {event.txid})")
        print("Waiting for confirmation...")
    elif event.status == PaymentStatus.CONFIRMED and event.is_first_confirmation:
        print(f"\n[confirmed] Payment confirmed — {event.received_sat} sat  label={event.label}")
        proc.stop()
    elif event.status == PaymentStatus.OVERPAID:
        print(f"\n[confirmed] Payment confirmed (overpaid) — {event.received_sat} sat  label={event.label}")
        proc.stop()
    elif event.status == PaymentStatus.EXPIRED:
        print(f"\n[expired] Invoice expired without payment.")
        proc.stop()

# --- create invoice and print ---
inv = proc.create_invoice(amount_sat=amount_sat, label=label)

print()
print(f"  Address : {inv.address}")
print(f"  BIP21   : {inv.bip21_uri}")
if inv.expires_at:
    print(f"  Expires : {inv.expires_at.strftime('%H:%M:%S')}")
print()
print("Waiting for payment... (Ctrl+C to cancel)")

signal.signal(signal.SIGINT, lambda *_: (print("\nCancelled."), proc.stop()))
proc.start()
proc.run_forever()
