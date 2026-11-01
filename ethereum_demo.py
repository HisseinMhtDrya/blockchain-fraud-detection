from __future__ import annotations

from ethereum_features import extract_live_features


DEMO_ADDRESS = "0x" + "a" * 40
DEMO_EOA = "0x" + "b" * 40
DEMO_CONTRACT = "0x" + "c" * 40
DEMO_TOKEN = "0x" + "d" * 40
DEMO_TIMESTAMP = 1_700_000_000


def build_demo_features() -> tuple[dict[str, float], dict[str, int]]:
    normal_transactions = [
        {
            "from": DEMO_ADDRESS,
            "to": DEMO_CONTRACT,
            "timeStamp": str(DEMO_TIMESTAMP),
            "value": str(10**18),
            "gasUsed": "50000",
            "gasPrice": str(20 * 10**9),
            "isError": "0",
        },
        {
            "from": DEMO_EOA,
            "to": DEMO_ADDRESS,
            "timeStamp": str(DEMO_TIMESTAMP + 60),
            "value": str(2 * 10**18),
            "gasUsed": "21000",
            "gasPrice": str(18 * 10**9),
            "isError": "0",
        },
        {
            "from": DEMO_ADDRESS,
            "to": DEMO_EOA,
            "timeStamp": str(DEMO_TIMESTAMP + 120),
            "value": str(5 * 10**17),
            "gasUsed": "21000",
            "gasPrice": str(19 * 10**9),
            "isError": "0",
        },
        {
            "from": DEMO_CONTRACT,
            "to": DEMO_ADDRESS,
            "timeStamp": str(DEMO_TIMESTAMP + 180),
            "value": str(25 * 10**16),
            "gasUsed": "65000",
            "gasPrice": str(17 * 10**9),
            "isError": "0",
        },
        {
            "from": DEMO_ADDRESS,
            "to": DEMO_EOA,
            "timeStamp": str(DEMO_TIMESTAMP + 240),
            "value": "0",
            "gasUsed": "21000",
            "gasPrice": str(19 * 10**9),
            "isError": "1",
        },
    ]
    internal_transactions = [
        {
            "from": DEMO_ADDRESS,
            "to": DEMO_EOA,
            "timeStamp": str(DEMO_TIMESTAMP + 300),
            "value": str(10**17),
            "isError": "0",
        }
    ]
    token_transfers = [
        {
            "from": DEMO_ADDRESS,
            "to": DEMO_EOA,
            "timeStamp": str(DEMO_TIMESTAMP + 360),
            "contractAddress": DEMO_TOKEN,
        },
        {
            "from": DEMO_EOA,
            "to": DEMO_ADDRESS,
            "timeStamp": str(DEMO_TIMESTAMP + 420),
            "contractAddress": DEMO_TOKEN,
        },
    ]
    features = extract_live_features(
        DEMO_ADDRESS,
        normal_transactions,
        internal_transactions,
        token_transfers,
        is_contract=False,
        is_contract_address=lambda address: address == DEMO_CONTRACT,
    )
    counts = {
        "transactions_normales": len(normal_transactions),
        "transactions_internes": len(internal_transactions),
        "transferts_erc20": len(token_transfers),
    }
    return features, counts
