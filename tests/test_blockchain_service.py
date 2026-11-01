import unittest
from pathlib import Path
from unittest.mock import patch

from blockchain_service import (
    ABI_PATH,
    BlockchainService,
    LOCAL_TEST_PRIVATE_KEY,
    LOCAL_RPC_URL,
    _configured_rpc_url,
    _resolve_signing_key,
)


class BlockchainSigningKeyTests(unittest.TestCase):
    def test_missing_rpc_uses_local_node_outside_render(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_configured_rpc_url(), LOCAL_RPC_URL)

    def test_missing_rpc_does_not_fall_back_to_localhost_on_render(self) -> None:
        with patch.dict("os.environ", {"RENDER": "true"}, clear=True):
            self.assertIsNone(_configured_rpc_url())

    def test_configured_rpc_is_used_on_render(self) -> None:
        rpc_url = "https://sepolia.example/rpc"
        with patch.dict(
            "os.environ",
            {"RENDER": "true", "BLOCKCHAIN_RPC_URL": rpc_url},
            clear=True,
        ):
            self.assertEqual(_configured_rpc_url(), rpc_url)

    def test_local_hardhat_key_is_only_available_on_loopback(self) -> None:
        self.assertEqual(
            _resolve_signing_key(31337, "http://127.0.0.1:8545"),
            LOCAL_TEST_PRIVATE_KEY,
        )
        with self.assertRaisesRegex(RuntimeError, "limited|limitée"):
            _resolve_signing_key(31337, "https://remote.example")

    def test_sepolia_requires_a_locally_configured_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BLOCKCHAIN_PRIVATE_KEY"):
                _resolve_signing_key(11155111, "https://sepolia.example")

    def test_sepolia_key_is_read_from_environment(self) -> None:
        with patch.dict("os.environ", {"BLOCKCHAIN_PRIVATE_KEY": "test-key"}):
            self.assertEqual(
                _resolve_signing_key(11155111, "https://sepolia.example"),
                "test-key",
            )

    def test_unapproved_network_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "31337"):
            _resolve_signing_key(1, "https://mainnet.example")

    def test_missing_contract_abi_uses_bundled_contract_abi(self) -> None:
        with (
            patch("blockchain_service.Web3") as web3,
            patch("blockchain_service.ABI_PATH", Path("missing-abi.json")),
        ):
            web3.return_value.is_connected.return_value = True
            web3.return_value.eth.chain_id = 31337
            web3.return_value.eth.get_code.return_value = b"\x60\x00"
            web3.return_value.eth.account.from_key.return_value.address = (
                "0x0000000000000000000000000000000000000001"
            )
            web3.return_value.eth.contract.return_value.functions.reporters.return_value.call.return_value = True

            service = BlockchainService()

        self.assertIsNotNone(service)
        contract_kwargs = web3.return_value.eth.contract.call_args.kwargs
        abi_names = {item["name"] for item in contract_kwargs["abi"]}
        self.assertTrue(
            {"reporters", "getAlertCount", "getAlert", "recordAlert", "AlertRecorded"}
            .issubset(abi_names)
        )


if __name__ == "__main__":
    unittest.main()
