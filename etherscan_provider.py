from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence


ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
DEFAULT_ETHEREUM_RPC_URL = "https://ethereum-rpc.publicnode.com"
FALLBACK_ETHEREUM_RPC_URLS = (
    DEFAULT_ETHEREUM_RPC_URL,
    "https://eth.drpc.org",
    "https://eth-mainnet.public.blastapi.io",
)
ADDRESS_PATTERN = re.compile(r"0x[0-9a-fA-F]{40}")
PAGE_SIZE = 10_000
MAX_PAGES_PER_ACTION = 100
MAX_CONTRACT_LOOKUPS = 20_000
RPC_BATCH_SIZE = 100
RPC_RATE_LIMIT_RETRIES = 3
RPC_RATE_LIMIT_BACKOFF_SECONDS = 1


class EthereumProviderError(RuntimeError):
    pass


class EthereumRpcAuthenticationError(EthereumProviderError):
    pass


class EthereumProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        rpc_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ETHERSCAN_API_KEY")
        configured_rpc_url = rpc_url or os.getenv("ETHEREUM_RPC_URL")
        self.rpc_url = configured_rpc_url or DEFAULT_ETHEREUM_RPC_URL
        if not self.api_key:
            raise EthereumProviderError(
                "ETHERSCAN_API_KEY is required for Ethereum address analysis."
            )
        self._rpc_id = 0
        self._verify_mainnet()

    @staticmethod
    def _read_json(request: urllib.request.Request) -> object:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            host = urllib.parse.urlparse(request.full_url).hostname
            if host == urllib.parse.urlparse(ETHERSCAN_API_URL).hostname:
                raise EthereumProviderError(
                    f"Etherscan returned HTTP {error.code}."
                ) from error
            error_type = (
                EthereumRpcAuthenticationError
                if error.code in (401, 403)
                else EthereumProviderError
            )
            raise error_type(
                f"Configured Ethereum RPC returned HTTP {error.code}."
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise EthereumProviderError(
                "Could not reach the configured Ethereum provider."
            ) from error
        except json.JSONDecodeError as error:
            raise EthereumProviderError(
                "Ethereum provider returned invalid JSON."
            ) from error

    def _rpc_request(self, payload: object) -> object:
        def create_request(
            rpc_url: str,
            request_payload: object,
        ) -> urllib.request.Request:
            return urllib.request.Request(
                rpc_url,
                data=json.dumps(request_payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "blockchain-fraud-detection/ethereum-phase4",
                },
                method="POST",
            )

        try:
            return self._read_json(create_request(self.rpc_url, payload))
        except EthereumRpcAuthenticationError as original_error:
            for fallback_url in FALLBACK_ETHEREUM_RPC_URLS:
                if fallback_url == self.rpc_url:
                    continue
                try:
                    chain_response = self._read_json(
                        create_request(
                            fallback_url,
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "eth_chainId",
                                "params": [],
                            },
                        )
                    )
                except EthereumRpcAuthenticationError:
                    continue

                if not isinstance(chain_response, Mapping) or chain_response.get(
                    "error"
                ):
                    raise EthereumProviderError(
                        "Could not verify the fallback RPC chain ID."
                    )
                try:
                    chain_id = int(str(chain_response["result"]), 16)
                except (KeyError, TypeError, ValueError) as error:
                    raise EthereumProviderError(
                        "The fallback RPC returned an invalid chain ID."
                    ) from error
                if chain_id != 1:
                    raise EthereumProviderError(
                        "The fallback RPC is not Ethereum mainnet."
                    )

                try:
                    response = self._read_json(create_request(fallback_url, payload))
                except EthereumRpcAuthenticationError:
                    continue
                self.rpc_url = fallback_url
                return response

            if self.rpc_url in FALLBACK_ETHEREUM_RPC_URLS:
                raise
            raise original_error

    def _verify_mainnet(self) -> None:
        result = self._rpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}
        )
        if not isinstance(result, Mapping) or result.get("error"):
            raise EthereumProviderError(
                "Could not verify the configured RPC chain ID."
            )
        try:
            chain_id = int(str(result["result"]), 16)
        except (KeyError, TypeError, ValueError) as error:
            raise EthereumProviderError(
                "The configured RPC returned an invalid chain ID."
            ) from error
        if chain_id != 1:
            raise EthereumProviderError(
                f"Expected Ethereum mainnet chain ID 1, received {chain_id}."
            )

    def _etherscan_page(
        self,
        address: str,
        action: str,
        page: int,
    ) -> list[dict[str, object]]:
        parameters = urllib.parse.urlencode(
            {
                "chainid": 1,
                "module": "account",
                "action": action,
                "address": address,
                "page": page,
                "offset": PAGE_SIZE,
                "sort": "asc",
                "apikey": self.api_key,
            }
        )
        request = urllib.request.Request(
            f"{ETHERSCAN_API_URL}?{parameters}",
            headers={"User-Agent": "blockchain-fraud-detection/ethereum-phase4"},
        )
        result = self._read_json(request)
        if not isinstance(result, Mapping):
            raise EthereumProviderError(
                f"Etherscan returned an invalid response for {action}."
            )

        status = result.get("status")
        payload = result.get("result")
        if status in ("0", 0):
            message = str(payload or result.get("message", "")).lower()
            if "no transactions found" in message or "no records found" in message:
                return []
            raise EthereumProviderError(
                f"Etherscan rejected the {action} request."
            )
        if status not in ("1", 1):
            raise EthereumProviderError(
                f"Etherscan returned an invalid status for {action}."
            )
        if not isinstance(payload, list):
            raise EthereumProviderError(
                f"Etherscan returned an invalid result for {action}."
            )
        if any(not isinstance(row, dict) for row in payload):
            raise EthereumProviderError(
                f"Etherscan returned malformed rows for {action}."
            )
        return payload

    def _all_transactions(self, address: str, action: str) -> list[dict[str, object]]:
        transactions: list[dict[str, object]] = []
        for page in range(1, MAX_PAGES_PER_ACTION + 1):
            if page > 1:
                time.sleep(0.22)
            rows = self._etherscan_page(address, action, page)
            transactions.extend(rows)
            if len(rows) < PAGE_SIZE:
                return transactions
        raise EthereumProviderError(
            f"Etherscan {action} history exceeded the configured safety limit; "
            "analysis was stopped instead of using truncated data."
        )

    def get_address_history(
        self,
        address: str,
    ) -> tuple[
        list[dict[str, object]],
        list[dict[str, object]],
        list[dict[str, object]],
    ]:
        if not ADDRESS_PATTERN.fullmatch(address):
            raise ValueError("Invalid Ethereum address.")
        address = address.lower()
        return (
            self._all_transactions(address, "txlist"),
            self._all_transactions(address, "txlistinternal"),
            self._all_transactions(address, "tokentx"),
        )

    def contract_flags(self, addresses: Sequence[str]) -> dict[str, bool]:
        normalized_addresses = [address.lower() for address in addresses]
        invalid_addresses = [
            address
            for address in normalized_addresses
            if not ADDRESS_PATTERN.fullmatch(address)
        ]
        if invalid_addresses:
            raise EthereumProviderError(
                "The provider returned an invalid counterparty address."
            )
        unique_addresses = sorted(set(normalized_addresses))
        if len(unique_addresses) > MAX_CONTRACT_LOOKUPS:
            raise EthereumProviderError(
                "This address has too many distinct counterparties for the "
                "configured RPC lookup limit; no partial analysis was returned."
            )

        flags: dict[str, bool] = {}
        for offset in range(0, len(unique_addresses), RPC_BATCH_SIZE):
            chunk = unique_addresses[offset : offset + RPC_BATCH_SIZE]
            requests = []
            expected_ids: dict[int, str] = {}
            for address in chunk:
                self._rpc_id += 1
                request_id = self._rpc_id
                expected_ids[request_id] = address
                requests.append(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "eth_getCode",
                        "params": [address, "latest"],
                    }
                )
            pending = expected_ids
            retry_count = 0
            while pending:
                response = self._rpc_request(
                    [
                        request
                        for request in requests
                        if request["id"] in pending
                    ]
                )
                if not isinstance(response, list):
                    raise EthereumProviderError(
                        "The configured RPC provider does not support JSON-RPC batches."
                    )

                received: dict[int, Mapping[str, object]] = {}
                for item in response:
                    if not isinstance(item, Mapping):
                        raise EthereumProviderError(
                            "The RPC returned an invalid batch response."
                        )
                    try:
                        request_id = int(item["id"])
                    except (KeyError, TypeError, ValueError) as error:
                        raise EthereumProviderError(
                            "The RPC returned an invalid batch response."
                        ) from error
                    if request_id not in pending or request_id in received:
                        raise EthereumProviderError(
                            "The RPC returned an invalid batch response."
                        )
                    received[request_id] = item
                if set(received) != set(pending):
                    raise EthereumProviderError(
                        "The RPC returned an incomplete contract-type batch."
                    )

                rate_limited: dict[int, str] = {}
                for request_id, item in received.items():
                    rpc_error = item.get("error")
                    if rpc_error:
                        if (
                            isinstance(rpc_error, Mapping)
                            and str(rpc_error.get("code")) == "429"
                        ):
                            rate_limited[request_id] = pending[request_id]
                            continue
                        raise EthereumProviderError(
                            "The RPC could not determine a counterparty contract type."
                        )

                    code = item.get("result")
                    if not isinstance(code, str) or not code.startswith("0x"):
                        raise EthereumProviderError(
                            "The RPC returned an invalid contract-code result."
                        )
                    flags[pending[request_id]] = code not in ("0x", "0x0")

                pending = rate_limited
                if pending:
                    if retry_count >= RPC_RATE_LIMIT_RETRIES:
                        raise EthereumProviderError(
                            "The configured RPC is rate-limiting contract-type "
                            "lookups; retry the analysis shortly."
                        )
                    time.sleep(
                        RPC_RATE_LIMIT_BACKOFF_SECONDS * (2**retry_count)
                    )
                    retry_count += 1
        return flags
