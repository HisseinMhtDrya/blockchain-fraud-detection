from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

import numpy as np
import pandas as pd


MONTHLY_SUM_FEATURES = (
    "active_span_min",
    "erc20_recv_cnt",
    "erc20_sent_cnt",
    "erc20_total_cnt",
    "erc20_unique_tokens_recv",
    "erc20_unique_tokens_sent",
    "eth_net_flow",
    "eth_recv_sum",
    "eth_sent_sum",
    "gas_used_sum",
    "internal_in_cnt",
    "internal_in_value_eth_sum",
    "internal_out_cnt",
    "internal_out_value_eth_sum",
    "normal_failed_cnt",
    "normal_recv_cnt",
    "normal_sent_cnt",
    "normal_to_contract_cnt",
    "normal_to_eoa_cnt",
    "normal_total_cnt",
    "sessions_cnt",
    "tx_fee_eth_sum",
    "uniq_contract_peers_cnt",
    "uniq_eoa_peers_cnt",
    "uniq_peers_cnt",
)
MONTHLY_MAX_FEATURES = ("burst_max_tx_5m",)
ADDRESS_FEATURES = (
    "normal_sent_cnt",
    "normal_recv_cnt",
    "normal_total_cnt",
    "normal_failed_cnt",
    "normal_to_contract_cnt",
    "normal_to_eoa_cnt",
    "eth_sent_sum",
    "eth_recv_sum",
    "eth_net_flow",
    "tx_fee_eth_sum",
    "gas_used_sum",
    "erc20_sent_cnt",
    "erc20_recv_cnt",
    "erc20_total_cnt",
    "erc20_unique_tokens_sent",
    "erc20_unique_tokens_recv",
    "internal_out_cnt",
    "internal_in_cnt",
    "internal_out_value_eth_sum",
    "internal_in_value_eth_sum",
    "uniq_peers_cnt",
    "uniq_contract_peers_cnt",
    "uniq_eoa_peers_cnt",
    "active_span_min",
    "burst_max_tx_5m",
    "sessions_cnt",
    "is_contract",
)
LIVE_FEATURES = ADDRESS_FEATURES[:-1]


class EthereumFeatureDataError(ValueError):
    pass


def signed_log1p(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.sign(values) * np.log1p(np.abs(values))


def aggregate_monthly_frame(monthly: pd.DataFrame) -> pd.DataFrame:
    required = {"node_id", "month", *MONTHLY_SUM_FEATURES, *MONTHLY_MAX_FEATURES}
    missing = required.difference(monthly.columns)
    if missing:
        raise ValueError(
            "Monthly feature file is missing columns: " + ", ".join(sorted(missing))
        )
    if monthly.duplicated(["node_id", "month"]).any():
        raise ValueError("Monthly feature file contains duplicate node/month rows.")

    frame = monthly[["node_id", "month", *MONTHLY_SUM_FEATURES, *MONTHLY_MAX_FEATURES]].copy()
    for column in (*MONTHLY_SUM_FEATURES, *MONTHLY_MAX_FEATURES):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    totals = frame.groupby("node_id", sort=False)[list(MONTHLY_SUM_FEATURES)].sum()
    bursts = frame.groupby("node_id", sort=False)[list(MONTHLY_MAX_FEATURES)].max()
    return totals.join(bursts).astype(np.float64)


def build_split_features(
    split: pd.DataFrame,
    address_map: pd.DataFrame,
    monthly_aggregates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    required_split = {"address", "is_scam", "is_contract"}
    if missing := required_split.difference(split.columns):
        raise ValueError("Split is missing columns: " + ", ".join(sorted(missing)))
    if not {"address", "node_id"}.issubset(address_map.columns):
        raise ValueError("Address map must contain address and node_id columns.")

    rows = split.copy()
    rows["address"] = rows["address"].str.strip().str.lower()
    if rows["address"].duplicated().any():
        raise ValueError("An address appears more than once in a data split.")
    if not rows["is_scam"].isin((0, 1)).all():
        raise ValueError("Address labels must be binary.")
    if not rows["is_contract"].isin((0, 1)).all():
        raise ValueError("Contract labels must be binary.")

    mapping = address_map[["address", "node_id"]].copy()
    mapping["address"] = mapping["address"].str.strip().str.lower()
    if mapping["address"].duplicated().any():
        raise ValueError("Address map contains duplicate addresses.")
    address_to_node = dict(zip(mapping["address"], mapping["node_id"], strict=True))
    node_ids = rows["address"].map(address_to_node)
    if node_ids.isna().any():
        raise ValueError("Some split addresses are missing from the address map.")
    by_node = rows.set_index(pd.Index(node_ids.to_numpy(dtype=np.uint64), name="node_id"))
    features = monthly_aggregates.reindex(by_node.index)
    features = features.fillna(0)
    features["is_contract"] = by_node["is_contract"].to_numpy(dtype=np.float64)
    features = features.loc[:, ADDRESS_FEATURES].astype(np.float64)
    labels = by_node["is_scam"].astype(np.int8)
    labels.index = rows["address"].to_numpy()
    features.index = rows["address"].to_numpy()
    return features, labels


def _integer(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(str(value), 10)
    except (TypeError, ValueError) as error:
        raise EthereumFeatureDataError(
            f"Provider returned an invalid integer value: {value!r}."
        ) from error


def _required_integer(value: object, field: str) -> int:
    if value is None or value == "":
        raise EthereumFeatureDataError(f"Provider transaction is missing {field}.")
    try:
        return int(str(value), 10)
    except (TypeError, ValueError) as error:
        raise EthereumFeatureDataError(
            f"Provider transaction contains invalid {field}."
        ) from error


def _wei_to_eth(value: object, field: str = "value") -> float:
    return float(Decimal(_required_integer(value, field)) / Decimal(10**18))


def _timestamp(value: object) -> int:
    timestamp = _integer(value, -1)
    if timestamp < 0:
        raise EthereumFeatureDataError(
            "Transaction is missing a valid Unix timestamp."
        )
    try:
        datetime.fromtimestamp(timestamp, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise EthereumFeatureDataError(
            "Transaction contains an invalid Unix timestamp."
        ) from error
    return timestamp


def _day(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def _month(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m")


def _success(row: Mapping[str, object]) -> bool:
    status = row.get("isError", row.get("txreceipt_status", row.get("status")))
    if isinstance(status, bool) or status not in ("0", "1", 0, 1):
        raise EthereumFeatureDataError(
            "Provider transaction is missing a valid receipt status."
        )
    if row.get("errCode"):
        return False
    if "isError" in row:
        return str(row["isError"]) == "0"
    return str(status) == "1"


def _required_address(value: object, field: str, *, allow_empty: bool = False) -> str:
    address = str(value or "").lower()
    if allow_empty and not address:
        return address
    if not re.fullmatch(r"0x[0-9a-f]{40}", address):
        raise EthereumFeatureDataError(
            f"Provider transaction contains an invalid {field} address."
        )
    return address


def extract_live_features(
    address: str,
    normal_transactions: Iterable[Mapping[str, object]],
    internal_transactions: Iterable[Mapping[str, object]],
    token_transfers: Iterable[Mapping[str, object]],
    *,
    is_contract: bool,
    is_contract_address: Callable[[str], bool],
) -> dict[str, float]:
    address = address.lower()
    daily: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "normal_sent_cnt": 0,
            "normal_recv_cnt": 0,
            "normal_failed_cnt": 0,
            "normal_to_contract_cnt": 0,
            "normal_to_eoa_cnt": 0,
            "eth_sent_sum": 0.0,
            "eth_recv_sum": 0.0,
            "tx_fee_eth_sum": 0.0,
            "gas_used_sum": 0,
            "erc20_sent_cnt": 0,
            "erc20_recv_cnt": 0,
            "internal_out_cnt": 0,
            "internal_in_cnt": 0,
            "internal_out_value_eth_sum": 0.0,
            "internal_in_value_eth_sum": 0.0,
        }
    )
    events: dict[str, list[int]] = defaultdict(list)
    monthly_peers: dict[str, set[str]] = defaultdict(set)
    monthly_tokens_sent: dict[str, set[str]] = defaultdict(set)
    monthly_tokens_received: dict[str, set[str]] = defaultdict(set)
    monthly_events: dict[str, list[int]] = defaultdict(list)
    peer_addresses: set[str] = set()

    for transaction in normal_transactions:
        timestamp = _timestamp(transaction.get("timeStamp"))
        day = _day(timestamp)
        month = _month(timestamp)
        sender = _required_address(transaction.get("from"), "from")
        recipient = _required_address(
            transaction.get("to"), "to", allow_empty=True
        )
        value = _wei_to_eth(transaction.get("value"))
        gas_used = _required_integer(transaction.get("gasUsed"), "gasUsed")
        gas_price = _required_integer(transaction.get("gasPrice"), "gasPrice")
        succeeded = _success(transaction)
        if sender == address:
            stats = daily[day]
            stats["normal_sent_cnt"] += 1
            stats["eth_sent_sum"] += value
            stats["gas_used_sum"] += gas_used
            stats["tx_fee_eth_sum"] += gas_used * gas_price / 10**18
            if not succeeded:
                stats["normal_failed_cnt"] += 1
            if recipient:
                peer_addresses.add(recipient)
                monthly_peers[month].add(recipient)
                if is_contract_address(recipient):
                    stats["normal_to_contract_cnt"] += 1
                else:
                    stats["normal_to_eoa_cnt"] += 1
            events[day].append(timestamp)
            monthly_events[month].append(timestamp)
        if recipient == address:
            daily[day]["normal_recv_cnt"] += 1
            daily[day]["eth_recv_sum"] += value
            if sender:
                peer_addresses.add(sender)
                monthly_peers[month].add(sender)
            events[day].append(timestamp)
            monthly_events[month].append(timestamp)

    for transfer in token_transfers:
        timestamp = _timestamp(transfer.get("timeStamp"))
        month = _month(timestamp)
        sender = _required_address(transfer.get("from"), "from")
        recipient = _required_address(transfer.get("to"), "to")
        token = _required_address(transfer.get("contractAddress"), "token contract")
        if sender == address:
            daily[day]["erc20_sent_cnt"] += 1
            monthly_tokens_sent[month].add(token)
            if recipient:
                monthly_peers[month].add(recipient)
                peer_addresses.add(recipient)
        if recipient == address:
            daily[day]["erc20_recv_cnt"] += 1
            monthly_tokens_received[month].add(token)
            if sender:
                monthly_peers[month].add(sender)
                peer_addresses.add(sender)

    for transaction in internal_transactions:
        if not _success(transaction):
            continue
        sender = _required_address(transaction.get("from"), "from")
        recipient = _required_address(transaction.get("to"), "to")
        value_wei = _required_integer(transaction.get("value"), "value")
        if value_wei <= 0:
            continue
        timestamp = _timestamp(transaction.get("timeStamp"))
        day = _day(timestamp)
        month = _month(timestamp)
        value = _wei_to_eth(value_wei)
        if sender == address:
            daily[day]["internal_out_cnt"] += 1
            daily[day]["internal_out_value_eth_sum"] += value
            if recipient:
                monthly_peers[month].add(recipient)
                peer_addresses.add(recipient)
            events[day].append(timestamp)
            monthly_events[month].append(timestamp)
        if recipient == address:
            daily[day]["internal_in_cnt"] += 1
            daily[day]["internal_in_value_eth_sum"] += value
            if sender:
                monthly_peers[month].add(sender)
                peer_addresses.add(sender)
            events[day].append(timestamp)
            monthly_events[month].append(timestamp)

    peer_types = {peer: is_contract_address(peer) for peer in peer_addresses}
    monthly_peer_counts: dict[str, tuple[int, int, int]] = {}
    for month, peer_set in monthly_peers.items():
        contract_count = sum(peer_types.get(peer, False) for peer in peer_set)
        monthly_peer_counts[month] = (
            len(peer_set),
            contract_count,
            len(peer_set) - contract_count,
        )

    totals = {name: 0.0 for name in LIVE_FEATURES}
    for month in monthly_peers.keys() | monthly_tokens_sent.keys() | monthly_tokens_received.keys():
        peer_count, contract_count, eoa_count = monthly_peer_counts.get(
            month, (0, 0, 0)
        )
        totals["uniq_peers_cnt"] += peer_count
        totals["uniq_contract_peers_cnt"] += contract_count
        totals["uniq_eoa_peers_cnt"] += eoa_count
        totals["erc20_unique_tokens_sent"] += len(monthly_tokens_sent[month])
        totals["erc20_unique_tokens_recv"] += len(monthly_tokens_received[month])

    for day, stats in daily.items():
        sent = stats["normal_sent_cnt"]
        received = stats["normal_recv_cnt"]
        stats["normal_total_cnt"] = sent + received
        stats["eth_net_flow"] = stats["eth_recv_sum"] - stats["eth_sent_sum"]
        stats["erc20_total_cnt"] = (
            stats["erc20_sent_cnt"] + stats["erc20_recv_cnt"]
        )

        timestamps = sorted(events[day])
        if len(timestamps) >= 2:
            stats["active_span_min"] = (timestamps[-1] - timestamps[0]) // 60
        else:
            stats["active_span_min"] = 0
        for name in LIVE_FEATURES:
            if name not in (
                "burst_max_tx_5m",
                "sessions_cnt",
                "uniq_peers_cnt",
                "uniq_contract_peers_cnt",
                "uniq_eoa_peers_cnt",
                "erc20_unique_tokens_sent",
                "erc20_unique_tokens_recv",
            ):
                totals[name] += stats.get(name, 0)

    for timestamps in monthly_events.values():
        timestamps.sort()
        totals["sessions_cnt"] += 1 + sum(
            current - previous > 30 * 60
            for previous, current in zip(timestamps, timestamps[1:])
        )

    all_events = [timestamp for timestamps in monthly_events.values() for timestamp in timestamps]
    per_minute: dict[int, int] = defaultdict(int)
    for timestamp in all_events:
        per_minute[timestamp // 60] += 1
    if per_minute:
        first_minute = min(per_minute)
        last_minute = max(per_minute)
        totals["burst_max_tx_5m"] = max(
            sum(per_minute.get(minute - offset, 0) for offset in range(5))
            for minute in range(first_minute, last_minute + 1)
        )

    return {
        **totals,
        "is_contract": float(is_contract),
    }


def load_monthly_aggregates(path: Path) -> pd.DataFrame:
    monthly = pd.read_parquet(path)
    return aggregate_monthly_frame(monthly)
