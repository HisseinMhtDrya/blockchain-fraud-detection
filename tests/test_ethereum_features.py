import unittest

import numpy as np
import pandas as pd

from ethereum_features import (
    ADDRESS_FEATURES,
    LIVE_FEATURES,
    aggregate_monthly_frame,
    build_split_features,
    extract_live_features,
)


class EthereumFeatureTests(unittest.TestCase):
    def test_feature_contract_contains_26_live_features_and_contract_flag(self) -> None:
        self.assertEqual(len(LIVE_FEATURES), 26)
        self.assertEqual(len(ADDRESS_FEATURES), 27)
        self.assertEqual(ADDRESS_FEATURES[:-1], LIVE_FEATURES)
        self.assertEqual(ADDRESS_FEATURES[-1], "is_contract")

    def test_aggregate_monthly_sums_and_maxima(self) -> None:
        monthly = pd.DataFrame(
            [
                {
                    "node_id": 2**63 + 7,
                    "month": "2024-01",
                    "normal_sent_cnt": 2,
                    "burst_max_tx_5m": 3,
                    "eth_net_flow": "-1.250000000",
                },
                {
                    "node_id": 2**63 + 7,
                    "month": "2024-02",
                    "normal_sent_cnt": 4,
                    "burst_max_tx_5m": 5,
                    "eth_net_flow": "0.250000000",
                },
            ]
        )
        for column in (
            "active_span_min",
            "erc20_recv_cnt",
            "erc20_sent_cnt",
            "erc20_total_cnt",
            "erc20_unique_tokens_recv",
            "erc20_unique_tokens_sent",
            "eth_recv_sum",
            "eth_sent_sum",
            "gas_used_sum",
            "internal_in_cnt",
            "internal_in_value_eth_sum",
            "internal_out_cnt",
            "internal_out_value_eth_sum",
            "normal_recv_cnt",
            "normal_failed_cnt",
            "normal_to_contract_cnt",
            "normal_to_eoa_cnt",
            "normal_total_cnt",
            "sessions_cnt",
            "tx_fee_eth_sum",
            "uniq_contract_peers_cnt",
            "uniq_eoa_peers_cnt",
            "uniq_peers_cnt",
        ):
            monthly[column] = 0

        result = aggregate_monthly_frame(monthly).iloc[0]
        self.assertEqual(result["normal_sent_cnt"], 6)
        self.assertEqual(result["burst_max_tx_5m"], 5)
        self.assertAlmostEqual(result["eth_net_flow"], -1.0)

    def test_build_split_preserves_uint64_node_ids(self) -> None:
        address = "0x" + "a" * 40
        node_id = 2**63 + 123
        split = pd.DataFrame(
            [{"address": address.upper().replace("0X", "0x"), "is_scam": 1, "is_contract": 0}]
        )
        mapping = pd.DataFrame([{"address": address, "node_id": np.uint64(node_id)}])
        aggregates = pd.DataFrame(
            [{"normal_total_cnt": 9.0}],
            index=pd.Index([np.uint64(node_id)], name="node_id"),
        )
        for feature in ADDRESS_FEATURES:
            if feature not in ("normal_total_cnt", "is_contract"):
                aggregates[feature] = 0.0

        features, labels = build_split_features(split, mapping, aggregates)
        self.assertEqual(features.iloc[0]["normal_total_cnt"], 9)
        self.assertEqual(labels.iloc[0], 1)

    def test_live_feature_extraction_matches_monthly_contract(self) -> None:
        address = "0x" + "a" * 40
        peer = "0x" + "b" * 40
        other = "0x" + "c" * 40
        timestamp = 1_700_000_000
        contract_addresses = {peer}

        features = extract_live_features(
            address,
            [
                {
                    "from": address,
                    "to": peer,
                    "timeStamp": str(timestamp),
                    "value": str(10**18),
                    "gasUsed": "21000",
                    "gasPrice": str(10**9),
                    "isError": "0",
                },
                {
                    "from": other,
                    "to": address,
                    "timeStamp": str(timestamp + 30),
                    "value": str(5 * 10**17),
                    "gasUsed": "21000",
                    "gasPrice": str(10**9),
                    "isError": "0",
                },
            ],
            [
                {
                    "from": address,
                    "to": other,
                    "timeStamp": str(timestamp + 60),
                    "value": str(2 * 10**18),
                    "isError": "0",
                }
            ],
            [
                {
                    "from": address,
                    "to": other,
                    "timeStamp": str(timestamp + 90),
                    "contractAddress": "0x" + "d" * 40,
                },
                {
                    "from": address,
                    "to": other,
                    "timeStamp": str(timestamp + 24 * 60 * 60),
                    "contractAddress": "0x" + "d" * 40,
                },
            ],
            is_contract=False,
            is_contract_address=lambda candidate: candidate in contract_addresses,
        )

        self.assertEqual(tuple(features), ADDRESS_FEATURES)
        self.assertEqual(features["normal_sent_cnt"], 1)
        self.assertEqual(features["normal_recv_cnt"], 1)
        self.assertEqual(features["normal_total_cnt"], 2)
        self.assertEqual(features["normal_to_contract_cnt"], 1)
        self.assertEqual(features["normal_to_eoa_cnt"], 0)
        self.assertAlmostEqual(features["eth_sent_sum"], 1.0)
        self.assertAlmostEqual(features["eth_recv_sum"], 0.5)
        self.assertAlmostEqual(features["eth_net_flow"], -0.5)
        self.assertAlmostEqual(features["tx_fee_eth_sum"], 0.000021)
        self.assertEqual(features["internal_out_cnt"], 1)
        self.assertEqual(features["erc20_sent_cnt"], 2)
        self.assertEqual(features["erc20_unique_tokens_sent"], 1)
        self.assertEqual(features["uniq_peers_cnt"], 2)
        self.assertEqual(features["uniq_contract_peers_cnt"], 1)
        self.assertEqual(features["uniq_eoa_peers_cnt"], 1)
        self.assertEqual(features["burst_max_tx_5m"], 3)
        self.assertEqual(features["sessions_cnt"], 1)

    def test_malformed_provider_transaction_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "receipt status"):
            extract_live_features(
                "0x" + "a" * 40,
                [
                    {
                        "from": "0x" + "a" * 40,
                        "to": "0x" + "b" * 40,
                        "timeStamp": "1700000000",
                        "value": "0",
                        "gasUsed": "21000",
                        "gasPrice": "1000000000",
                    }
                ],
                [],
                [],
                is_contract=False,
                is_contract_address=lambda _: False,
            )

    def test_failed_internal_transactions_are_not_aggregated(self) -> None:
        address = "0x" + "a" * 40
        features = extract_live_features(
            address,
            [],
            [
                {
                    "from": address,
                    "to": "0x" + "b" * 40,
                    "timeStamp": "1700000000",
                    "value": str(10**18),
                    "isError": "1",
                }
            ],
            [],
            is_contract=False,
            is_contract_address=lambda _: False,
        )
        self.assertEqual(features["internal_out_cnt"], 0)
        self.assertEqual(features["internal_out_value_eth_sum"], 0)


if __name__ == "__main__":
    unittest.main()
