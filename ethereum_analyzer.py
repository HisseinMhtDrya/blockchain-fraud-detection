from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ethereum_features import ADDRESS_FEATURES


class EthereumAddressAnalyzer:
    def __init__(self, bundle_path: Path, background_path: Path) -> None:
        bundle = joblib.load(bundle_path)
        if bundle.get("feature_names") != list(ADDRESS_FEATURES):
            raise ValueError("Ethereum model feature schema is incompatible.")
        if float(bundle.get("threshold", -1)) != 0.5:
            raise ValueError("Ethereum model classification threshold is unsupported.")

        self.classifier = bundle["classifier"]
        self.preprocessor = bundle["preprocessor"]
        self.background = np.load(background_path, allow_pickle=False)
        if self.background.ndim != 2 or self.background.shape[1] != len(ADDRESS_FEATURES):
            raise ValueError("Ethereum SHAP background has an invalid shape.")

        import shap

        self.explainer = shap.TreeExplainer(
            self.classifier,
            data=self.background,
            feature_perturbation="interventional",
            model_output="probability",
        )

    def analyze(self, values: dict[str, float]) -> dict:
        features = pd.DataFrame(
            [[values[name] for name in ADDRESS_FEATURES]],
            columns=ADDRESS_FEATURES,
        )
        transformed = self.preprocessor.transform(features)
        probabilities = self.classifier.predict_proba(transformed)[0]
        shap_output = self.explainer(transformed, check_additivity=False)
        shap_values = np.asarray(shap_output.values)
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]
        contributions = shap_values[0]
        explanations = sorted(
            (
                {
                    "feature": feature,
                    "value": float(values[feature]),
                    "contribution": float(contribution),
                }
                for feature, contribution in zip(
                    ADDRESS_FEATURES,
                    contributions,
                    strict=True,
                )
            ),
            key=lambda item: abs(item["contribution"]),
            reverse=True,
        )
        predicted_class = int(probabilities[1] >= 0.5)
        return {
            "classe_predite": predicted_class,
            "probabilite_non_scam": float(probabilities[0]),
            "probabilite_scam": float(probabilities[1]),
            "score_risque_sur_100": round(float(probabilities[1]) * 100),
            "explications_shap": explanations[:8],
        }
