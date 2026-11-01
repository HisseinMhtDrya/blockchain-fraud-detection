from collections.abc import Generator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@contextmanager
def _connection(database_path: Path) -> Generator[sqlite3.Connection, None, None]:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            yield connection


def initialize_history(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with _connection(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT,
                classe_predite INTEGER NOT NULL CHECK (classe_predite IN (0, 1)),
                probabilite_licite REAL NOT NULL,
                probabilite_illicite REAL NOT NULL,
                score_risque INTEGER NOT NULL CHECK (score_risque BETWEEN 0 AND 100),
                blockchain_enregistre INTEGER NOT NULL CHECK (blockchain_enregistre IN (0, 1)),
                hash_transaction_blockchain TEXT,
                erreur_blockchain TEXT,
                cree_le TEXT NOT NULL,
                type_analyse TEXT DEFAULT 'bitcoin' CHECK (type_analyse IN ('bitcoin', 'ethereum'))
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analyses)")
        }
        if "type_analyse" not in columns:
            connection.execute(
                """
                ALTER TABLE analyses
                ADD COLUMN type_analyse TEXT DEFAULT 'bitcoin'
                CHECK (type_analyse IN ('bitcoin', 'ethereum'))
                """
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_cree_le ON analyses (cree_le DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_transaction_id ON analyses (transaction_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_type ON analyses (type_analyse)"
        )


def save_analysis(
    database_path: Path,
    transaction_id: str | None,
    predicted_class: int,
    legal_probability: float,
    illicit_probability: float,
    risk_score: int,
    blockchain_recorded: bool,
    blockchain_hash: str | None,
    blockchain_error: str | None,
    analysis_type: str = "bitcoin",
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connection(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO analyses (
                transaction_id,
                classe_predite,
                probabilite_licite,
                probabilite_illicite,
                score_risque,
                blockchain_enregistre,
                hash_transaction_blockchain,
                erreur_blockchain,
                cree_le,
                type_analyse
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                predicted_class,
                legal_probability,
                illicit_probability,
                risk_score,
                int(blockchain_recorded),
                blockchain_hash,
                blockchain_error,
                created_at,
                analysis_type,
            ),
        )
        return cursor.lastrowid


def list_analyses(
    database_path: Path,
    *,
    limit: int,
    offset: int,
    query: str | None = None,
    predicted_class: int | None = None,
    blockchain_recorded: bool | None = None,
    analysis_type: str | None = None,
) -> dict:
    conditions: list[str] = []
    parameters: list[object] = []

    if query:
        search_pattern = f"%{query.strip()}%"
        conditions.append(
            "(transaction_id LIKE ? COLLATE NOCASE OR CAST(id AS TEXT) LIKE ?)"
        )
        parameters.extend((search_pattern, search_pattern))

    if predicted_class is not None:
        conditions.append("classe_predite = ?")
        parameters.append(predicted_class)

    if blockchain_recorded is not None:
        conditions.append("blockchain_enregistre = ?")
        parameters.append(int(blockchain_recorded))

    if analysis_type is not None:
        conditions.append("type_analyse = ?")
        parameters.append(analysis_type)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with _connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        total = connection.execute(
            f"SELECT COUNT(*) FROM analyses {where_clause}",
            parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT
                id,
                transaction_id,
                classe_predite,
                probabilite_licite,
                probabilite_illicite,
                score_risque,
                blockchain_enregistre,
                hash_transaction_blockchain,
                erreur_blockchain,
                cree_le,
                type_analyse
            FROM analyses
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            [*parameters, limit, offset],
        ).fetchall()

    analyses = []
    for row in rows:
        analysis = dict(row)
        analysis["blockchain_enregistre"] = bool(analysis["blockchain_enregistre"])
        analyses.append(analysis)

    return {"analyses": analyses, "total": total}


def get_history_summary(database_path: Path) -> dict:
    with _connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_analyses,
                COALESCE(SUM(classe_predite), 0) AS analyses_illicites,
                COALESCE(SUM(blockchain_enregistre), 0) AS analyses_enregistrees,
                COALESCE(AVG(score_risque), 0) AS score_moyen
            FROM analyses
            """
        ).fetchone()

        blockchain_rows = connection.execute(
            """
            SELECT
                type_analyse,
                COUNT(*) AS total,
                COALESCE(SUM(classe_predite), 0) AS risk_detected,
                COALESCE(SUM(blockchain_enregistre), 0) AS recorded,
                COALESCE(AVG(score_risque), 0) AS average_risk
            FROM analyses
            GROUP BY type_analyse
            """
        ).fetchall()

        daily_rows = connection.execute(
            """
            SELECT
                type_analyse,
                substr(cree_le, 1, 10) AS jour,
                COUNT(*) AS total,
                COALESCE(SUM(classe_predite), 0) AS risk_detected
            FROM analyses
            WHERE cree_le >= datetime('now', '-89 days')
            GROUP BY type_analyse, jour
            ORDER BY jour, type_analyse
            """
        ).fetchall()

    total_analyses, analyses_illicites, analyses_enregistrees, score_moyen = row
    per_blockchain = {
        chain: {
            "total_analyses": 0,
            "risques_detectes": 0,
            "alertes_enregistrees": 0,
            "part_risque_detecte": None,
            "score_risque_moyen": 0,
            "evolution": [],
        }
        for chain in ("bitcoin", "ethereum")
    }
    for chain, total, risks_detected, recorded, average_risk in blockchain_rows:
        chain_summary = per_blockchain[chain]
        chain_summary.update(
            {
                "total_analyses": total,
                "risques_detectes": risks_detected,
                "alertes_enregistrees": recorded,
                "part_risque_detecte": (
                    risks_detected / total if total else None
                ),
                "score_risque_moyen": round(average_risk, 2),
            }
        )
    for chain, day, total, risks_detected in daily_rows:
        per_blockchain[chain]["evolution"].append(
            {
                "jour": day,
                "total": total,
                "risques_detectes": risks_detected,
            }
        )

    return {
        "total_analyses": total_analyses,
        "analyses_illicites": analyses_illicites,
        "analyses_enregistrees": analyses_enregistrees,
        "analyses_bitcoin": per_blockchain["bitcoin"]["total_analyses"],
        "analyses_ethereum": per_blockchain["ethereum"]["total_analyses"],
        "part_illicite": (
            analyses_illicites / total_analyses if total_analyses else None
        ),
        "score_moyen": round(score_moyen, 2),
        "par_blockchain": per_blockchain,
        "evolution": [
            {
                "jour": day,
                "type_analyse": chain,
                "total": total,
                "risques_detectes": risks_detected,
            }
            for chain, day, total, risks_detected in daily_rows
        ],
    }
