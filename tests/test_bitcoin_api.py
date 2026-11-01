import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

import api
from analysis_history import initialize_history, list_analyses


class BitcoinApiTests(unittest.TestCase):
    def test_real_elliptic_sample_is_scored_explained_and_saved(self) -> None:
        sample = pd.read_csv(api.FEATURES_PATH, header=None, nrows=1)
        features = [float(value) for value in sample.iloc[0, 1:]]
        transaction_id = str(int(sample.iloc[0, 0]))

        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.sqlite3"
            initialize_history(history_path)
            with (
                patch.object(api, "HISTORY_DB_PATH", history_path),
                patch.object(api, "bitcoin_explainer", None),
                patch.object(api, "obtenir_blockchain", return_value=None),
            ):
                response = TestClient(api.app).post(
                    "/predict",
                    json={
                        "features": features,
                        "transaction_id": transaction_id,
                    },
                )

            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["classe_predite"], api.model.predict([features])[0])
            self.assertEqual(len(result["explications_shap"]), 8)
            self.assertTrue(
                all(
                    isinstance(item["feature"], str)
                    and isinstance(item["value"], float)
                    and isinstance(item["contribution"], float)
                    for item in result["explications_shap"]
                )
            )
            self.assertFalse(result["blockchain_enregistre"])

            history = list_analyses(history_path, limit=10, offset=0)
            self.assertEqual(history["total"], 1)
            self.assertEqual(
                history["analyses"][0]["transaction_id"],
                transaction_id,
            )
            self.assertEqual(history["analyses"][0]["type_analyse"], "bitcoin")

    def test_rejects_non_finite_features_and_oversized_transaction_id(self) -> None:
        features = [0.0] * 166
        features[0] = float("nan")
        client = TestClient(api.app, raise_server_exceptions=False)

        non_finite_body = (
            '{"features":['
            + ",".join("NaN" if value != value else str(value) for value in features)
            + "]}"
        )
        non_finite_response = client.post(
            "/predict",
            content=non_finite_body,
            headers={"content-type": "application/json"},
        )
        oversized_id_response = client.post(
            "/predict",
            json={
                "features": [0.0] * 166,
                "transaction_id": "x" * 129,
            },
        )

        self.assertEqual(non_finite_response.status_code, 422)
        self.assertEqual(oversized_id_response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
