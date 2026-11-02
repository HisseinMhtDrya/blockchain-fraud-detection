# 🛡️ Détection de Fraude et de Blanchiment sur les Transactions Blockchain

Système intelligent de détection d'anomalies et de fraudes sur les transactions blockchain (Bitcoin/Elliptic et Ethereum) combinant un modèle de Machine Learning (**XGBoost + SHAP**), une API **FastAPI**, une interface Web interactive et un registre d'alertes sécurisé sur **Smart Contract Solidity**.

---

## 📊 Aperçu de l'Interface

Voici les différentes vues de l'application :

### 1. Tableau de Bord
![Tableau de bord](tableau_de_bord.png)
*Vue d'ensemble en temps réel de l'état de l'API, du modèle de Machine Learning et du contrat intelligent.*

### 2. Historique des Analyses
![Historique](historique.png)
*Consultation, filtrage et recherche dans l'historique local des transactions analysées (`sqlite3`).*

### 3. Analyse d'une Transaction
![Transaction Analyse](transaction_analyse.png)
*Interface d'analyse détaillée des caractéristiques, des scores de risque XGBoost et des explications SHAP.*

### 4. Paramètres & Configuration
![Paramètres](parametres.png)
*Gestion des connexions RPC, clés Etherscan et configuration du réseau (Hardhat local / Sepolia).*

---

## ⚙️ Installation des Dépendances

Depuis la racine du dépôt, avec **Python 3.11** et **Node.js 18** (ou plus récent), exécutez dans un terminal PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
npm install
