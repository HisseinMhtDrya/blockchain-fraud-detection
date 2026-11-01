import csv
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_ethereum_dataset import prepare_dataset


class EthereumDatasetPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / "labels.csv"
        self.output_path = self.root / "splits"
        self.rows = []

        address_number = 1
        for is_scam in (0, 1):
            for is_contract in (0, 1):
                for _ in range(100):
                    self.rows.append(
                        {
                            "address": f"0x{address_number:040x}",
                            "is_scam": is_scam,
                            "is_contract": is_contract,
                            "description": "must not be exported",
                            "activity_start_ts": "",
                            "activity_end_ts": "",
                        }
                    )
                    address_number += 1
        self.write_rows()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_rows(self) -> None:
        with self.input_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=self.rows[0].keys())
            writer.writeheader()
            writer.writerows(self.rows)

    def read_split_addresses(self, split_name: str) -> set[str]:
        with (self.output_path / f"{split_name}.csv").open(
            encoding="utf-8", newline=""
        ) as source:
            return {row["address"] for row in csv.DictReader(source)}

    def test_splits_are_disjoint_stratified_and_reproducible(self) -> None:
        self.rows.append(self.rows[0].copy())
        self.write_rows()

        manifest = prepare_dataset(self.input_path, self.output_path, seed=42)
        train = self.read_split_addresses("train")
        validation = self.read_split_addresses("validation")
        test = self.read_split_addresses("test")

        self.assertEqual(manifest["input_rows_after_deduplication"], 400)
        self.assertEqual(manifest["duplicate_rows_removed"], 1)
        self.assertEqual((len(train), len(validation), len(test)), (280, 60, 60))
        self.assertEqual(train & validation, set())
        self.assertEqual(train & test, set())
        self.assertEqual(validation & test, set())
        self.assertEqual(len(train | validation | test), 400)

        for split_name, expected_count in (
            ("train", 280),
            ("validation", 60),
            ("test", 60),
        ):
            with (self.output_path / f"{split_name}.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                reader = csv.DictReader(source)
                self.assertEqual(
                    reader.fieldnames, ["address", "is_scam", "is_contract"]
                )
                rows = list(reader)
            self.assertEqual(len(rows), expected_count)
            self.assertEqual(
                {(row["is_scam"], row["is_contract"]) for row in rows},
                {("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")},
            )

        second_output = self.root / "second-splits"
        prepare_dataset(self.input_path, second_output, seed=42)
        for split_name in ("train", "validation", "test"):
            with (second_output / f"{split_name}.csv").open(
                encoding="utf-8", newline=""
            ) as source:
                second_addresses = {
                    row["address"] for row in csv.DictReader(source)
                }
            self.assertEqual(self.read_split_addresses(split_name), second_addresses)

    def test_conflicting_duplicate_labels_are_rejected(self) -> None:
        conflict = self.rows[0].copy()
        conflict["is_scam"] = 1
        self.rows.append(conflict)
        self.write_rows()

        with self.assertRaisesRegex(ValueError, "Conflicting labels"):
            prepare_dataset(self.input_path, self.output_path)

        self.assertFalse(self.output_path.exists())

    def test_invalid_address_is_rejected(self) -> None:
        self.rows[0]["address"] = "not-an-address"
        self.write_rows()

        with self.assertRaisesRegex(ValueError, "Invalid Ethereum address"):
            prepare_dataset(self.input_path, self.output_path)

    def test_existing_outputs_are_not_overwritten(self) -> None:
        self.output_path.mkdir()
        existing_file = self.output_path / "train.csv"
        existing_file.write_text("keep me", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            prepare_dataset(self.input_path, self.output_path)

        self.assertEqual(existing_file.read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
