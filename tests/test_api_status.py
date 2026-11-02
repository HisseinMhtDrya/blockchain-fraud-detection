import unittest
from unittest.mock import Mock, patch

import api


class ApiStatusTests(unittest.TestCase):
    def test_reports_sepolia_by_chain_id_without_exposing_credentials(self) -> None:
        service = Mock()
        service.w3.eth.chain_id = 11155111
        service.contract.functions.getAlertCount.return_value.call.return_value = 2

        with (
            patch.object(api, "obtenir_blockchain", return_value=service),
            patch.object(api, "obtenir_analyseur_ethereum", return_value=None),
            patch.dict(
                "os.environ",
                {
                    "ETHERSCAN_API_KEY": "test-key-not-a-secret",
                    "ETHEREUM_RPC_URL": "https://rpc.example/test",
                },
            ),
        ):
            status = api.statut_services()

        self.assertEqual(status["reseau"], "Sepolia (chain ID 11155111)")
        self.assertEqual(status["chain_id"], 11155111)
        self.assertTrue(status["ethereum_provider_configured"])
        self.assertNotIn("ETHERSCAN_API_KEY", status)
        self.assertNotIn("ETHEREUM_RPC_URL", status)

    def test_reports_missing_ethereum_provider_configuration(self) -> None:
        with (
            patch.object(api, "obtenir_blockchain", return_value=None),
            patch.object(api, "obtenir_analyseur_ethereum", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            status = api.statut_services()

        self.assertIsNone(status["reseau"])
        self.assertFalse(status["ethereum_provider_configured"])

    def test_public_rpc_means_only_etherscan_key_is_required(self) -> None:
        with (
            patch.object(api, "obtenir_blockchain", return_value=None),
            patch.object(api, "obtenir_analyseur_ethereum", return_value=None),
            patch.dict(
                "os.environ",
                {"ETHERSCAN_API_KEY": "test-key"},
                clear=True,
            ),
        ):
            status = api.statut_services()

        self.assertTrue(status["ethereum_provider_configured"])


if __name__ == "__main__":
    unittest.main()
