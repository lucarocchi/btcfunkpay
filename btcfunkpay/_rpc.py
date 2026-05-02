from __future__ import annotations

from typing import Any

import requests


class RPCError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"RPC error {code}: {message}")
        self.code = code
        self.message = message


class BitcoinRPC:
    def __init__(self, url: str, timeout: int = 30):
        self._url = url
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def call(self, method: str, *params) -> Any:
        payload = {
            "jsonrpc": "1.0",
            "id": method,
            "method": method,
            "params": list(params),
        }
        r = self._session.post(self._url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        resp = r.json()
        if resp.get("error"):
            e = resp["error"]
            raise RPCError(e["code"], e["message"])
        return resp["result"]

    def getblockcount(self) -> int:
        return self.call("getblockcount")

    def getblockhash(self, height: int) -> str:
        return self.call("getblockhash", height)

    def getbestblockhash(self) -> str:
        return self.call("getbestblockhash")

    def listsinceblock(self, blockhash: str = "", minconf: int = 0) -> dict:
        return self.call("listsinceblock", blockhash, minconf, True, True)

    def gettransaction(self, txid: str) -> dict:
        return self.call("gettransaction", txid, True)

    def createwallet(
        self,
        name: str,
        disable_private_keys: bool = True,
        blank: bool = True,
    ) -> dict:
        return self.call("createwallet", name, disable_private_keys, blank)

    def importdescriptors(self, descriptors: list) -> list:
        return self.call("importdescriptors", descriptors)

    def loadwallet(self, name: str) -> dict:
        return self.call("loadwallet", name)
