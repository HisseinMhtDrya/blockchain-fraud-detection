# Détection de fraude blockchain

L'API FastAPI enregistre sur `TransactionAlerts` les prédictions envoyées avec
un `transaction_id`.

## Installation des dépendances de l'application

Depuis la racine du dépôt, avec Python 3.11 et Node.js 18 ou plus récent :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
npm install
```

Le fichier `requirements-app.txt` déclare les dépendances nécessaires au
backend, aux modèles et aux tests API. `requirements-ethereum-data.txt` ajoute
les dépendances de préparation et de réentraînement du modèle Ethereum ; elles
ne sont pas nécessaires pour lancer l'application avec les artifacts existants.

## Démarrage local en une commande (Windows)

Depuis la racine du projet, lancez :

```powershell
npm run start:local
```

Le lanceur démarre le nœud Hardhat en arrière-plan s'il n'est pas déjà actif,
attend une réponse JSON-RPC, déploie le contrat sur ce nœud et démarre ensuite
l'API. Gardez la fenêtre du serveur ouverte. Le tableau de bord est disponible
sur `http://127.0.0.1:8000` ou `http://127.0.0.1:8000/ui/`, et la documentation
de l'API sur `http://127.0.0.1:8000/docs`.

Le tableau de bord présente l'état réel de l'API, du modèle et du contrat. Il
permet d'analyser une transaction en fournissant ses 166 caractéristiques ou
en chargeant une ligne CSV, puis affiche les alertes réellement inscrites sur
la blockchain locale.

Dans **Transactions → Analyse d'une adresse Ethereum**, le bouton
**Tester avec l'exemple local** vérifie immédiatement le modèle XGBoost et ses
explications SHAP avec un historique synthétique. Il est disponible uniquement
avec le nœud Hardhat local et le modèle Ethereum chargé. Cette démo n'appelle
ni Etherscan ni un RPC mainnet, ne crée aucune transaction et n'ajoute rien à
l'historique. Elle est distincte de l'analyse d'une adresse réelle.

Dans l'onglet **Transactions**, le bouton **Charger l'exemple Elliptic**
remplit automatiquement l'identifiant et les 166 caractéristiques de la
première ligne de `elliptic_txs_features.csv`. Il suffit ensuite de cliquer
sur **Analyser la transaction**. La zone des 166 valeurs est masquée dans
« Afficher ou coller les 166 valeurs » ; elle est réservée à la saisie avancée.
Le chargement manuel d'un CSV ne lit que sa première ligne, pas tout le fichier
de plusieurs centaines de mégaoctets.

Chaque prédiction est également ajoutée à `data/analysis_history.sqlite3`,
même si aucun identifiant n'est fourni ou si l'inscription sur la blockchain
échoue. Cet historique local survit au redémarrage du nœud Hardhat et peut
être recherché et filtré dans l'onglet **Transactions**. Les caractéristiques
brutes ne sont pas conservées.

Les routes `GET /api/history`, `GET /api/analytics` et `GET /api/status`
fournissent respectivement l'historique paginé, les indicateurs agrégés et
l'état de connexion des services.

## Prototype Ethereum (XGBoost + SHAP)

Le modèle d'adresses Ethereum est séparé du classifieur Elliptic Bitcoin.
Pour préparer l'environnement et (re)produire le modèle depuis les artifacts
publics épinglés par SHA-256 :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ethereum-data.txt
.\.venv\Scripts\python.exe .\scripts\train_ethereum_xgboost.py
.\.venv\Scripts\python.exe -m unittest tests.test_ethereum_features tests.test_ethereum_dataset_preparation tests.test_ethereum_api tests.test_etherscan_provider tests.test_analysis_history -v
```

Le script place les artifacts et les partitions d'adresses sous `data\external\ethereum`
et `data\processed\ethereum-address-splits` (ignorés par Git), sauvegarde le
bundle sous `models\ethereum_xgboost`, et produit les métriques/explications
dans `reports\ethereum_model_metrics.json`, `reports\ethereum_model_training.md`
et `reports\ethereum_shap_global_importance.csv`.
`reports\ethereum_dataset_audit.md` décrit la provenance et les limites du corpus.
Le rapport académique structuré du projet est disponible dans
[`DELIVERY_REPORT.md`](./DELIVERY_REPORT.md) ; il distingue les résultats
mesurés, les limites et les exigences de déploiement restant à satisfaire.
Les caractéristiques sont agrégées par adresse depuis les agrégats mensuels
publiés ; l'absence de caractéristiques est remplie par zéro et sa couverture
est explicitement documentée. Le jeu étant sélectionné/équilibré et ses labels
sans date de connaissance, ces métriques ne mesurent ni la prévalence en
production ni une performance prospective.

Pour l'analyse live d'une adresse mainnet, configurez `ETHERSCAN_API_KEY` et
`ETHEREUM_RPC_URL` puis démarrez l'API dans le même terminal. Les étapes
complètes, le test réel en lecture seule et les variables séparées du reporter
Sepolia sont dans [`CONFIGURATION_GUIDE.md`](./CONFIGURATION_GUIDE.md).
`.\scripts\test-ethereum-live.ps1` appelle le vrai parcours Etherscan/RPC,
XGBoost et SHAP, avec enregistrement d'historique local mais sans transaction
on-chain. `npm run start:local` reste réservé au test Hardhat local.

`POST /api/ethereum/analyze` récupère les transactions natives, internes et
ERC-20 depuis Etherscan, calcule les 26 caractéristiques live et le drapeau de
contrat, puis renvoie le score et les contributions SHAP. Une alerte positive
n'est envoyée au contrat configuré que si la requête contient
`autoriser_enregistrement_alerte: true` ; par défaut, analyser n'envoie aucune
transaction. L'interface exige de cocher explicitement la case d'autorisation
avant l'écriture. Les transferts ERC-721/ERC-1155 ne sont pas utilisés comme
caractéristiques ERC-20. Les
requêtes à historique incomplet, une API indisponible ou un RPC autre que
mainnet sont refusés ; le projet ne bascule pas silencieusement vers des données
partielles. Les contributions SHAP ne sont pas causales, et l'analyse reste
expérimentale. Le détail des métriques mesurées est dans
`reports\ethereum_model_training.md`. Le contrat des colonnes, l'ordre, les
unités et les limites de comparabilité entre agrégats mensuels publiés et
reconstitution live est décrit dans
`reports\ethereum_feature_contract.md`. Le modèle contient 27 colonnes (26
caractéristiques comportementales plus `is_contract`) et applique
`sign(x) * log(1 + abs(x))` aux 27.

Les champs requis manquants ou malformés dans une réponse fournisseur sont
rejetés ; ils ne sont pas remplacés par des zéros. Une adresse sans activité
exploitable ne reçoit pas de score. L'ordre des caractéristiques et le
prétraitement sont partagés et contrôlés, mais l'équivalence sémantique complète
avec les agrégats d'entraînement n'est pas prouvée : la définition historique
des colonnes du dataset est incomplète et les types de contrat live viennent de
l'état actuel du RPC. Les scores ne sont pas une preuve de fraude, ni une
détection spécifique du blanchiment.

Le GNN n'a pas été entraîné : l'artifact d'arêtes complet publié pèse environ
20,1 Gio et nécessite un environnement de calcul/graph dédié ainsi qu'un split
des arêtes sans fuite. Le rapport d'entraînement détaille cette décision.

Les indicateurs du tableau de bord distinguent le nombre de prédictions du
nombre d'alertes on-chain. La part de prédictions illicites n'est pas une mesure
de précision : la précision, le rappel et le F1 nécessitent les vraies classes
d'un jeu de test étiqueté.

Pour utiliser d'autres ports :

```powershell
npm run start:local -- -ApiPort 8001 -RpcPort 8546
```

Le nœud Hardhat local est une blockchain de test. Ses contrats et données sont
perdus quand il s'arrête. Relancez `npm run start:local` après un arrêt : le
script redémarre le nœud si nécessaire et redéploie le contrat, puis configure
automatiquement l'adresse correspondante pour l'API. Il ne faut plus démarrer
le nœud, le déploiement et l'API dans trois terminaux distincts.

Les clés privées affichées par Hardhat sont publiques et réservées aux tests
locaux. Ne les utilisez jamais sur un réseau réel.

## Sécurité et Tests

### Tests unitaires

```powershell
npm test
```

```powershell
npm run build:production
npm run typecheck
```

### Analyse de sécurité

Slither n'est pas installé dans l'environnement de livraison ; aucune
conclusion de son analyse n'est revendiquée. Le contrôle vérifié ici comprend
la compilation Solidity en profil production et les tests automatisés de rôles,
permissions, entrées et événements. Exécutez Slither séparément avant une
publication si cet outil est disponible.

Le contrat utilise le pragma `^0.8.34`, limite l'écriture aux reporters
autorisés, valide les identifiants et scores et émet les événements d'alerte
et d'administration. Ces contrôles et les permissions sont couverts par les
tests Hardhat ; cela ne remplace pas un audit indépendant.

## Préparation Sepolia

Le contrat limite l'écriture à des reporters autorisés. Le déployeur est
initialement propriétaire et reporter ; seul le propriétaire peut gérer les
reporters ou transférer la propriété. Les fonctions de lecture restent
publiques.

1. Stockez l'URL RPC et la clé de déploiement dans le keystore chiffré Hardhat.
   Ne collez jamais de clé privée dans le dépôt, une issue ou une conversation :

   ```powershell
   npx hardhat keystore set SEPOLIA_RPC_URL
   npx hardhat keystore set SEPOLIA_PRIVATE_KEY
   ```

2. Vérifiez le réseau et le solde du déployeur (lecture seule, aucune transaction) :

   ```powershell
   npx hardhat --network sepolia run .\scripts\check-sepolia-config.ts
   ```

3. Après avoir explicitement autorisé l'envoi de la transaction de déploiement,
   déployez sur Sepolia depuis la racine du dépôt avec le profil de production :

   ```powershell
   npx hardhat --build-profile production --network sepolia run .\ignition\deploy-transaction-alerts.ts
   ```

   Notez l'adresse affichée. Après le déploiement, configurez l'API key
   Etherscan localement et vérifiez la source avec
   `npx hardhat verify etherscan --network sepolia <ADRESSE_CONTRAT>`.
   Consultez ensuite le contrat et ses transactions sur
   `https://sepolia.etherscan.io/address/<ADRESSE_CONTRAT>`.

4. Créez localement une clé séparée pour le signataire API et financez-la en
   Sepolia ETH de test. Configurez les valeurs uniquement dans l'environnement
   local du processus API, jamais dans le code ou le dépôt :

   ```powershell
   $env:BLOCKCHAIN_RPC_URL = Read-Host "Sepolia RPC URL"
   $env:BLOCKCHAIN_CONTRACT_ADDRESS = Read-Host "Deployed contract address"
   $secret = Read-Host "API reporter private key" -AsSecureString
   $env:BLOCKCHAIN_PRIVATE_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
   $env:BLOCKCHAIN_REPORTER_ADDRESS = Read-Host "API reporter public address"
   ```

5. Autorisez le signataire API depuis le compte propriétaire du contrat :

   ```powershell
   npx hardhat --network sepolia run .\scripts\register-alert-reporter.ts
   ```

   Cette commande envoie une transaction d'administration. Ne l'exécutez
   qu'après autorisation explicite ; vérifiez le reçu et l'événement
   `ReporterUpdated` sur Sepolia Etherscan.

6. Configurez séparément les accès mainnet Etherscan/RPC pour l'analyse live :
   `ETHERSCAN_API_KEY` et `ETHEREUM_RPC_URL` (chain ID 1). Le RPC d'analyse
   mainnet et le RPC Sepolia d'inscription d'alertes ont des usages distincts.

`BlockchainService` n'utilise la clé publique de test Hardhat que le
chain ID est 31337 **et** que l'URL RPC est loopback. La signature d'alertes
hors local est limitée à Sepolia (chain ID 11155111) et exige
`BLOCKCHAIN_PRIVATE_KEY` ainsi que l'autorisation reporter. Ces commandes
préparent le déploiement ; elles ne signifient pas qu'un contrat a été déployé
ou vérifié. Aucun déploiement Sepolia n'est déclaré tant qu'il n'a pas été
effectivement exécuté et contrôlé.

## Limites Scientifiques

- **Corpus Ethereum** : Les labels proviennent de sources multiples (Etherscan, Forta, CryptoScamDB) sans date de connaissance fiable. La séparation train/validation/test est par adresse, pas temporelle.
- **Dérive temporelle** : Les caractéristiques d'entraînement s'arrêtent en août 2025. L'inférence sur l'historique actuel peut subir une dérive.
- **Équivalence sémantique** : Les types de contrats live sont calculés depuis l'état RPC actuel, tandis que le corpus utilise des labels historiques. Cette différence limite la comparabilité.
- **GNN non implémenté** : L'artifact d'arêtes complet (~20,1 Gio) nécessite un environnement GPU/graph dédié. Aucun GNN n'est entraîné ni évalué.
- **Scores expérimentaux** : Les résultats ne sont pas une preuve de fraude ni une détection spécifique du blanchiment. Ils doivent être utilisés comme indicateurs de risque, pas comme preuves juridiques.
