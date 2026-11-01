from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analysis_history import (
    get_history_summary,
    initialize_history,
    list_analyses,
    save_analysis,
)


class AnalysisHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "history.sqlite3"
        initialize_history(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def save(
        self,
        transaction_id: str | None,
        predicted_class: int,
        risk_score: int,
        blockchain_recorded: bool,
        analysis_type: str = "bitcoin",
    ) -> int:
        return save_analysis(
            self.database_path,
            transaction_id,
            predicted_class,
            1 - risk_score / 100,
            risk_score / 100,
            risk_score,
            blockchain_recorded,
            "0xabc123" if blockchain_recorded else None,
            None if blockchain_recorded else "No transaction ID",
            analysis_type=analysis_type,
        )

    def test_initialize_history_migrates_legacy_schema(self) -> None:
        legacy_database = Path(self.temporary_directory.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_database)) as connection, connection:
            connection.execute(
                """
                CREATE TABLE analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT,
                    classe_predite INTEGER NOT NULL,
                    probabilite_licite REAL NOT NULL,
                    probabilite_illicite REAL NOT NULL,
                    score_risque INTEGER NOT NULL,
                    blockchain_enregistre INTEGER NOT NULL,
                    hash_transaction_blockchain TEXT,
                    erreur_blockchain TEXT,
                    cree_le TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO analyses (
                    transaction_id,
                    classe_predite,
                    probabilite_licite,
                    probabilite_illicite,
                    score_risque,
                    blockchain_enregistre,
                    cree_le
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("legacy-tx", 1, 0.1, 0.9, 90, 0, "2024-01-01T00:00:00+00:00"),
            )

        initialize_history(legacy_database)

        with closing(sqlite3.connect(legacy_database)) as connection, connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(analyses)")
            }
            indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(analyses)")
            }

        self.assertIn("type_analyse", columns)
        self.assertIn("idx_analyses_type", indexes)
        history = list_analyses(legacy_database, limit=10, offset=0)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["analyses"][0]["transaction_id"], "legacy-tx")
        self.assertEqual(history["analyses"][0]["classe_predite"], 1)
        self.assertEqual(history["analyses"][0]["score_risque"], 90)
        self.assertEqual(history["analyses"][0]["type_analyse"], "bitcoin")
        summary = get_history_summary(legacy_database)
        self.assertEqual(summary["total_analyses"], 1)
        self.assertEqual(summary["analyses_bitcoin"], 1)

    def test_history_returns_analysis_types_and_separate_kpis(self) -> None:
        self.save("btc-tx", 0, 10, False)
        self.save("eth-address", 1, 90, False, analysis_type="ethereum")

        page = list_analyses(self.database_path, limit=10, offset=0)
        summary = get_history_summary(self.database_path)

        self.assertEqual(
            [analysis["type_analyse"] for analysis in page["analyses"]],
            ["ethereum", "bitcoin"],
        )
        self.assertEqual(summary["total_analyses"], 2)
        self.assertEqual(summary["analyses_bitcoin"], 1)
        self.assertEqual(summary["analyses_ethereum"], 1)
        self.assertEqual(summary["analyses_illicites"], 1)
        self.assertEqual(summary["score_moyen"], 50)
        self.assertEqual(
            summary["par_blockchain"]["bitcoin"]["risques_detectes"],
            0,
        )
        self.assertEqual(
            summary["par_blockchain"]["ethereum"]["risques_detectes"],
            1,
        )
        self.assertEqual(
            summary["par_blockchain"]["ethereum"]["part_risque_detecte"],
            1,
        )
        ethereum_history = list_analyses(
            self.database_path,
            limit=10,
            offset=0,
            analysis_type="ethereum",
        )
        self.assertEqual(ethereum_history["total"], 1)
        self.assertEqual(
            ethereum_history["analyses"][0]["transaction_id"],
            "eth-address",
        )

    def test_history_keeps_each_prediction_and_summary(self) -> None:
        self.save("elliptic-001", 1, 90, True)
        self.save("elliptic-002", 0, 12, False)
        self.save(None, 1, 70, False)

        page = list_analyses(self.database_path, limit=10, offset=0)
        summary = get_history_summary(self.database_path)

        self.assertEqual(page["total"], 3)
        self.assertEqual([row["transaction_id"] for row in page["analyses"]], [
            None,
            "elliptic-002",
            "elliptic-001",
        ])
        self.assertEqual(summary["total_analyses"], 3)
        self.assertEqual(summary["analyses_illicites"], 2)
        self.assertEqual(summary["analyses_enregistrees"], 1)
        self.assertAlmostEqual(summary["part_illicite"], 2 / 3)

    def test_history_search_filters_and_pagination(self) -> None:
        self.save("elliptic-001", 1, 90, True)
        self.save("elliptic-002", 0, 12, False)
        self.save("other-003", 1, 70, False)

        filtered = list_analyses(
            self.database_path,
            limit=10,
            offset=0,
            query="ELLIPTIC",
            predicted_class=0,
            blockchain_recorded=False,
        )
        second_page = list_analyses(self.database_path, limit=1, offset=1)

        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["analyses"][0]["transaction_id"], "elliptic-002")
        self.assertEqual(second_page["total"], 3)
        self.assertEqual(len(second_page["analyses"]), 1)


if __name__ == "__main__":
    unittest.main()
