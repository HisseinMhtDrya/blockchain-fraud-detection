# Rapport de Livraison Académique

**Date :** 31 octobre 2026
**Projet :** Détection de fraude blockchain (Bitcoin + Ethereum)
**Version :** 1.1.0

---

## Résumé Exécutif

Ce projet implémente un système de détection de fraude blockchain combinant :
- Un classifieur XGBoost pour le dataset Elliptic Bitcoin (166 caractéristiques)
- Un classifieur XGBoost pour les adresses Ethereum (26 caractéristiques + SHAP)
- Un smart contract Ethereum pour l'enregistrement d'alertes on-chain
- Une interface web FastAPI avec tableau de bord interactif

---

## 1. Installation et Démarrage

### Prérequis

- Windows 10/11
- Node.js 18+
- Python 3.11+
- Git

### Installation

```powershell
# Cloner le dépôt (si nécessaire)
git clone <repository-url>
cd blockchain-fraud-detection

# Installer les dépendances Python
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-app.txt

# Installer les dépendances Node
npm install
```

### Démarrage rapide (local)

```powershell
npm run start:local
```

L'application démarre automatiquement :
- Nœud Hardhat local (chain ID 31337)
- Déploiement du contrat TransactionAlerts
- API FastAPI sur http://127.0.0.1:8000
- Interface web sur http://127.0.0.1:8000/ui/

### Pour l'analyse Ethereum live

Voir `CONFIGURATION_GUIDE.md` pour la configuration sécurisée des clés Etherscan et RPC.

---

## 2. Architecture Technique

### Composants principaux

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| API Backend | FastAPI | Endpoints REST, orchestration |
| Modèle Bitcoin | XGBoost (joblib) | Classification transactions Elliptic |
| Modèle Ethereum | XGBoost + SHAP | Classification adresses Ethereum |
| Smart Contract | Solidity 0.8.34 | Enregistrement alertes on-chain |
| Blockchain Local | Hardhat | Testnet local pour développement |
| Frontend | HTML/JS/Chart.js | Tableau de bord interactif |
| Provider Ethereum | Etherscan API | Récupération historique live |

### Flux de données

1. **Bitcoin (Elliptic)**
   - Chargement CSV → 166 caractéristiques → XGBoost → Prédiction → (optionnel) Smart Contract

2. **Ethereum (Live)**
   - Adresse Ethereum → Etherscan API → 26 caractéristiques → XGBoost → SHAP → Prédiction → (si scam) Smart Contract

---

## 3. Résultats Scientifiques

### Modèle Bitcoin (Elliptic)

- **Caractéristiques :** 166 (anonymisées)
- **Classes :** Illicite (1) vs Licite (0)
- **Performance :** Non mesurée dans cette phase (focus sur Ethereum)

### Modèle Ethereum

| Métrique | Train | Validation | Test |
|----------|-------|------------|------|
| Accuracy | 0.9354 | 0.9019 | 0.8991 |
| Précision (scam) | 0.9213 | 0.8759 | 0.8742 |
| Rappel (scam) | 0.8916 | 0.8414 | 0.8340 |
| F1 (scam) | 0.9062 | 0.8583 | 0.8536 |
| ROC-AUC | 0.9830 | 0.9626 | 0.9605 |
| PR-AUC | 0.9707 | 0.9410 | 0.9389 |

**Corpus :**
- Adresses totales : 114,739 (après déduplication)
- Période : août 2015 à août 2025
- Source : Hugging Face (fesevu/ethereum_fraud_dataset_by_activity)
- Licence : CC BY 4.0 (déclarée)

**Caractéristiques (26) :**
- Transactions natives (envoyées/reçues/échouées)
- Volumes ETH (envoyés/reçus/flux net)
- Frais et gas
- Transferts ERC-20 (nombre, tokens uniques)
- Transactions internes
- Contreparties uniques (total, contrats, EOA)
- Durée d'activité, rafales, sessions

**Importances SHAP (top 5) :**
1. `tx_fee_eth_sum` : 0.135
2. `sessions_cnt` : 0.080
3. `internal_in_value_eth_sum` : 0.077
4. `internal_out_value_eth_sum` : 0.065
5. `erc20_unique_tokens_recv` : 0.061

---

## 4. Smart Contract

### Contrat TransactionAlerts

**Adresse locale :** Déployée automatiquement sur Hardhat local
**Réseau test :** Sepolia (prêt pour déploiement, non déployé)

**Fonctionnalités :**
- Enregistrement d'alertes (transaction ID, score de risque, classification)
- Contrôle d'accès (owner + reporters autorisés)
- Transfert de propriété
- Événements pour traçabilité

**Contrôles de sécurité réalisés :**
- Pragma Solidity 0.8.34
- Protection reentrancy (modificateur `nonReentrant`)
- Validation des entrées (longueurs, scores, adresses)
- Contrôle d'accès par rôles (onlyOwner, onlyReporter)
- Tests Hardhat des permissions, rôles, entrées et événements
- Compilation du contrat avec le profil de production

Slither n'est pas installé dans cet environnement et n'a pas été exécuté ;
aucune conclusion de son analyse n'est revendiquée.

**Sepolia :** non déployé. Aucun coût, adresse ou événement Sepolia n'est
revendiqué. Le déploiement nécessite un RPC, la clé propriétaire et des ETH de
test ; l'autorisation du reporter nécessite une transaction propriétaire.

---

## 5. Tests et Validation

### Tests unitaires

**Hardhat (Solidity + TypeScript) :**
```
9/9 passing
- 3 tests Solidity (Counter)
- 6 tests TypeScript (TransactionAlerts)
```

**Python :**
```
34 tests exécutés avec :
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Le parcours local a également été vérifié sur Hardhat chain ID 31337 :
analyse d'un échantillon réel Elliptic, 8 contributions SHAP, reçu de
transaction confirmé avec l'événement `AlertRecorded`, alerte visible depuis
l'API, et analyse persistée dans SQLite. Cette validation concerne uniquement
la chaîne locale ; l'entrée de démonstration a été ajoutée à l'historique local.

### Analyse de sécurité

**Slither :** non installé dans l'environnement et non exécuté. Aucune
conclusion de sécurité Slither n'est revendiquée. Le contrôle automatisé
effectivement réalisé est la compilation de production et les tests Hardhat
des rôles, permissions, validations d'entrée et événements.

### Tests réels

**Statut :**
- ✅ Tests unitaires : Passés
- ❌ Test API Ethereum live : **BLOQUÉ** (clés non fournies)
- ❌ Déploiement Sepolia : **BLOQUÉ** (RPC et clé propriétaire absents du keystore ; aucune autorisation de déploiement donnée)
- ❌ Vérification explorateur : **BLOQUÉ** (pas de déploiement)
- ❌ Test bout en bout on-chain : **BLOQUÉ** (pas de déploiement)

**Ce qui bloque les tests réels :**
1. `ETHERSCAN_API_KEY` non configurée
2. `ETHEREUM_RPC_URL` (mainnet) non configuré
3. `SEPOLIA_RPC_URL` non configurée
4. `SEPOLIA_PRIVATE_KEY` absente du keystore Hardhat
5. Aucun déploiement ni enregistrement de reporter explicitement autorisé

Le script `scripts/test-ethereum-live.ps1` est préparé pour lancer le parcours
Etherscan → RPC mainnet → caractéristiques → XGBoost/SHAP avec autorisation
d'alerte forcée à `false`. Sa syntaxe a été vérifiée ; il n'a pas été exécuté
sur une adresse réelle faute d'accès configuré.

### Dépendances npm

`npm audit` a signalé 12 entrées de sévérité élevée et aucune critique. Ce ne
sont pas 12 causes indépendantes : toutes remontent à l'avis Zod
[GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5),
qui concerne Zod `<4.6.6` et peut entraîner une exhaustion mémoire sur des
collections contraintes surdimensionnées. Les dépendances directement
concernées dans l'arbre sont Hardhat, `@nomicfoundation/hardhat-toolbox-viem`,
`@nomicfoundation/hardhat-ignition` et `@nomicfoundation/hardhat-verify` ;
les entrées restantes sont des dépendances transitoires de ces outils.

`npm audit --omit=dev` rapporte zéro vulnérabilité : les alertes touchent
l'outillage de développement/déploiement, et non les dépendances de production
déclarées par ce dépôt. La correction automatique proposée rétrograde Hardhat
3 vers 2.29.1 et le toolbox viem vers une autre version majeure ; cela casserait
la configuration Hardhat 3 actuelle. Le Hardhat 3 disponible déclare encore
une plage Zod 3 vulnérable. Aucun override forcé de Zod 4 ni rétrogradage
majeur n'a été appliqué faute de compatibilité démontrée. Revoir cet avis après
publication de versions Hardhat 3/toolbox compatibles, puis relancer toute la
suite avant mise à niveau.

### État des accès lors de la finalisation

Le 31 octobre 2026, les contrôles de présence (sans lire ni afficher les
valeurs) ont confirmé l'absence des variables `ETHERSCAN_API_KEY`,
`ETHEREUM_RPC_URL`, `SEPOLIA_RPC_URL` et des variables reporter. `npx hardhat
keystore list` a indiqué qu'aucun keystore de production n'existe. Le script
live s'arrête sur ce contrôle avant de demander une adresse. L'API a été
démarrée localement et annonce Hardhat local, pas Sepolia.

---

## 6. Limites Scientifiques

### Corpus Ethereum

1. **Provenance des labels** : Sources multiples (Etherscan, Forta, CryptoScamDB) sans date de connaissance fiable
2. **Séparation des données** : Par adresse, pas temporelle (évaluation prospective non garantie)
3. **Classe négative** : Sélection d'adresses "non étiquetées comme scam", pas preuve d'innocuité
4. **Déséquilibre types** : Contrats vs EOA différents entre classes

### Dérive temporelle

- Caractéristiques d'entraînement arrêtées en août 2025
- Inférence sur historique actuel peut subir dérive
- Types de contrats live calculés depuis état RPC actuel (vs historique)

### Équivalence sémantique

- Définitions historiques des colonnes incomplètes
- Agrégats BigQuery vs reconstitution Etherscan non identiques
- Différence contractuelle entre entraînement et inférence

### GNN

- **Non implémenté** : Artifact d'arêtes ~20.1 Gio
- Nécessite environnement GPU/graph dédié
- Nécessite split des arêtes sans fuite temporelle

### Interprétation

- Scores expérimentaux, pas preuves juridiques
- SHAP = contributions relatives, pas causalité
- Ne détecte pas spécifiquement le blanchiment
- Classe "scam" = étiquetée dans corpus, pas fraude prouvée

---

## 7. Utilisation

### Interface web

**Onglets :**
1. **Transactions** : Analyse Bitcoin (CSV) et Ethereum (adresse)
2. **Alertes** : Vue des alertes enregistrées on-chain
3. **Analyses** : Statistiques et graphiques
4. **Configuration** : État des services connectés

### API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/predict` | POST | Prédire transaction Bitcoin |
| `/api/ethereum/analyze` | POST | Analyser adresse Ethereum |
| `/api/ethereum/demo` | POST | Démo Ethereum synthétique sur Hardhat local (sans historique ni transaction) |
| `/api/history` | GET | Historique des analyses |
| `/api/analytics` | GET | Statistiques agrégées |
| `/api/alerts` | GET | Alertes on-chain |
| `/api/status` | GET | État des services |

### Exemple d'utilisation (Bitcoin)

1. Cliquer "Charger l'exemple Elliptic"
2. Vérifier "166 / 166" caractéristiques chargées
3. Cliquer "Analyser la transaction"
4. Voir score, probabilités et avertissement

### Exemple d'utilisation (Ethereum)

1. Démarrer `npm run start:local`
2. Dans Transactions, cliquer "Tester avec l'exemple local"
3. Vérifier le score et les explications SHAP, marqués comme simulation
4. Pour une analyse réelle, configurer `ETHERSCAN_API_KEY` et `ETHEREUM_RPC_URL`, puis saisir une adresse mainnet
5. L'analyse réelle n'envoie aucune transaction par défaut ; l'autorisation doit être cochée explicitement

---

## 8. Déploiement Production

### Prérequis

- Clé Etherscan API (gratuit)
- RPC Ethereum mainnet (Alchemy, Infura, etc.)
- RPC Sepolia + ETH de test pour contrat
- Clé privée séparée pour signataire API

### Étapes

1. **Configuration** : Suivre `CONFIGURATION_GUIDE.md`
2. **Vérification en lecture seule** (après configuration du keystore) :
   ```powershell
   npx hardhat --network sepolia run .\scripts\check-sepolia-config.ts
   ```
3. **Déploiement Sepolia** — uniquement après autorisation explicite :
   ```powershell
   npx hardhat --build-profile production --network sepolia run .\ignition\deploy-transaction-alerts.ts
   ```
4. **Vérification de la source sur Etherscan** :
   ```powershell
   npx hardhat verify etherscan --network sepolia <ADRESSE_CONTRAT>
   ```
5. **Autorisation du reporter** — transaction distincte, autorisation explicite requise :
   ```powershell
   npx hardhat --network sepolia run .\scripts\register-alert-reporter.ts
   ```
6. **Configuration API** : suivre les étapes du guide, qui demandent les
   secrets localement et distinguent le RPC Sepolia d'écriture du RPC mainnet
   de lecture. Cochez l'autorisation de l'interface uniquement pour une alerte
   que vous souhaitez publier sur Sepolia.

### Sécurité

- ✅ Keystore chiffré Hardhat
- ✅ Variables d'environnement temporaires
- ✅ Séparation clés déployeur/signataire
- ✅ Contrôle d'accès par rôles
- ❌ Jamais de clés en clair dans le code

---

## 9. Documentation

### Fichiers techniques

- `README.md` : Guide d'utilisation principal
- `CONFIGURATION_GUIDE.md` : Configuration sécurisée des clés
- `reports/ethereum_model_training.md` : Résultats modèle Ethereum
- `reports/ethereum_dataset_audit.md` : Audit du corpus
- `reports/ethereum_feature_contract.md` : Contrat caractéristiques
- `reports/ethereum_model_metrics.json` : Métriques détaillées

### Code source

- `api.py` : API FastAPI
- `ethereum_features.py` : Extraction caractéristiques
- `etherscan_provider.py` : Provider Etherscan
- `ethereum_analyzer.py` : Analyseur XGBoost + SHAP
- `contracts/TransactionAlerts.sol` : Smart contract
- `frontend/index.html` : Interface web

---

## 10. Bilan Final

### Terminé ✅

- Architecture complète (Bitcoin + Ethereum)
- Modèle XGBoost Ethereum entraîné et évalué
- Contrat `TransactionAlerts` compilé en profil production et couvert par des tests de permissions
- Interface web fonctionnelle
- Parcours local Bitcoin testé de bout en bout : API, SHAP, reçu/événement Hardhat et persistance SQLite
- Script de test mainnet en lecture seule préparé, sans transaction, qui affiche les contributions SHAP
- Plugin Hardhat Etherscan configuré avec `ETHERSCAN_API_KEY` et profil de production
- Interface distinguant la simulation synthétique de l'analyse mainnet et affichant le réseau cible des alertes
- Statistiques et filtres d'historique séparés par blockchain
- Documentation technique complète
- Guide configuration sécurisée

### Testé réellement ✅

- `npm test` : 34 tests Python et 9 tests Hardhat réussis
- `npm run build:production` : compilation réussie avec Solidity 0.8.34
- `npm run typecheck` : réussi
- Tâche `hardhat verify etherscan` disponible ; aucune vérification réelle sans contrat Sepolia déployé
- Syntaxe PowerShell du script `scripts/test-ethereum-live.ps1` validée ; l'appel réel reste bloqué par l'absence des accès mainnet
- Parcours local sur Hardhat chain ID 31337 : analyse Elliptic, 8 explications SHAP, reçu/événement confirmé et historique SQLite vérifié
- Interface locale : tableau de bord, statistiques, métriques Ethereum, importances SHAP et filtre d'historique testés
- API, métriques Ethereum, endpoint SHAP et historique répondent en local

### Non testé ❌ (BLOQUÉ)

- **API Ethereum mainnet live** : accès Etherscan et RPC mainnet non configurés
- **Déploiement Sepolia** : RPC et clé propriétaire absents du keystore Hardhat ; aucune transaction externe n'a été envoyée
- **Vérification explorateur et parcours reporter Sepolia** : nécessitent un déploiement autorisé
- **Analyse Slither** : outil absent de l'environnement ; aucun résultat Slither n'est revendiqué
- **Métriques de test Bitcoin** : non disponibles dans les artefacts actuels ; aucune performance n'est inventée

### Pour débloquer les tests réels

Configurer localement, sans transmettre de clé privée dans une conversation :
1. Clé API Etherscan et URL RPC Ethereum mainnet pour l'analyse live
2. URL RPC Sepolia, clé propriétaire stockée dans le keystore Hardhat et ETH de test pour le déploiement autorisé
3. Clé de reporter distincte, ETH de test et autorisation par le propriétaire pour écrire des alertes depuis l'API

Voir `CONFIGURATION_GUIDE.md` pour les instructions détaillées.

---

## 11. Perspectives

### Améliorations possibles

1. **Validation temporelle** : Obtenir des labels datés pour évaluation prospective
2. **GNN** : Implémenter avec sous-échantillonnage d'arêtes
3. **Multi-chain** : Étendre à d'autres blockchains (BSC, Polygon)
4. **Monitoring** : Dashboard temps réel des alertes
5. **Explainability** : Améliorer les explications SHAP avec LIME

### Publications potentielles

- "Address-level fraud detection on Ethereum with behavioral features"
- "Comparison of tabular vs graph-based methods for blockchain fraud detection"
- "Real-time fraud scoring system with on-chain alert registry"

---

## Contact et Support

Pour questions ou problèmes :
- Vérifier d'abord `CONFIGURATION_GUIDE.md`
- Consulter `README.md`
- Vérifier les logs dans le terminal Hardhat et API

---

**Fin du rapport de livraison**
