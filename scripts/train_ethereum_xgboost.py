from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as parquet
import shap
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import FunctionTransformer
from xgboost import XGBClassifier

from ethereum_features import (
    ADDRESS_FEATURES,
    aggregate_monthly_frame,
    build_split_features,
    signed_log1p,
)
from scripts.prepare_ethereum_dataset import (
    DATASET_REVISION,
    EXPECTED_SHA256,
    prepare_dataset,
)


DATASET_ROOT = (
    "https://huggingface.co/datasets/"
    "fesevu/ethereum_fraud_dataset_by_activity/resolve/"
    f"{DATASET_REVISION}/"
)
ARTIFACTS = {
    "addr_labels_balanced.csv.zst": (
        "addr_labels_balanced.csv.zst",
        EXPECTED_SHA256,
    ),
    "monthly.parquet": (
        "lstm_dataset/monthly.parquet",
        "c16d21902080684db4afee5f7585fa795b951ef0a97be774b794d7bde5cc7eb4",
    ),
    "address_id_map_labels.parquet": (
        "gnn_dataset/mapping/address_id_map_labels.parquet",
        "32dae60d32c4c5e1d76689a6a69992b7e3d5c9d171e626b135e54bda77a6d45e",
    ),
}
MAX_ESTIMATORS = 3_000
EARLY_STOPPING_ROUNDS = 40


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified_artifact(
    destination: Path,
    relative_url: str,
    expected_sha256: str,
) -> None:
    if destination.exists():
        actual = _sha256(destination)
        if actual != expected_sha256:
            raise ValueError(
                f"SHA-256 mismatch for existing artifact {destination}: {actual}"
            )
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_path = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        DATASET_ROOT + relative_url,
        headers={"User-Agent": "blockchain-fraud-detection/ethereum-phase3"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                with partial_path.open("wb") as target:
                    while chunk := response.read(1024 * 1024):
                        target.write(chunk)
            last_error = None
            break
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            last_error = error
            partial_path.unlink(missing_ok=True)
    if last_error is not None:
        raise RuntimeError(
            f"Could not download dataset artifact {relative_url} after 3 attempts: "
            f"{last_error}"
        ) from last_error

    actual = _sha256(partial_path)
    if actual != expected_sha256:
        partial_path.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch for {relative_url}: expected "
            f"{expected_sha256}, got {actual}"
        )
    partial_path.replace(destination)


def ensure_artifacts(data_dir: Path, splits_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for filename, (relative_url, checksum) in ARTIFACTS.items():
        path = data_dir / filename
        download_verified_artifact(path, relative_url, checksum)
        paths[filename] = path

    split_names = ("train.csv", "validation.csv", "test.csv", "manifest.json")
    existing = [splits_dir / name for name in split_names if (splits_dir / name).exists()]
    if len(existing) != len(split_names):
        if existing:
            raise FileExistsError(
                "Prepared split directory is incomplete; refusing to overwrite: "
                + ", ".join(str(path) for path in existing)
            )
        prepare_dataset(
            paths["addr_labels_balanced.csv.zst"],
            splits_dir,
            seed=42,
            expected_sha256=EXPECTED_SHA256,
        )
    return paths


def _metric_set(
    labels: pd.Series,
    probabilities: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict:
    expected = labels.to_numpy(dtype=np.int8)
    predicted = (probabilities >= threshold).astype(np.int8)
    return {
        "threshold": threshold,
        "accuracy": float(accuracy_score(expected, predicted)),
        "precision_positive": float(
            precision_score(expected, predicted, pos_label=1, zero_division=0)
        ),
        "recall_positive": float(
            recall_score(expected, predicted, pos_label=1, zero_division=0)
        ),
        "f1_positive": float(
            f1_score(expected, predicted, pos_label=1, zero_division=0)
        ),
        "roc_auc": float(roc_auc_score(expected, probabilities)),
        "average_precision": float(average_precision_score(expected, probabilities)),
        "confusion_matrix_labels_0_1": confusion_matrix(
            expected, predicted, labels=[0, 1]
        ).tolist(),
        "classification_report": classification_report(
            expected,
            predicted,
            labels=[0, 1],
            target_names=["selected_non_scam", "labeled_scam"],
            output_dict=True,
            zero_division=0,
        ),
    }


def train(
    *,
    data_dir: Path,
    splits_dir: Path,
    model_dir: Path,
    reports_dir: Path,
    seed: int = 42,
) -> dict:
    artifacts = ensure_artifacts(data_dir, splits_dir)
    monthly_path = artifacts["monthly.parquet"]
    address_map_path = artifacts["address_id_map_labels.parquet"]
    monthly_metadata = parquet.ParquetFile(monthly_path).metadata
    monthly = pd.read_parquet(monthly_path)
    monthly_aggregates = aggregate_monthly_frame(monthly)
    address_map = pd.read_parquet(address_map_path, columns=["address", "node_id"])

    feature_frames: dict[str, pd.DataFrame] = {}
    labels: dict[str, pd.Series] = {}
    coverage: dict[str, dict[str, int]] = {}
    active_masks: dict[str, pd.Series] = {}
    for split_name in ("train", "validation", "test"):
        split_path = splits_dir / f"{split_name}.csv"
        split = pd.read_csv(split_path, dtype={"address": "string"})
        features, target = build_split_features(split, address_map, monthly_aggregates)
        feature_frames[split_name] = features
        labels[split_name] = target
        active_mask = features.drop(columns=["is_contract"]).ne(0).any(axis=1)
        active_masks[split_name] = active_mask
        coverage[split_name] = {
            "addresses": len(features),
            "with_published_activity_features": int(active_mask.sum()),
            "without_published_activity_features": int((~active_mask).sum()),
            "without_features_by_class": {
                str(class_label): int(
                    (~active_mask)[labels[split_name] == class_label].sum()
                )
                for class_label in (0, 1)
            },
            "with_features_by_class": {
                str(class_label): int(
                    active_mask[labels[split_name] == class_label].sum()
                )
                for class_label in (0, 1)
            },
        }

    preprocessor = FunctionTransformer(
        signed_log1p,
        validate=False,
        feature_names_out="one-to-one",
    )
    transformed = {
        split_name: preprocessor.fit_transform(frame)
        if split_name == "train"
        else preprocessor.transform(frame)
        for split_name, frame in feature_frames.items()
    }

    classifier = XGBClassifier(
        objective="binary:logistic",
        eval_metric="auc",
        n_estimators=MAX_ESTIMATORS,
        max_depth=5,
        learning_rate=0.05,
        min_child_weight=5,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        tree_method="hist",
        n_jobs=min(8, os.cpu_count() or 1),
        random_state=seed,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
    )
    classifier.fit(
        transformed["train"][active_masks["train"].to_numpy()],
        labels["train"][active_masks["train"]].to_numpy(dtype=np.int8),
        eval_set=[
            (
                transformed["validation"][active_masks["validation"].to_numpy()],
                labels["validation"][active_masks["validation"]].to_numpy(dtype=np.int8),
            )
        ],
        verbose=False,
    )

    selected_iteration = int(classifier.best_iteration)
    early_stopping_reached = (
        selected_iteration + EARLY_STOPPING_ROUNDS < MAX_ESTIMATORS
    )
    classifier.set_params(
        n_estimators=selected_iteration + 1,
        early_stopping_rounds=None,
    )
    classifier.fit(
        transformed["train"][active_masks["train"].to_numpy()],
        labels["train"][active_masks["train"]].to_numpy(dtype=np.int8),
        verbose=False,
    )

    metrics = {
        split_name: _metric_set(
            labels[split_name][active_masks[split_name]],
            classifier.predict_proba(
                transformed[split_name][active_masks[split_name].to_numpy()]
            )[:, 1],
        )
        for split_name in ("train", "validation", "test")
    }
    train_active = transformed["train"][active_masks["train"].to_numpy()]
    test_active = transformed["test"][active_masks["test"].to_numpy()]
    background_size = min(100, len(train_active))
    background = train_active[
        np.random.default_rng(seed)
        .choice(len(train_active), size=background_size, replace=False)
    ]
    explainer = shap.TreeExplainer(
        classifier,
        data=background,
        feature_perturbation="interventional",
        model_output="probability",
    )
    test_size = min(1000, len(test_active))
    test_indices = np.random.default_rng(seed).choice(
        len(test_active),
        size=test_size,
        replace=False,
    )
    shap_output = explainer(test_active[test_indices], check_additivity=False)
    shap_values = np.asarray(shap_output.values)
    if shap_values.ndim == 3:
        shap_values = shap_values[:, :, 1]
    mean_absolute_shap = np.abs(shap_values).mean(axis=0)
    shap_importance = [
        {"feature": feature, "mean_abs_shap": float(value)}
        for feature, value in sorted(
            zip(ADDRESS_FEATURES, mean_absolute_shap, strict=True),
            key=lambda row: row[1],
            reverse=True,
        )
    ]

    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "classifier": classifier,
            "preprocessor": preprocessor,
            "feature_names": list(ADDRESS_FEATURES),
            "threshold": 0.5,
        },
        model_dir / "model_bundle.joblib",
    )
    classifier.save_model(model_dir / "xgboost_model.json")
    np.save(model_dir / "shap_background.npy", background)
    pd.DataFrame(shap_importance).to_csv(
        reports_dir / "ethereum_shap_global_importance.csv",
        index=False,
    )
    (reports_dir / "ethereum_model_metrics.json").write_text(
        json.dumps(
            {
                "dataset": {
                    "revision": DATASET_REVISION,
                    "monthly_rows": monthly_metadata.num_rows,
                    "monthly_addresses_with_features": len(monthly_aggregates),
                    "feature_window_start": str(monthly["month"].min()),
                    "feature_window_end": str(monthly["month"].max()),
                    "labeled_addresses": sum(item["addresses"] for item in coverage.values()),
                    "evaluated_active_addresses": {
                        split_name: int(active_masks[split_name].sum())
                        for split_name in ("train", "validation", "test")
                    },
                    "coverage_by_split": coverage,
                    "features": list(ADDRESS_FEATURES),
                },
                "training": {
                    "random_seed": seed,
                    "model_parameters": {
                        "objective": "binary:logistic",
                        "n_estimators": selected_iteration + 1,
                        "max_depth": 5,
                        "learning_rate": 0.05,
                        "min_child_weight": 5,
                        "subsample": 0.85,
                        "colsample_bytree": 0.85,
                        "reg_lambda": 2.0,
                        "tree_method": "hist",
                    },
                    "best_iteration": selected_iteration,
                    "early_stopping_reached": early_stopping_reached,
                    "threshold": 0.5,
                    "metrics": metrics,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# Modèle XGBoost Ethereum — résultats mesurés",
        "",
        f"- Révision du corpus : `{DATASET_REVISION}`",
        f"- Lignes mensuelles agrégées : {monthly_metadata.num_rows:,}",
        f"- Période couverte par les features : {monthly['month'].min()} à {monthly['month'].max()}",
        f"- Adresses ayant des caractéristiques publiées : {len(monthly_aggregates):,}",
        (
            f"- Itération retenue par arrêt anticipé sur validation : {selected_iteration}"
            if early_stopping_reached
            else f"- Entraînement arrêté à la limite de {MAX_ESTIMATORS:,} arbres ; l'arrêt anticipé n'a pas été atteint (itération {selected_iteration})."
        ),
        "- Seuil de classification : 0,5 (fixé avant évaluation)",
        "- Entraînement et métriques principales portent uniquement sur les adresses ayant au moins une caractéristique d'activité non nulle ; l'API refuse de scorer une adresse sans activité observée.",
        "- La classe positive signifie « étiquetée scam dans ce corpus », pas blanchiment prouvé.",
        "- Les lignes sans caractéristiques mensuelles sont encodées comme zéros ; leur couverture diffère selon la classe et figure dans le JSON détaillé.",
        "- La séparation aléatoire par adresse n'est pas une évaluation prospective : les dates de connaissance des labels sont absentes.",
        "- Les caractéristiques d'entraînement s'arrêtent à la dernière fenêtre mensuelle publiée ; l'inférence sur l'historique actuel peut subir une dérive temporelle.",
        "- Pour l'inférence Etherscan, les champs « type de contrepartie » et `is_contract` sont calculés depuis l'état RPC actuel, tandis que le corpus utilise des labels/contracts historiques ; cette différence doit être considérée dans l'interprétation.",
        "",
        "## Métriques par partition",
        "",
        "| Partition | Accuracy | Précision (scam) | Rappel (scam) | F1 (scam) | ROC-AUC | PR-AUC | Confusion [[TN, FP], [FN, TP]] |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for split_name, result in metrics.items():
        report_lines.append(
            f"| {split_name} | {result['accuracy']:.4f} | "
            f"{result['precision_positive']:.4f} | {result['recall_positive']:.4f} | "
            f"{result['f1_positive']:.4f} | {result['roc_auc']:.4f} | "
            f"{result['average_precision']:.4f} | "
            f"`{result['confusion_matrix_labels_0_1']}` |"
        )
    report_lines.extend(
        [
            "",
            "Les précisions, rappels et F1 par classe, ainsi que les matrices détaillées, sont dans `ethereum_model_metrics.json`.",
            "",
            "## Couverture des caractéristiques",
            "",
            "| Partition | Total | Avec activité | Sans activité publiée |",
            "|---|---:|---:|---:|",
        ]
    )
    for split_name, counts in coverage.items():
        report_lines.append(
            f"| {split_name} | {counts['addresses']:,} | "
            f"{counts['with_published_activity_features']:,} | "
            f"{counts['without_published_activity_features']:,} |"
        )
    report_lines.extend(
        [
            "",
            "Nombre d'adresses avec features par classe : "
            + "; ".join(
                f"{split_name} (non-scam={counts['with_features_by_class']['0']:,}, "
                f"scam={counts['with_features_by_class']['1']:,})"
                for split_name, counts in coverage.items()
            ),
            "",
            "## Faisabilité GNN",
            "",
            "Le dépôt Hugging Face publie un artifact d'arêtes complet de 21 572 870 251 octets (~20,1 Gio), ainsi qu'un mapping de nœuds et des labels. Cet artifact n'a pas été téléchargé. L'environnement ne contient pas PyTorch ni PyTorch Geometric, et le budget de calcul/mémoire ne permet pas de charger ce graphe intégral ; aucun GNN n'est déclaré entraîné. Une suite nécessitera un snapshot temporel plus petit ou un échantillonnage de voisins, un split de graphe sans arêtes de fuite et un runtime GPU/graph dédié.",
            "",
        ]
    )
    report_lines.extend(
        [
            "",
            "## Principales importances SHAP",
            "",
            "| Caractéristique | Moyenne de |SHAP| sur un échantillon de test |",
            "|---|---:|",
        ]
    )
    for row in shap_importance[:10]:
        report_lines.append(
            f"| `{row['feature']}` | {row['mean_abs_shap']:.6f} |"
        )
    report_lines.extend(
        [
            "",
            "SHAP décrit les contributions du modèle relativement au fond d'entraînement ; ce n'est pas une explication causale.",
            "",
            "Les caractéristiques sont agrégées depuis le parquet mensuel publié. L'API récupère les historiques normaux, internes, ERC-20, ERC-721 et ERC-1155, puis applique le même contrat de champs, unités et agrégations. Les caractéristiques exigeant l'état historique des contrats restent une source de décalage entre BigQuery et l'état actuel du RPC.",
        ]
    )
    (reports_dir / "ethereum_model_training.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    return {
        "best_iteration": selected_iteration,
        "coverage": coverage,
        "metrics": metrics,
        "model_bundle": str(model_dir / "model_bundle.joblib"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate Ethereum address XGBoost on fixed address splits."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/external/ethereum"),
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=Path("data/processed/ethereum-address-splits"),
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/ethereum_xgboost"),
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--seed", type=int, default=42)
    arguments = parser.parse_args()
    result = train(
        data_dir=arguments.data_dir,
        splits_dir=arguments.splits_dir,
        model_dir=arguments.model_dir,
        reports_dir=arguments.reports_dir,
        seed=arguments.seed,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
