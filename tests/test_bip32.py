"""
BIP84 test vectors from:
https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki#test-vectors

Mnemonic: abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about
"""

import pytest
from btcfunkpay._bip32 import derive_address, parse_xpub, p2wpkh_address, child_pubkey


# BIP84 test vector: account-level zpub
ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"

# Expected receiving addresses (change=0)
EXPECTED_ADDRESSES = [
    "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
    "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g",
    "bc1qp59yckz4ae5c4efgw2s5wfyvrz0ala7rgvuz8z",
]


def test_parse_zpub():
    pub, chain = parse_xpub(ZPUB)
    assert len(pub) == 33
    assert len(chain) == 32
    assert pub[0] in (2, 3), "should be compressed pubkey"


def test_derive_address_index_0():
    addr = derive_address(ZPUB, change=0, index=0)
    assert addr == EXPECTED_ADDRESSES[0]


def test_derive_address_index_1():
    addr = derive_address(ZPUB, change=0, index=1)
    assert addr == EXPECTED_ADDRESSES[1]


def test_derive_address_index_2():
    addr = derive_address(ZPUB, change=0, index=2)
    assert addr == EXPECTED_ADDRESSES[2]


def test_derive_change_address():
    # change=1 should produce a different address than change=0
    addr_receive = derive_address(ZPUB, change=0, index=0)
    addr_change = derive_address(ZPUB, change=1, index=0)
    assert addr_receive != addr_change
    assert addr_change.startswith("bc1q")


def test_invalid_xpub_checksum():
    bad = ZPUB[:-1] + ("x" if ZPUB[-1] != "x" else "y")
    with pytest.raises(ValueError, match="checksum|index"):
        parse_xpub(bad)


def test_hardened_derivation_rejected():
    pub, chain = parse_xpub(ZPUB)
    with pytest.raises(ValueError, match="Hardened"):
        child_pubkey(pub, chain, 0x80000000)


def test_testnet_address():
    # Change=0, index=0 on testnet should start with tb1q
    # (we don't have official testnet vectors here, just check prefix)
    addr = derive_address(ZPUB, change=0, index=0, mainnet=False)
    assert addr.startswith("tb1q")
