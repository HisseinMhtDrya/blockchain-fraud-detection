import pandas as pd
import requests
from pathlib import Path

fichier = Path("data/raw/archive/elliptic_bitcoin_dataset/elliptic_txs_features.csv")
donnees = pd.read_csv(fichier, header=None)

transaction = donnees.iloc[0, 1:].astype(float).tolist()

reponse = requests.post(
    "http://127.0.0.1:8000/predict",
    json={
        "features": transaction,
        "transaction_id": "tx-test-blockchain-001"
    },
    timeout=60
)

print("Code HTTP :", reponse.status_code)
print("Résultat :", reponse.text)
