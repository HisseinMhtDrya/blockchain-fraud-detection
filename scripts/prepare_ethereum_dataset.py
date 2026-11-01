from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import TextIO

from sklearn.model_selection import train_test_split


DATASET_URL = (
    "https://huggingface.co/datasets/"
    "fesevu/ethereum_fraud_dataset_by_activity"
)
DATASET_REVISION = "6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70"
EXPECTED_SHA256 = (
    "52941005bd44d2597037e2e1c932e4d25fcf9c855980f442896cb497d1827b39"
)
ADDRESS_PATTERN = re.compile(r"0x[0-9a-f]{40}")
OUTPUT_COLUMNS = ("address", "is_scam", "is_contract")
REQUIRED_COLUMNS = frozenset(
    {"address", "is_scam", "is_contract", "description",
     "activity_start_ts", "activity_end_ts"}
)
SPLIT_FRACTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_csv(path: Path) -> TextIO:
    if path.name.lower().endswith(".zst"):
        try:
            import zstandard
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Compressed .zst input requires zstandard; install "
                "requirements-ethereum-data.txt."
            ) from error

        binary = path.open("rb")
        reader = zstandard.ZstdDecompressor().stream_reader(binary)
        return io.TextIOWrapper(reader, encoding="utf-8-sig", newline="")

    return path.open("r", encoding="utf-8-sig", newline="")


def load_address_labels(
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[dict[str, tuple[int, int]], int, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    input_sha256 = _sha256(path)
    if expected_sha256 and input_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            "Dataset SHA-256 mismatch: "
            f"expected {expected_sha256.lower()}, got {input_sha256}"
        )

    labels: dict[str, tuple[int, int]] = {}
    duplicate_rows = 0
    with _open_csv(path) as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("Dataset CSV is empty or has no header.")

        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                "Dataset is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            address = (row["address"] or "").strip().lower()
            if not ADDRESS_PATTERN.fullmatch(address):
                raise ValueError(
                    f"Invalid Ethereum address at CSV row {row_number}."
                )

            try:
                is_scam = int(row["is_scam"])
                is_contract = int(row["is_contract"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid label/type at CSV row {row_number}."
                ) from error

            if is_scam not in (0, 1) or is_contract not in (0, 1):
                raise ValueError(
                    f"Labels must be binary at CSV row {row_number}."
                )

            current = (is_scam, is_contract)
            existing = labels.get(address)
            if existing is not None:
                if existing != current:
                    raise ValueError(
                        "Conflicting labels or contract types for "
                        f"duplicate address at CSV row {row_number}."
                    )
                duplicate_rows += 1
                continue

            labels[address] = current

    if not labels:
        raise ValueError("Dataset contains no labeled addresses.")

    stratum_counts = Counter(labels.values())
    if set(label for label, _ in stratum_counts) != {0, 1}:
        raise ValueError("Both scam and non-scam labels are required.")
    if len(stratum_counts) != 4 or min(stratum_counts.values()) < 4:
        raise ValueError(
            "Each (is_scam, is_contract) stratum needs at least four addresses."
        )

    return labels, duplicate_rows, input_sha256


def _make_splits(
    labels: dict[str, tuple[int, int]],
    *,
    seed: int,
) -> dict[str, list[str]]:
    addresses = sorted(labels)
    strata = [f"{labels[address][0]}:{labels[address][1]}" for address in addresses]
    train, remainder, train_strata, remainder_strata = train_test_split(
        addresses,
        strata,
        test_size=0.30,
        random_state=seed,
        stratify=strata,
    )
    validation, test = train_test_split(
        remainder,
        test_size=0.50,
        random_state=seed,
        stratify=remainder_strata,
    )

    return {
        "train": sorted(train),
        "validation": sorted(validation),
        "test": sorted(test),
    }


def _split_summary(
    split_addresses: dict[str, list[str]],
    labels: dict[str, tuple[int, int]],
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for split_name, addresses in split_addresses.items():
        class_counts = Counter(labels[address][0] for address in addresses)
        contract_counts = Counter(labels[address][1] for address in addresses)
        summary[split_name] = {
            "addresses": len(addresses),
            "is_scam_0": class_counts[0],
            "is_scam_1": class_counts[1],
            "is_contract_0": contract_counts[0],
            "is_contract_1": contract_counts[1],
        }
    return summary


def prepare_dataset(
    input_path: Path,
    output_dir: Path,
    *,
    seed: int = 42,
    expected_sha256: str | None = None,
) -> dict:
    labels, duplicate_rows, input_sha256 = load_address_labels(
        input_path,
        expected_sha256=expected_sha256,
    )
    splits = _make_splits(labels, seed=seed)

    all_addresses = [address for values in splits.values() for address in values]
    if len(all_addresses) != len(set(all_addresses)):
        raise RuntimeError("An address was assigned to multiple data splits.")
    if set(all_addresses) != set(labels):
        raise RuntimeError("The data splits do not cover every unique address.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = [
        *(output_dir / f"{split_name}.csv" for split_name in SPLIT_FRACTIONS),
        output_dir / "manifest.json",
    ]
    existing_paths = [path for path in output_paths if path.exists()]
    if existing_paths:
        raise FileExistsError(
            "Refusing to overwrite existing output: "
            + ", ".join(str(path) for path in existing_paths)
        )

    for split_name, addresses in splits.items():
        with (output_dir / f"{split_name}.csv").open(
            "x", encoding="utf-8", newline=""
        ) as destination:
            writer = csv.DictWriter(destination, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for address in addresses:
                is_scam, is_contract = labels[address]
                writer.writerow(
                    {
                        "address": address,
                        "is_scam": is_scam,
                        "is_contract": is_contract,
                    }
                )

    manifest = {
        "dataset_url": DATASET_URL,
        "dataset_revision": DATASET_REVISION,
        "declared_license": "CC-BY-4.0",
        "input_filename": input_path.name,
        "input_sha256": input_sha256,
        "input_rows_after_deduplication": len(labels),
        "duplicate_rows_removed": duplicate_rows,
        "seed": seed,
        "split_fractions": SPLIT_FRACTIONS,
        "stratification": ["is_scam", "is_contract"],
        "predictor_policy": (
            "This manifest contains labels only. Exclude address, description, "
            "activity_start_ts, activity_end_ts, and is_scam from model inputs. "
            "Use is_contract only if the identical feature is available at inference."
        ),
        "splits": _split_summary(splits, labels),
    }
    with (output_dir / "manifest.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as destination:
        json.dump(manifest, destination, indent=2, sort_keys=True)
        destination.write("\n")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Ethereum address labels and create deterministic, "
            "address-disjoint train/validation/test partitions."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    arguments = parser.parse_args()

    manifest = prepare_dataset(
        arguments.input,
        arguments.output_dir,
        seed=arguments.seed,
        expected_sha256=arguments.expected_sha256,
    )
    print(json.dumps(manifest["splits"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
