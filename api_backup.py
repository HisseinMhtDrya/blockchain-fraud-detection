
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "xgboost_blockchain.pkl"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Modèle introuvable : {MODEL_PATH}")

model = joblib.load(MODEL_PATH)

app = FastAPI(
    title="Détection de transactions blockchain suspectes",
    version="1.0.0"
)


class Transaction(BaseModel):
    features: list[float] = Field(min_length=166, max_length=166)


@app.get("/")
def accueil():
    return {
        "message": "API opérationnelle",
        "caracteristiques_attendues": 166
    }


@app.post("/predict")
def predire(transaction: Transaction):
    donnees = pd.DataFrame(
        [transaction.features],
        columns=model.feature_names_in_
    )

    prediction = int(model.predict(donnees)[0])
    probabilites = model.predict_proba(donnees)[0]

    return {
        "prediction": "illicite" if prediction == 1 else "licite",
        "classe_predite": prediction,
        "probabilite_licite": round(float(probabilites[0]), 4),
        "probabilite_illicite": round(float(probabilites[1]), 4),
        "avertissement": (
            "Résultat expérimental, et non une preuve de fraude "
            "ou de blanchiment."
        )
    }
