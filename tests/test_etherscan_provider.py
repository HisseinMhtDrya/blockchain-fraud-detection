import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from etherscan_provider import EthereumProvider, EthereumProviderError


class EthereumProviderTests(unittest.TestCase):
    def provider(self) -> EthereumProvider:
        provider = EthereumProvider.__new__(EthereumProvider)
        provider.api_key = "test-key"
        provider.rpc_url = "https://rpc.example"
        provider._rpc_id = 0
        return provider

    def test_requires_api_key_and_rpc_url(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(EthereumProviderError, "ETHERSCAN_API_KEY"):
                EthereumProvider()

    def test_refuses_non_mainnet_rpc(self) -> None:
        provider = self.provider()
        provider._rpc_request = lambda payload: {"result": "0x7a69"}
        with self.assertRaisesRegex(EthereumProviderError, "received 31337"):
            provider._verify_mainnet()

    def test_http_error_identifies_provider_without_exposing_credentials(self) -> None:
        request = urllib.request.Request(
            "https://eth-mainnet.g.alchemy.com/v2/sensitive-test-key"
        )
        error = urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, None
        )
        with (
            patch("etherscan_provider.urllib.request.urlopen", side_effect=error),
            self.assertRaisesRegex(EthereumProviderError, "Configured Ethereum RPC returned HTTP 401") as caught,
        ):
            EthereumProvider._read_json(request)

        self.assertNotIn("sensitive-test-key", str(caught.exception))

    def test_etherscan_http_error_identifies_provider(self) -> None:
        request = urllib.request.Request(
            "https://api.etherscan.io/v2/api?apikey=sensitive-test-key"
        )
        error = urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, None
        )
        with (
            patch("etherscan_provider.urllib.request.urlopen", side_effect=error),
            self.assertRaisesRegex(EthereumProviderError, "Etherscan returned HTTP 401") as caught,
        ):
            EthereumProvider._read_json(request)

        self.assertNotIn("sensitive-test-key", str(caught.exception))

    def test_history_fetch_rejects_truncated_pages(self) -> None:
        provider = self.provider()
        provider._etherscan_page = lambda address, action, page: (
            [{"timeStamp": "1700000000"}] * 10_000
            if page == 1
            else [{"timeStamp": "1700000001"}]
        )
        with patch("etherscan_provider.MAX_PAGES_PER_ACTION", 1):
            with self.assertRaisesRegex(EthereumProviderError, "safety limit"):
                provider._all_transactions("0x" + "a" * 40, "txlist")

    def test_contract_type_batch_must_be_complete(self) -> None:
        provider = self.provider()
        provider._rpc_request = lambda payload: []
        with self.assertRaisesRegex(EthereumProviderError, "incomplete"):
            provider.contract_flags(["0x" + "a" * 40])

    def test_contract_type_reads_batched_code(self) -> None:
        provider = self.provider()

        def rpc_response(payload):
            return [
                {"id": item["id"], "result": "0x6000"}
                for item in reversed(payload)
            ]

        provider._rpc_request = rpc_response
        addresses = ["0x" + "a" * 40, "0x" + "b" * 40]
        self.assertEqual(
            provider.contract_flags(addresses),
            {address: True for address in addresses},
        )

    def test_contract_type_retries_rate_limited_batch_items(self) -> None:
        provider = self.provider()
        addresses = ["0x" + "a" * 40, "0x" + "b" * 40]
        calls = 0

        def rpc_response(payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                return [
                    {"id": payload[0]["id"], "result": "0x"},
                    {
                        "id": payload[1]["id"],
                        "error": {
                            "code": 429,
                            "message": "compute units per second capacity exceeded",
                        },
                    },
                ]
            return [{"id": payload[0]["id"], "result": "0x6000"}]

        provider._rpc_request = rpc_response
        with patch("etherscan_provider.time.sleep") as sleep:
            result = provider.contract_flags(addresses)

        self.assertEqual(result, {addresses[0]: False, addresses[1]: True})
        self.assertEqual(calls, 2)
        sleep.assert_called_once_with(1)

    def test_contract_type_fails_explicitly_after_rate_limit_retries(self) -> None:
        provider = self.provider()

        def rpc_response(payload):
            return [
                {
                    "id": item["id"],
                    "error": {"code": 429, "message": "rate limited"},
                }
                for item in payload
            ]

        provider._rpc_request = rpc_response
        with (
            patch("etherscan_provider.time.sleep"),
            patch("etherscan_provider.RPC_RATE_LIMIT_RETRIES", 1),
            self.assertRaisesRegex(EthereumProviderError, "rate-limiting"),
        ):
            provider.contract_flags(["0x" + "a" * 40])


if __name__ == "__main__":
    unittest.main()
