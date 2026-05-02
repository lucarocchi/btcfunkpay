import pytest
from unittest.mock import MagicMock, patch
from btcfunkpay._rpc import BitcoinRPC, RPCError


def _mock_response(result=None, error=None):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"result": result, "error": error}
    return mock


@pytest.fixture
def rpc():
    return BitcoinRPC("http://user:pass@127.0.0.1:18443/wallet/test")


def test_call_success(rpc):
    with patch.object(rpc._session, "post", return_value=_mock_response(result=42)) as mock_post:
        result = rpc.call("getblockcount")
        assert result == 42
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "getblockcount"
        assert payload["params"] == []


def test_call_with_params(rpc):
    with patch.object(rpc._session, "post", return_value=_mock_response(result="hash123")):
        result = rpc.call("getblockhash", 100)
        assert result == "hash123"


def test_call_rpc_error(rpc):
    error_resp = {"code": -5, "message": "Block not found"}
    with patch.object(rpc._session, "post", return_value=_mock_response(error=error_resp)):
        with pytest.raises(RPCError) as exc_info:
            rpc.call("getblockhash", 9999)
        assert exc_info.value.code == -5
        assert "Block not found" in str(exc_info.value)


def test_getblockcount(rpc):
    with patch.object(rpc._session, "post", return_value=_mock_response(result=800000)):
        assert rpc.getblockcount() == 800000


def test_listsinceblock(rpc):
    fake_result = {"transactions": [], "removed": [], "lastblock": "abc123"}
    with patch.object(rpc._session, "post", return_value=_mock_response(result=fake_result)):
        result = rpc.listsinceblock("", 0)
        assert result["lastblock"] == "abc123"


def test_rpc_error_str():
    e = RPCError(-28, "Warmup")
    assert "-28" in str(e)
    assert "Warmup" in str(e)
    assert e.code == -28
    assert e.message == "Warmup"
