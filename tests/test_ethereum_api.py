import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import api
from api import EthereumAddressRequest, analyser_adresse_ethereum
from analysis_history import initialize_history, list_analyses
from ethereum_features import ADDRESS_FEATURES


class FakeEthereumAnalyzer:
    def analyze(self, values: dict[str, float]) -> dict:
        return {
            "classe_predite": 1,
            "probabilite_non_scam": 0.1,
            "probabilite_scam": 0.9,
            "score_risque_sur_100": 90,
            "explications_shap": [
                {
                    "feature": "normal_total_cnt",
                    "value": values["normal_total_cnt"],
                    "contribution": 0.4,
                }
            ],
        }


class FakeEthereumProvider:
    def get_address_history(self, address: str):
        return ([{"from": address}], [], [])

    def contract_flags(self, addresses: list[str]):
        return {address: False for address in addresses}


class FakeBlockchainService:
    def __init__(self) -> None:
        self.recorded: list[tuple[str, int, bool]] = []

    def enregistrer_alerte(
        self,
        address: str,
        risk_score: int,
        scam: bool,
    ) -> str:
        self.recorded.append((address, risk_score, scam))
        return "0x" + "1" * 64


class FakeLocalBlockchainService:
    class FakeWeb3:
        class FakeEth:
            chain_id = 31337

        eth = FakeEth()

    w3 = FakeWeb3()


class EthereumApiTests(unittest.TestCase):
    def test_returns_shap_and_records_scam_alert(self) -> None:
        address = "0x" + "a" * 40
        blockchain = FakeBlockchainService()
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.sqlite3"
            initialize_history(history_path)
            with (
                patch.object(api, "HISTORY_DB_PATH", history_path),
                patch.object(api, "ethereum_analyzer", FakeEthereumAnalyzer()),
                patch.object(api, "ethereum_analyzer_error", None),
                patch.object(api, "ethereum_provider", FakeEthereumProvider()),
                patch.object(api, "ethereum_provider_error", None),
                patch.object(api, "obtenir_blockchain", return_value=blockchain),
                patch.object(
                    api,
                    "extract_live_features",
                    return_value={
                        **{name: 0.0 for name in ADDRESS_FEATURES},
                        "normal_total_cnt": 1.0,
                    },
                ),
            ):
                response = analyser_adresse_ethereum(
                    EthereumAddressRequest(
                        address=address,
                        autoriser_enregistrement_alerte=True,
                    )
                )

            self.assertEqual(response["adresse"], address)
            self.assertEqual(response["score_risque_sur_100"], 90)
            self.assertEqual(
                response["source_features"]["reseau"],
                "Ethereum mainnet (chain ID 1)",
            )
            self.assertEqual(response["explications_shap"][0]["feature"], "normal_total_cnt")
            self.assertTrue(response["blockchain_enregistre"])
            self.assertEqual(blockchain.recorded, [(address, 90, True)])
            history = list_analyses(
                history_path,
                limit=10,
                offset=0,
            )
            self.assertEqual(history["total"], 1)
            self.assertEqual(history["analyses"][0]["transaction_id"], address)

    def test_positive_prediction_does_not_send_without_explicit_authorization(self) -> None:
        address = "0x" + "e" * 40
        blockchain = FakeBlockchainService()
        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.sqlite3"
            initialize_history(history_path)
            with (
                patch.object(api, "HISTORY_DB_PATH", history_path),
                patch.object(api, "ethereum_analyzer", FakeEthereumAnalyzer()),
                patch.object(api, "ethereum_provider", FakeEthereumProvider()),
                patch.object(api, "obtenir_blockchain", return_value=blockchain),
                patch.object(
                    api,
                    "extract_live_features",
                    return_value={
                        **{name: 0.0 for name in ADDRESS_FEATURES},
                        "normal_total_cnt": 1.0,
                    },
                ),
            ):
                response = analyser_adresse_ethereum(
                    EthereumAddressRequest(address=address)
                )

        self.assertFalse(response["blockchain_enregistre"])
        self.assertEqual(
            response["alerte_non_enregistree_raison"],
            "autorisation_absente",
        )
        self.assertEqual(blockchain.recorded, [])

    def test_missing_model_and_provider_return_service_unavailable(self) -> None:
        request = EthereumAddressRequest(address="0x" + "b" * 40)
        with patch.object(api, "obtenir_analyseur_ethereum", return_value=None):
            with self.assertRaises(HTTPException) as model_error:
                analyser_adresse_ethereum(request)
        self.assertEqual(model_error.exception.status_code, 503)

        with (
            patch.object(api, "obtenir_analyseur_ethereum", return_value=FakeEthereumAnalyzer()),
            patch.object(api, "obtenir_fournisseur_ethereum", return_value=None),
        ):
            with self.assertRaises(HTTPException) as provider_error:
                analyser_adresse_ethereum(request)
        self.assertEqual(provider_error.exception.status_code, 503)

    def test_featureless_address_is_not_scored(self) -> None:
        address = "0x" + "c" * 40
        with (
            patch.object(api, "ethereum_analyzer", FakeEthereumAnalyzer()),
            patch.object(api, "ethereum_provider", FakeEthereumProvider()),
            patch.object(
                api,
                "extract_live_features",
                return_value={name: 0.0 for name in ADDRESS_FEATURES},
            ),
        ):
            with self.assertRaises(HTTPException) as error:
                analyser_adresse_ethereum(EthereumAddressRequest(address=address))
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("Aucune activité", error.exception.detail)

    def test_local_demo_uses_model_without_provider_or_side_effects(self) -> None:
        with (
            patch.object(api, "obtenir_blockchain", return_value=FakeLocalBlockchainService()),
            patch.object(api, "obtenir_analyseur_ethereum", return_value=FakeEthereumAnalyzer()),
            patch.object(
                api,
                "obtenir_fournisseur_ethereum",
                side_effect=AssertionError("Demo must not call an external provider"),
            ),
            patch.object(
                api,
                "save_analysis",
                side_effect=AssertionError("Demo must not be persisted"),
            ),
        ):
            response = api.analyser_exemple_ethereum()

        self.assertEqual(response["mode"], "simulation_locale")
        self.assertEqual(response["source_features"]["transactions_normales"], 5)
        self.assertEqual(response["source_features"]["transferts_erc20"], 2)
        self.assertEqual(response["score_risque_sur_100"], 90)
        self.assertFalse(response["blockchain_enregistre"])
        self.assertIsNone(response["hash_transaction_blockchain"])
        self.assertIsNone(response["id_analyse"])

    def test_local_demo_refuses_non_local_chain(self) -> None:
        class MainnetService:
            class FakeWeb3:
                class FakeEth:
                    chain_id = 1

                eth = FakeEth()

            w3 = FakeWeb3()

        with patch.object(api, "obtenir_blockchain", return_value=MainnetService()):
            with self.assertRaises(HTTPException) as error:
                api.analyser_exemple_ethereum()

        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
