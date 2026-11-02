#  Détection de Fraude et de Blanchiment sur les Transactions Blockchain

Système intelligent de détection d'anomalies et de fraudes sur les transactions blockchain (Bitcoin/Elliptic et Ethereum) combinant un modèle de Machine Learning (**XGBoost + SHAP**), une API **FastAPI**, une interface Web interactive et un registre d'alertes sécurisé sur **Smart Contract Solidity**.

---

## 📊 Aperçu de l'Interface

Voici les différentes vues de l'application :

### 1. Tableau de Bord
<img width="2915" height="1702" alt="Capture d&#39;écran 2026-11-02 155733" src="https://github.com/user-attachments/assets/f04b9d19-be8d-4ee7-9d1e-fa7ef5397d9d" />
*Vue d'ensemble en temps réel de l'état de l'API, du modèle de Machine Learning et du contrat intelligent.*

### 2. Historique des Analyses
<img width="3000" height="1679" alt="Capture d&#39;écran 2026-11-02 155833" src="https://github.com/user-attachments/assets/3ba1a97f-a884-4fc5-aabf-a253fa393085" />

*Consultation, filtrage et recherche dans l'historique local des transactions analysées (`sqlite3`).*

### 3. Analyse d'une Transaction
<img width="3000" height="1679" alt="Capture d&#39;écran 2026-11-02 155833" src="https://github.com/user-attachments/assets/e4e93c61-b5e0-4534-80c6-ed2240a6c334" />

*Interface d'analyse détaillée des caractéristiques, des scores de risque XGBoost et des explications SHAP.*

### 4. Paramètres & Configuration
<img width="3000" height="1690" alt="Capture d&#39;écran 2026-11-02 155818" src="https://github.com/user-attachments/assets/c651c682-bfbf-4d0d-b37d-d2fd6ae7444c" />

*Gestion des connexions RPC, clés Etherscan et configuration du réseau (Hardhat local / Sepolia).*

---

## ⚙️ Installation des Dépendances

Depuis la racine du dépôt, avec **Python 3.11** et **Node.js 18** (ou plus récent), exécutez dans un terminal PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
npm install
