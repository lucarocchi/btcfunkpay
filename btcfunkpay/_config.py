from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional


_DEFAULTS = {
    "bitcoin": {
        "xpub": "",
        "rpc_url": "",
        "wallet_name": "btcfunkpay",
        "mainnet": "true",
    },
    "payments": {
        "required_confirmations": "1",
        "poll_interval": "30",
        "expiry_seconds": "3600",
        "min_sat": "1000",
    },
    "server": {
        "db_path": "btcfunkpay.sqlite",
        "host": "127.0.0.1",
        "port": "8001",
        "public_url": "",   # e.g. https://btcfunk.com/pay — used in well-known discovery
        "name": "",         # display name, e.g. "btcfunk.com"
        "catalog_url": "",  # e.g. http://127.0.0.1:8003 — merchant catalog service
    },
    "notifications": {
        "webhook_url": "",
    },
    "cors": {
        "allowed_origins": "*",
    },
    "admin": {
        "username": "admin",
        "password": "",
    },
}

_ENV_MAP = {
    # env var name -> (section, key)
    "BTCFUNKPAY_XPUB":                    ("bitcoin",  "xpub"),
    "BTCFUNKPAY_RPC_URL":                 ("bitcoin",  "rpc_url"),
    "BTCFUNKPAY_WALLET_NAME":             ("bitcoin",  "wallet_name"),
    "BTCFUNKPAY_MAINNET":                 ("bitcoin",  "mainnet"),
    "BTCFUNKPAY_REQUIRED_CONFIRMATIONS":  ("payments", "required_confirmations"),
    "BTCFUNKPAY_POLL_INTERVAL":           ("payments", "poll_interval"),
    "BTCFUNKPAY_EXPIRY_SECONDS":          ("payments", "expiry_seconds"),
    "BTCFUNKPAY_MIN_SAT":                 ("payments", "min_sat"),
    "BTCFUNKPAY_DB_PATH":                 ("server",   "db_path"),
    "BTCFUNKPAY_HOST":                    ("server",   "host"),
    "BTCFUNKPAY_PORT":                    ("server",   "port"),
    "BTCFUNKPAY_PUBLIC_URL":              ("server",   "public_url"),
    "BTCFUNKPAY_NAME":                    ("server",   "name"),
    "BTCFUNKPAY_CATALOG_URL":             ("server",        "catalog_url"),
    "BTCFUNKPAY_WEBHOOK_URL":             ("notifications", "webhook_url"),
    "BTCFUNKPAY_ALLOWED_ORIGINS":         ("cors",          "allowed_origins"),
    "BTCFUNKPAY_ADMIN_USERNAME":          ("admin",         "username"),
    "BTCFUNKPAY_ADMIN_PASSWORD":          ("admin",         "password"),
}


class Config:
    def __init__(self, path: Optional[str | Path] = None):
        self._cp = configparser.ConfigParser()
        # load defaults
        for section, values in _DEFAULTS.items():
            self._cp[section] = values

        # load config file
        if path is None:
            path = os.environ.get("BTCFUNKPAY_CONFIG", "btcfunkpay.conf")
        resolved = Path(path).expanduser()
        if resolved.exists():
            self._cp.read(resolved)

        # env vars override file
        for env_key, (section, key) in _ENV_MAP.items():
            val = os.environ.get(env_key)
            if val is not None:
                self._cp[section][key] = val

    # bitcoin
    @property
    def xpub(self) -> str:
        return self._cp["bitcoin"]["xpub"]

    @property
    def rpc_url(self) -> str:
        return self._cp["bitcoin"]["rpc_url"]

    @property
    def wallet_name(self) -> str:
        return self._cp["bitcoin"]["wallet_name"]

    @property
    def mainnet(self) -> bool:
        return self._cp["bitcoin"].getboolean("mainnet")

    # payments
    @property
    def required_confirmations(self) -> int:
        return self._cp["payments"].getint("required_confirmations")

    @property
    def poll_interval(self) -> int:
        return self._cp["payments"].getint("poll_interval")

    @property
    def expiry_seconds(self) -> Optional[int]:
        v = self._cp["payments"].getint("expiry_seconds")
        return v if v > 0 else None

    @property
    def min_sat(self) -> int:
        return self._cp["payments"].getint("min_sat")

    # server
    @property
    def db_path(self) -> str:
        return self._cp["server"]["db_path"]

    @property
    def host(self) -> str:
        return self._cp["server"]["host"]

    @property
    def port(self) -> int:
        return self._cp["server"].getint("port")

    @property
    def public_url(self) -> str:
        return self._cp.get("server", "public_url", fallback="")

    @property
    def name(self) -> str:
        return self._cp.get("server", "name", fallback="")

    @property
    def catalog_url(self) -> str:
        return self._cp.get("server", "catalog_url", fallback="")

    # notifications
    @property
    def webhook_url(self) -> str:
        return self._cp.get("notifications", "webhook_url", fallback="")

    # cors
    @property
    def allowed_origins(self) -> str:
        return self._cp.get("cors", "allowed_origins", fallback="*")

    # admin
    @property
    def admin_username(self) -> str:
        return self._cp.get("admin", "username", fallback="admin")

    @property
    def admin_password(self) -> str:
        return self._cp.get("admin", "password", fallback="")

    def validate(self) -> None:
        if not self.xpub:
            raise ValueError("btcfunkpay: xpub not set (config file or BTCFUNKPAY_XPUB)")
        if not self.rpc_url:
            raise ValueError("btcfunkpay: rpc_url not set (config file or BTCFUNKPAY_RPC_URL)")


def load(path: Optional[str | Path] = None) -> Config:
    cfg = Config(path)
    cfg.validate()
    return cfg
