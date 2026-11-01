import json
import os
from pathlib import Path
from urllib.parse import urlparse

from web3 import Web3

from local_config import load_local_environment

BASE_DIR = Path(__file__).resolve().parent
load_local_environment(BASE_DIR / ".env")

RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.getenv(
    "BLOCKCHAIN_CONTRACT_ADDRESS",
    "0x5fbdb2315678afecb367f032d93f642f64180aa3",
)

ABI_PATH = (
    BASE_DIR
    / "artifacts"
    / "contracts"
    / "TransactionAlerts.sol"
    / "TransactionAlerts.json"
)

# Clé publique de développement Hardhat, autorisée uniquement sur localhost.
LOCAL_TEST_PRIVATE_KEY = (
    "0xac0974bec39a17e36ba4a6b4d238ff944"
    "bacb478cbed5efcae784d7bf4f2ff80"
)


def _resolve_signing_key(chain_id: int, rpc_url: str) -> str:
    rpc_host = urlparse(rpc_url).hostname
    if chain_id == 31337 and rpc_host in ("localhost", "127.0.0.1", "::1"):
        return LOCAL_TEST_PRIVATE_KEY
    if chain_id == 11155111:
        private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
        if not private_key:
            raise RuntimeError(
                "BLOCKCHAIN_PRIVATE_KEY doit être configurée localement "
                "pour signer les alertes sur Sepolia."
            )
        return private_key
    raise RuntimeError(
        "La signature d'alertes est limitée au Hardhat local (31337) "
        "et à Sepolia (11155111)."
    )


def _rpc_endpoint_label(rpc_url: str) -> str:
    return urlparse(rpc_url).hostname or "RPC configuré"


class BlockchainService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))

        if not self.w3.is_connected():
            raise ConnectionError(
                f"Blockchain inaccessible via {_rpc_endpoint_label(RPC_URL)}."
            )

        private_key = _resolve_signing_key(self.w3.eth.chain_id, RPC_URL)

        if not ABI_PATH.is_file():
            raise RuntimeError(
                f"Artefact ABI du contrat introuvable : {ABI_PATH}. "
                "Compilez le projet avec « npx hardhat build » avant de "
                "démarrer l'API."
            )

        with open(ABI_PATH, "r", encoding="utf-8-sig") as fichier:
            artefact = json.load(fichier)

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=artefact["abi"],
        )

        self._verifier_contrat_deploye()
        try:
            self.account = self.w3.eth.account.from_key(private_key)
        except ValueError as erreur:
            raise RuntimeError("BLOCKCHAIN_PRIVATE_KEY est invalide.") from erreur

        if not self.contract.functions.reporters(self.account.address).call():
            raise RuntimeError(
                f"Le compte d'alerte {self.account.address} n'est pas autorisé "
                "comme reporter du contrat."
            )

    def _verifier_contrat_deploye(self) -> None:
        code = self.w3.eth.get_code(self.contract.address)
        if not code:
            raise RuntimeError(
                f"Aucun contrat déployé à l'adresse {self.contract.address} "
                f"sur {_rpc_endpoint_label(RPC_URL)}. Déployez TransactionAlerts sur ce nœud, "
                "puis configurez BLOCKCHAIN_CONTRACT_ADDRESS si nécessaire."
            )

    def enregistrer_alerte(
        self,
        transaction_id: str,
        score_risque: int,
        illicite: bool,
    ) -> str:
        if not 0 <= score_risque <= 100:
            raise ValueError("Le score de risque doit être entre 0 et 100.")

        self._verifier_contrat_deploye()
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        transaction = self.contract.functions.recordAlert(
            transaction_id,
            score_risque,
            illicite,
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "chainId": self.w3.eth.chain_id,
                "gas": 300000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signee = self.account.sign_transaction(transaction)
        tx_hash = self.w3.eth.send_raw_transaction(signee.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError("L'enregistrement blockchain a échoué.")
        if receipt.transactionHash != tx_hash or receipt.blockNumber is None:
            raise RuntimeError(
                "Le reçu ne correspond pas à la transaction envoyée."
            )

        events = self.contract.events.AlertRecorded().process_receipt(receipt)
        if not any(
            event["args"]["transactionId"] == transaction_id
            and event["args"]["riskScore"] == score_risque
            and event["args"]["illicit"] == illicite
            and event["args"]["reporter"] == self.account.address
            for event in events
        ):
            raise RuntimeError(
                "Le reçu confirmé ne contient pas l'événement d'alerte attendu."
            )

        return tx_hash.hex()

    def lister_alertes(self, limite: int = 100) -> list[dict]:
        nombre = self.contract.functions.getAlertCount().call()
        debut = max(0, nombre - limite)
        alertes = []

        for alert_id in range(nombre - 1, debut - 1, -1):
            alerte = self.contract.functions.getAlert(alert_id).call()
            alertes.append(
                {
                    "id": alert_id,
                    "transaction_id": alerte[0],
                    "score_risque": alerte[1],
                    "illicite": alerte[2],
                    "timestamp": alerte[3],
                    "reporter": alerte[4],
                }
            )

        return alertes
