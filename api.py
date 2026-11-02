from pathlib import Path
import os
import math

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from analysis_history import get_history_summary, initialize_history, list_analyses, save_analysis
from blockchain_service import BlockchainService
from ethereum_analyzer import EthereumAddressAnalyzer
from ethereum_demo import build_demo_features
from ethereum_features import EthereumFeatureDataError, extract_live_features
from etherscan_provider import EthereumProvider, EthereumProviderError

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "xgboost_blockchain.pkl"
ETHEREUM_MODEL_DIR = BASE_DIR / "models" / "ethereum_xgboost"
ETHEREUM_MODEL_PATH = ETHEREUM_MODEL_DIR / "model_bundle.joblib"
ETHEREUM_SHAP_BACKGROUND_PATH = ETHEREUM_MODEL_DIR / "shap_background.npy"
FRONTEND_PATH = BASE_DIR / "frontend"
FEATURES_PATH = (
    BASE_DIR
    / "data"
    / "raw"
    / "archive"
    / "elliptic_bitcoin_dataset"
    / "elliptic_txs_features.csv"
)
HISTORY_DB_PATH = Path(
    os.getenv("ANALYSIS_HISTORY_DB", str(BASE_DIR / "data" / "analysis_history.sqlite3"))
)

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Modèle introuvable : {MODEL_PATH}")

model = joblib.load(MODEL_PATH)
initialize_history(HISTORY_DB_PATH)

app = FastAPI(
    title="Détection de transactions blockchain suspectes",
    version="1.1.0",
)

blockchain = None
blockchain_error = None
bitcoin_explainer = None
ethereum_analyzer = None
ethereum_analyzer_error = None
ethereum_provider = None
ethereum_provider_error = None


def _erreur_sans_secrets(erreur: Exception) -> str:
    message = str(erreur)
    for variable in ("BLOCKCHAIN_RPC_URL", "BLOCKCHAIN_PRIVATE_KEY"):
        valeur = os.getenv(variable)
        if valeur:
            message = message.replace(valeur, "[masqué]")
    return message


try:
    blockchain = BlockchainService()
except (ConnectionError, RuntimeError) as erreur:
    blockchain_error = _erreur_sans_secrets(erreur)


def obtenir_blockchain():
    global blockchain, blockchain_error

    if blockchain is not None and not blockchain.w3.is_connected():
        blockchain = None

    if blockchain is None:
        try:
            blockchain = BlockchainService()
            blockchain_error = None
        except (ConnectionError, RuntimeError) as erreur:
            blockchain_error = _erreur_sans_secrets(erreur)

    return blockchain


def obtenir_analyseur_ethereum():
    global ethereum_analyzer, ethereum_analyzer_error

    if ethereum_analyzer is None:
        if not ETHEREUM_MODEL_PATH.is_file():
            ethereum_analyzer_error = (
                "Le modèle Ethereum est absent. Exécutez "
                "scripts/train_ethereum_xgboost.py."
            )
            return None
        if not ETHEREUM_SHAP_BACKGROUND_PATH.is_file():
            ethereum_analyzer_error = "Le fond SHAP du modèle Ethereum est absent."
            return None
        try:
            ethereum_analyzer = EthereumAddressAnalyzer(
                ETHEREUM_MODEL_PATH,
                ETHEREUM_SHAP_BACKGROUND_PATH,
            )
            ethereum_analyzer_error = None
        except (ImportError, OSError, ValueError, RuntimeError) as erreur:
            ethereum_analyzer_error = str(erreur)

    return ethereum_analyzer


def obtenir_fournisseur_ethereum():
    global ethereum_provider, ethereum_provider_error

    if ethereum_provider is None:
        try:
            ethereum_provider = EthereumProvider()
            ethereum_provider_error = None
        except EthereumProviderError as erreur:
            ethereum_provider_error = str(erreur)

    return ethereum_provider


@app.get("/api/status")
def statut_services():
    service_blockchain = obtenir_blockchain()
    analyseur_ethereum_disponible = obtenir_analyseur_ethereum() is not None
    chain_id = (
        service_blockchain.w3.eth.chain_id
        if service_blockchain is not None
        else None
    )
    if chain_id == 31337:
        reseau = "Hardhat local (chain ID 31337)"
    elif chain_id == 11155111:
        reseau = "Sepolia (chain ID 11155111)"
    elif chain_id is not None:
        reseau = f"Ethereum (chain ID {chain_id})"
    else:
        reseau = None
    return {
        "api_connectee": True,
        "modele_charge": model is not None,
        "modele_ethereum_charge": (
            ETHEREUM_MODEL_PATH.is_file()
            and ETHEREUM_SHAP_BACKGROUND_PATH.is_file()
        ),
        "blockchain_connectee": service_blockchain is not None,
        "reseau": reseau,
        "chain_id": chain_id,
        "adresse_contrat": (
            service_blockchain.contract.address
            if service_blockchain is not None
            else None
        ),
        "nombre_alertes": (
            service_blockchain.contract.functions.getAlertCount().call()
            if service_blockchain is not None
            else 0
        ),
        "erreur_blockchain": blockchain_error,
        "erreur_modele_ethereum": ethereum_analyzer_error,
        "analyseur_ethereum_disponible": analyseur_ethereum_disponible,
        "ethereum_provider_configured": bool(os.getenv("ETHERSCAN_API_KEY")),
    }


@app.get("/api/history")
def historique_analyses(
    query: str | None = Query(default=None, max_length=200),
    classe_predite: int | None = Query(default=None, ge=0, le=1),
    blockchain_enregistre: bool | None = None,
    type_analyse: str | None = Query(default=None, pattern=r"^(bitcoin|ethereum)$"),
    limite: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return list_analyses(
        HISTORY_DB_PATH,
        limit=limite,
        offset=offset,
        query=query,
        predicted_class=classe_predite,
        blockchain_recorded=blockchain_enregistre,
        analysis_type=type_analyse,
    )


@app.get("/api/analytics")
def statistiques_analyses():
    summary = get_history_summary(HISTORY_DB_PATH)
    # Ajouter des statistiques séparées pour Bitcoin et Ethereum
    summary["analyses_bitcoin"] = summary.get("analyses_bitcoin", 0)
    summary["analyses_ethereum"] = summary.get("analyses_ethereum", 0)
    return summary


@app.get("/api/ethereum/metrics")
def ethereum_metrics():
    """Retourne les métriques du modèle Ethereum depuis le fichier JSON."""
    metrics_path = BASE_DIR / "reports" / "ethereum_model_metrics.json"
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Métriques Ethereum non disponibles")

    import json
    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/ethereum/shap-importance")
def ethereum_shap_importance():
    """Retourne l'importance des caractéristiques SHAP depuis le fichier CSV."""
    shap_path = BASE_DIR / "reports" / "ethereum_shap_global_importance.csv"
    if not shap_path.exists():
        raise HTTPException(status_code=404, detail="Données SHAP non disponibles")

    import pandas as pd
    df = pd.read_csv(shap_path)
    # Convertir en liste de dictionnaires
    return df.to_dict(orient="records")


@app.get("/health")
def etat_api():
    service_blockchain = obtenir_blockchain()
    return {
        "message": "API opérationnelle",
        "caracteristiques_attendues": 166,
        "modele_ethereum_disponible": (
            obtenir_analyseur_ethereum() is not None
        ),
        "blockchain_connectee": service_blockchain is not None,
    }


@app.get("/api/dataset/sample")
def exemple_dataset():
    if not FEATURES_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Le fichier elliptic_txs_features.csv est introuvable. "
                "Chargez ce fichier dans le formulaire d'analyse."
            ),
        )

    donnees = pd.read_csv(FEATURES_PATH, header=None, nrows=1)
    if donnees.empty:
        raise HTTPException(
            status_code=422,
            detail="Le fichier Elliptic ne contient aucune transaction.",
        )

    ligne = donnees.iloc[0]
    if len(ligne) != 167:
        raise HTTPException(
            status_code=422,
            detail=(
                "Le fichier d'exemple doit contenir un identifiant et "
                "166 caractéristiques numériques."
            ),
        )

    try:
        transaction_id = str(int(ligne.iloc[0]))
        caracteristiques = [float(valeur) for valeur in ligne.iloc[1:]]
    except (TypeError, ValueError, OverflowError) as erreur:
        raise HTTPException(
            status_code=422,
            detail="La première ligne du fichier Elliptic est invalide.",
        ) from erreur

    if not all(pd.notna(valeur) for valeur in caracteristiques):
        raise HTTPException(
            status_code=422,
            detail="La première ligne contient une caractéristique manquante.",
        )

    return {
        "transaction_id": transaction_id,
        "features": caracteristiques,
        "nombre_caracteristiques": len(caracteristiques),
        "fichier": FEATURES_PATH.name,
    }


@app.get("/api/alerts")
def lister_alertes(
    limite: int = Query(default=100, ge=1, le=500),
):
    service_blockchain = obtenir_blockchain()
    if service_blockchain is None:
        return {
            "alertes": [],
            "nombre_total": 0,
            "erreur": blockchain_error,
        }

    nombre_total = service_blockchain.contract.functions.getAlertCount().call()
    alertes = service_blockchain.lister_alertes(limite)
    return {
        "alertes": alertes,
        "nombre_total": nombre_total,
        "erreur": None,
    }


class Transaction(BaseModel):
    features: list[float] = Field(
        min_length=166,
        max_length=166,
    )
    transaction_id: str | None = Field(default=None, min_length=1, max_length=128)


class EthereumAddressRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    autoriser_enregistrement_alerte: bool = False


@app.get("/")
def accueil():
    return FileResponse(FRONTEND_PATH / "index.html")


@app.post("/predict")
def predire(transaction: Transaction):
    global bitcoin_explainer

    if not all(math.isfinite(value) for value in transaction.features):
        raise HTTPException(
            status_code=422,
            detail="Chaque caractéristique doit être un nombre fini.",
        )

    donnees = pd.DataFrame(
        [transaction.features],
        columns=model.feature_names_in_,
    )

    prediction = int(model.predict(donnees)[0])
    probabilites = model.predict_proba(donnees)[0]
    score_risque = round(float(probabilites[1]) * 100)

    try:
        if bitcoin_explainer is None:
            import shap

            bitcoin_explainer = shap.TreeExplainer(
                model,
                feature_perturbation="tree_path_dependent",
            )
        valeurs_shap = bitcoin_explainer.shap_values(donnees)
    except (ImportError, ValueError, RuntimeError) as erreur:
        raise HTTPException(
            status_code=503,
            detail="Impossible de calculer les explications SHAP Bitcoin.",
        ) from erreur

    contributions = valeurs_shap[0]
    if len(contributions) != len(model.feature_names_in_):
        raise HTTPException(
            status_code=503,
            detail="Le résultat SHAP Bitcoin ne correspond pas aux caractéristiques du modèle.",
        )
    explanations = sorted(
        (
            {
                "feature": feature,
                "value": float(transaction.features[index]),
                "contribution": float(contribution),
            }
            for index, (feature, contribution) in enumerate(
                zip(model.feature_names_in_, contributions, strict=True)
            )
        ),
        key=lambda item: abs(item["contribution"]),
        reverse=True,
    )
    if not all(
        math.isfinite(item["contribution"]) and math.isfinite(item["value"])
        for item in explanations
    ):
        raise HTTPException(
            status_code=503,
            detail="Les explications SHAP Bitcoin contiennent une valeur non finie.",
        )

    resultat = {
        "prediction": "risque détecté" if prediction == 1 else "risque non détecté",
        "classe_predite": prediction,
        "probabilite_licite": round(float(probabilites[0]), 4),
        "probabilite_illicite": round(float(probabilites[1]), 4),
        "score_risque_sur_100": score_risque,
        "explications_shap": explanations[:8],
        "explication_shap_unite": "log-odds",
        "avertissement": (
            "La classe positive indique une correspondance avec les étiquettes "
            "du corpus Elliptic. Ce score expérimental n'est pas une preuve de "
            "fraude ou de blanchiment. Les contributions SHAP sont exprimées "
            "en log-odds et ne sont pas causales."
        ),
        "blockchain_enregistre": False,
    }

    hash_transaction_blockchain = None
    erreur_blockchain = None
    if transaction.transaction_id is not None:
        service_blockchain = obtenir_blockchain()
        if service_blockchain is None:
            erreur_blockchain = (
                "Blockchain indisponible : " + str(blockchain_error)
            )
        else:
            try:
                tx_hash = service_blockchain.enregistrer_alerte(
                    transaction.transaction_id,
                    score_risque,
                    prediction == 1,
                )
                resultat["blockchain_enregistre"] = True
                resultat["hash_transaction_blockchain"] = tx_hash
                hash_transaction_blockchain = tx_hash
            except Exception as erreur:
                resultat["erreur_blockchain"] = _erreur_sans_secrets(erreur)
                erreur_blockchain = resultat["erreur_blockchain"]

    analysis_id = save_analysis(
        HISTORY_DB_PATH,
        transaction.transaction_id,
        prediction,
        float(probabilites[0]),
        float(probabilites[1]),
        score_risque,
        bool(resultat["blockchain_enregistre"]),
        hash_transaction_blockchain,
        erreur_blockchain,
        analysis_type="bitcoin",
    )
    resultat["id_analyse"] = analysis_id

    return resultat


@app.post("/api/ethereum/analyze")
def analyser_adresse_ethereum(request: EthereumAddressRequest):
    analyseur = obtenir_analyseur_ethereum()
    if analyseur is None:
        raise HTTPException(
            status_code=503,
            detail=ethereum_analyzer_error or "Le modèle Ethereum est indisponible.",
        )

    fournisseur = obtenir_fournisseur_ethereum()
    if fournisseur is None:
        raise HTTPException(
            status_code=503,
            detail=ethereum_provider_error
            or "Le fournisseur Ethereum est indisponible.",
        )

    address = request.address.lower()
    try:
        (
            transactions,
            internal_transactions,
            token_transfers,
        ) = fournisseur.get_address_history(address)
        counterparties = {
            str(transaction.get(field, "")).lower()
            for transaction in (
                *transactions,
                *internal_transactions,
                *token_transfers,
            )
            for field in ("from", "to")
            if transaction.get(field)
        }
        counterparties.discard(address)
        contract_flags = fournisseur.contract_flags(
            [address, *counterparties]
        )
        if address not in contract_flags:
            raise EthereumProviderError(
                "The RPC did not return the analyzed address contract type."
            )
        features = extract_live_features(
            address,
            transactions,
            internal_transactions,
            token_transfers,
            is_contract=contract_flags[address],
            is_contract_address=lambda peer: contract_flags[peer.lower()],
        )
        if not any(
            value != 0
            for name, value in features.items()
            if name != "is_contract"
        ):
            raise ValueError(
                "Aucune activité transactionnelle exploitable n'a été trouvée "
                "pour cette adresse ; le modèle ne peut pas produire un score fiable."
            )
        prediction = analyseur.analyze(features)
    except EthereumFeatureDataError as erreur:
        raise HTTPException(status_code=502, detail=str(erreur)) from erreur
    except ValueError as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except EthereumProviderError as erreur:
        raise HTTPException(status_code=502, detail=str(erreur)) from erreur

    blockchain_recorded = False
    blockchain_hash = None
    blockchain_failure = None
    if (
        prediction["classe_predite"] == 1
        and request.autoriser_enregistrement_alerte
    ):
        service_blockchain = obtenir_blockchain()
        if service_blockchain is None:
            blockchain_failure = (
                "Blockchain indisponible : " + str(blockchain_error)
            )
        else:
            try:
                blockchain_hash = service_blockchain.enregistrer_alerte(
                    address,
                    prediction["score_risque_sur_100"],
                    True,
                )
                blockchain_recorded = True
            except Exception as erreur:
                blockchain_failure = _erreur_sans_secrets(erreur)

    analysis_id = save_analysis(
        HISTORY_DB_PATH,
        address,
        prediction["classe_predite"],
        prediction["probabilite_non_scam"],
        prediction["probabilite_scam"],
        prediction["score_risque_sur_100"],
        blockchain_recorded,
        blockchain_hash,
        blockchain_failure,
        analysis_type="ethereum",
    )
    return {
        "adresse": address,
        **prediction,
        "id_analyse": analysis_id,
        "blockchain_enregistre": blockchain_recorded,
        "hash_transaction_blockchain": blockchain_hash,
        "erreur_blockchain": blockchain_failure,
        "alerte_non_enregistree_raison": (
            "autorisation_absente"
            if prediction["classe_predite"] == 1
            and not request.autoriser_enregistrement_alerte
            else None
        ),
        "source_features": {
            "transactions_normales": len(transactions),
            "transactions_internes": len(internal_transactions),
            "transferts_erc20": len(token_transfers),
            "reseau": "Ethereum mainnet (chain ID 1)",
            "fenetre": "historique complet disponible via Etherscan",
        },
        "avertissement": (
            "Score expérimental pour des adresses étiquetées scam dans le corpus ; "
            "ce résultat n'est ni une preuve de fraude ni une détection spécifique "
            "du blanchiment."
        ),
    }


@app.post("/api/ethereum/demo")
def analyser_exemple_ethereum():
    service_blockchain = obtenir_blockchain()
    if (
        service_blockchain is None
        or service_blockchain.w3.eth.chain_id != 31337
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "La démo Ethereum est réservée au réseau Hardhat local "
                "(chain ID 31337)."
            ),
        )

    analyseur = obtenir_analyseur_ethereum()
    if analyseur is None:
        raise HTTPException(
            status_code=503,
            detail=ethereum_analyzer_error or "Le modèle Ethereum est indisponible.",
        )

    features, counts = build_demo_features()
    prediction = analyseur.analyze(features)
    return {
        **prediction,
        "id_analyse": None,
        "blockchain_enregistre": False,
        "hash_transaction_blockchain": None,
        "erreur_blockchain": None,
        "source_features": {
            **counts,
            "fenetre": "exemple synthétique local — aucune donnée mainnet",
        },
        "mode": "simulation_locale",
        "avertissement": (
            "Démo locale sur un historique synthétique : ce résultat sert à "
            "tester le modèle et SHAP, pas à analyser une adresse réelle. "
            "Aucune donnée n'est enregistrée dans l'historique ou sur la "
            "blockchain. Un score n'est pas une preuve de fraude."
        ),
    }


app.mount("/ui", StaticFiles(directory=FRONTEND_PATH, html=True), name="ui")
