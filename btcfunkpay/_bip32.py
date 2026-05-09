"""
Pure-stdlib BIP32/BIP84 address derivation.
Accepts xpub/zpub (mainnet) and tpub/vpub (testnet) at the account level
(m/84'/0'/0') and derives P2WPKH child addresses without external dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import struct

# secp256k1 parameters
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
_G = (_Gx, _Gy)

_XPUB_VERSION  = bytes.fromhex("0488B21E")  # mainnet xpub
_ZPUB_VERSION  = bytes.fromhex("04B24746")  # mainnet zpub
_TPUB_VERSION  = bytes.fromhex("043587CF")  # testnet tpub
_VPUB_VERSION  = bytes.fromhex("045F1CF6")  # testnet vpub

# bech32 charset
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _point_add(P, Q):
    if P is None:
        return Q
    if Q is None:
        return P
    if P[0] == Q[0]:
        if P[1] != Q[1]:
            return None
        lam = (3 * P[0] * P[0] * pow(2 * P[1], _P - 2, _P)) % _P
    else:
        lam = ((Q[1] - P[1]) * pow(Q[0] - P[0], _P - 2, _P)) % _P
    x = (lam * lam - P[0] - Q[0]) % _P
    y = (lam * (P[0] - x) - P[1]) % _P
    return (x, y)


def _point_mul(k, P):
    R = None
    for i in range(256):
        if (k >> i) & 1:
            R = _point_add(R, P)
        P = _point_add(P, P)
    return R


def _compress(x, y) -> bytes:
    return bytes([2 + (y & 1)]) + x.to_bytes(32, "big")


def _decompress(pub33: bytes):
    prefix = pub33[0]
    x = int.from_bytes(pub33[1:], "big")
    y_sq = (pow(x, 3, _P) + 7) % _P
    y = pow(y_sq, (_P + 1) // 4, _P)
    if (y & 1) != (prefix & 1):
        y = _P - y
    return x, y


def _b58decode_check(s: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        idx = alphabet.find(c)
        if idx < 0:
            raise ValueError(f"Invalid Base58 character: {c!r}")
        n = n * 58 + idx
    nbytes = (n.bit_length() + 7) // 8 or 1
    raw = n.to_bytes(nbytes, "big")
    # Leading '1' chars in base58 encode leading zero bytes
    pad = len(s) - len(s.lstrip("1"))
    raw = b"\x00" * pad + raw
    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        raise ValueError("Invalid checksum")
    return payload


def parse_xpub(xpub_str: str) -> tuple[bytes, bytes]:
    """Return (pubkey_33, chain_code_32) from an xpub or zpub string."""
    data = _b58decode_check(xpub_str)
    version = data[:4]
    if version not in (_XPUB_VERSION, _ZPUB_VERSION, _TPUB_VERSION, _VPUB_VERSION):
        raise ValueError(f"Unsupported xpub version: {version.hex()}")
    # depth=data[4], fingerprint=data[5:9], index=data[9:13]
    chain_code = data[13:45]
    pubkey = data[45:78]
    return pubkey, chain_code


def child_pubkey(parent_pub33: bytes, chain_code: bytes, index: int) -> tuple[bytes, bytes]:
    """Derive a non-hardened child public key (index < 2^31)."""
    if index >= 0x80000000:
        raise ValueError("Hardened derivation requires private key")
    data = parent_pub33 + struct.pack(">I", index)
    I = hmac.new(chain_code, data, hashlib.sha512).digest()
    IL, IR = I[:32], I[32:]
    il_int = int.from_bytes(IL, "big")
    if il_int >= _N:
        raise ValueError("Derived key invalid — increment index")
    px, py = _decompress(parent_pub33)
    child_point = _point_add(_point_mul(il_int, _G), (px, py))
    if child_point is None:
        raise ValueError("Derived key is point at infinity — increment index")
    return _compress(*child_point), IR


def _bech32_polymod(values) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data, frombits, tobits, pad=True) -> list:
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = ((acc << frombits) | value) & 0x3FFFFFFF
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return []
    return ret


def _bech32_encode(hrp: str, data: list) -> str:
    combined = data + [0, 0, 0, 0, 0, 0]
    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + combined) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join([_CHARSET[d] for d in data + checksum])


def p2wpkh_address(pubkey33: bytes, mainnet: bool = True) -> str:
    """Convert a 33-byte compressed pubkey to a bech32 P2WPKH address."""
    sha = hashlib.sha256(pubkey33).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    hrp = "bc" if mainnet else "tb"
    witness_program = _convertbits(ripe, 8, 5)
    return _bech32_encode(hrp, [0] + witness_program)


def derive_address(xpub_str: str, change: int, index: int, mainnet: bool = True) -> str:
    """Derive a BIP84 P2WPKH address at path .../change/index from an xpub/zpub."""
    pub, chain = parse_xpub(xpub_str)
    pub, chain = child_pubkey(pub, chain, change)
    pub, chain = child_pubkey(pub, chain, index)
    return p2wpkh_address(pub, mainnet)
