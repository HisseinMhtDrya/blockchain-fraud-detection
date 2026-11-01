# Guide de Configuration Sécurisée

Ce guide explique comment configurer les accès nécessaires sans exposer vos clés privées dans le code ou le dépôt.

## 1. Configuration Etherscan et RPC Mainnet (pour analyse Ethereum live)

### Méthode recommandée : fichier `.env` local

À la racine du projet, créez votre fichier local à partir du modèle :

```powershell
Copy-Item .env.example .env
notepad .env
```

Dans Notepad, remplacez les valeurs vides et l'exemple de clé par vos propres
clés, puis enregistrez le fichier. N'ajoutez ni guillemets ni espaces autour du
`=`. Ne partagez jamais `.env` : il est exclu de Git.

```dotenv
ETHERSCAN_API_KEY=votre_nouvelle_cle_etherscan
ETHEREUM_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/votre_nouvelle_cle_alchemy
```

Révoquez toute clé déjà partagée publiquement et utilisez de nouvelles clés.
L'API lit automatiquement `.env` à chaque démarrage ; aucune saisie de clés
dans PowerShell n'est nécessaire. Les variables d'environnement déjà définies
restent prioritaires sur les valeurs du fichier.

Le RPC Alchemy fournit l'accès Ethereum mainnet utilisé pour vérifier le réseau
et les contrats. L'historique des transactions de l'analyse live continue de
venir d'Etherscan ; `ETHERSCAN_API_KEY` reste donc nécessaire séparément. Ne
remplacez pas `BLOCKCHAIN_RPC_URL` par ce RPC : cette variable sert au reporter
du contrat et peut cibler un autre réseau.

Après avoir enregistré `.env`, arrêtez l'ancienne API avec `Ctrl+C`, puis
redémarrez-la depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Vérifiez `http://127.0.0.1:8000/api/status` : `ethereum_provider_configured`
doit être `true`. N'utilisez pas `npm run start:local` pour le parcours Sepolia :
ce lanceur force volontairement le RPC Hardhat sur loopback.

### Faire un test réel en lecture seule

Dans un second terminal PowerShell, exécutez :

```powershell
.\scripts\test-ethereum-live.ps1
```

Le script demande une adresse publique Ethereum mainnet avec un historique,
puis appelle l'API réelle : Etherscan, vérification RPC chain ID 1, extraction
des caractéristiques, XGBoost et SHAP. Il fixe toujours
`autoriser_enregistrement_alerte` à `false` : aucune transaction n'est envoyée.
L'analyse réelle est toutefois conservée dans l'historique SQLite local.
L'interface web peut aussi lancer cette analyse ; laissez alors la case
d'autorisation d'alerte décochée.

Une adresse sans activité exploitable, une réponse fournisseur incomplète ou
un RPC incorrect doit produire une erreur explicite plutôt qu'un score de
remplacement. Le score reste expérimental et ne prouve ni fraude ni
blanchiment.

### Obtenir une clé Etherscan

1. Créez un compte gratuit sur https://etherscan.io/
2. Allez dans votre profil → API Keys
3. Créez une nouvelle clé (gratuite pour 5 requêtes/seconde)
4. Copiez la clé dans votre gestionnaire de secrets local ou dans la variable d'environnement; ne l'ajoutez pas au dépôt.

### Obtenir un RPC Mainnet

Options gratuites :
- https://cloud.google.com/application/web3/docs/ethereum-public-rpc
- https://www.alchemy.com/
- https://infura.io/

**Exigence :** Le RPC doit être Ethereum mainnet (chain ID 1). L'application vérifie cela automatiquement.

## 2. Configuration Sepolia (pour déploiement du contrat)

### Étape 1 : Stocker dans le keystore Hardhat (recommandé)

```powershell
# Stocke les valeurs chiffrées dans le keystore Hardhat local
npx hardhat keystore set SEPOLIA_RPC_URL
npx hardhat keystore set SEPOLIA_PRIVATE_KEY
```

Hardhat demande les valeurs et les stocke chiffrées dans son keystore utilisateur, hors du dépôt. `npx hardhat keystore path` affiche son emplacement et `npx hardhat keystore list` affiche uniquement les noms des variables enregistrées. `hardhat.config.ts` accepte également ces noms comme variables d'environnement; `.env` n'est pas chargé automatiquement.

### Étape 2 : Obtenir Sepolia ETH de test

1. Allez sur https://sepoliafaucet.com/ ou https://faucet.quicknode.com/ethereum/sepolia
2. Entrez l'adresse de votre wallet de déploiement
3. Attendez le crédit (quelques minutes)

### Étape 3 : Vérifier la configuration (lecture seule)

```powershell
npx hardhat --network sepolia run .\scripts\check-sepolia-config.ts
```

Le contrôle vérifie que le RPC répond sur Sepolia, affiche l'adresse publique du déployeur et lit son solde. Il n'envoie aucune transaction. Les erreurs indiquent le nom de la variable à vérifier; ne partagez pas les valeurs ni les sorties contenant des informations de compte.

### Étape 4 : Déployer le contrat (transaction Sepolia)

Le déploiement n'est pas nécessaire pour vérifier la configuration. Il envoie
une transaction et consomme du Sepolia ETH. Ne lancez cette commande qu'après
avoir contrôlé le contrat et donné votre autorisation explicite au déploiement :

```powershell
npx hardhat --build-profile production --network sepolia run .\ignition\deploy-transaction-alerts.ts
```

Notez l'adresse retournée et ouvrez
`https://sepolia.etherscan.io/address/<ADRESSE_CONTRAT>`. Dans l'onglet
**Contract**, la commande Hardhat ci-dessous vérifie et publie la source
compilée. L'API key Etherscan est demandée via une variable d'environnement
locale ou peut être stockée dans le keystore Hardhat :

```powershell
# Dans le terminal de vérification, si la clé n'est pas déjà dans l'environnement
$secret = Read-Host "Etherscan API key" -AsSecureString
$env:ETHERSCAN_API_KEY = [System.Net.NetworkCredential]::new("", $secret).Password

npx hardhat verify etherscan --network sepolia <ADRESSE_CONTRAT>
```

Le plugin utilise le profil `production` par défaut, Solidity 0.8.34 et
l'optimiseur activé à 200 runs. Le constructeur de `TransactionAlerts` n'a pas
d'argument. Ne présentez la source comme vérifiée qu'après confirmation de
l'explorateur.

### Étape 5 : Configurer le signataire API

Créez une clé séparée pour l'API (jamais la même que le déployeur) :

```powershell
# Générer une nouvelle clé (avec MetaMask ou autre wallet)
# Financez cette adresse avec Sepolia ETH de test

# RPC Sepolia et adresse du contrat déployé
$secret = Read-Host "Sepolia RPC URL for API" -AsSecureString
$env:BLOCKCHAIN_RPC_URL = [System.Net.NetworkCredential]::new("", $secret).Password
$env:BLOCKCHAIN_CONTRACT_ADDRESS = Read-Host "Deployed contract address"
$secret = Read-Host "API reporter private key" -AsSecureString
$env:BLOCKCHAIN_PRIVATE_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
$env:BLOCKCHAIN_REPORTER_ADDRESS = Read-Host "Public address derived from the API reporter key"
```

Cette clé doit appartenir à un compte distinct du déployeur. `BLOCKCHAIN_REPORTER_ADDRESS` est l'adresse publique autorisée par le script d'enregistrement; l'API vérifie à la connexion que le compte dérivé de `BLOCKCHAIN_PRIVATE_KEY` est reporter autorisé.

### Étape 6 : Autoriser le signataire API (transaction distincte)

Depuis le compte propriétaire (déployeur) :

```powershell
npx hardhat --network sepolia run .\scripts\register-alert-reporter.ts
```

Cette étape écrit elle aussi sur Sepolia et nécessite une autorisation
explicite. Le script attend le reçu et vérifie son statut. Contrôlez le hash
affiché sur `https://sepolia.etherscan.io/tx/<HASH>` avant de continuer.

### Étape 7 : Démarrer l'API avec le reporter Sepolia

Dans le terminal qui lancera l'API, configurez le RPC Sepolia et les valeurs
du contrat/reporter (la clé privée reporter reste locale) :

```powershell
$secret = Read-Host "Sepolia RPC URL for API" -AsSecureString
$env:BLOCKCHAIN_RPC_URL = [System.Net.NetworkCredential]::new("", $secret).Password
$env:BLOCKCHAIN_CONTRACT_ADDRESS = Read-Host "Verified deployed contract address"
$secret = Read-Host "API reporter private key" -AsSecureString
$env:BLOCKCHAIN_PRIVATE_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
$env:BLOCKCHAIN_REPORTER_ADDRESS = Read-Host "Public address derived from the API reporter key"

# Accès mainnet pour les données d'analyse; pas le RPC Sepolia ci-dessus.
$secret = Read-Host "Etherscan API key" -AsSecureString
$env:ETHERSCAN_API_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
$secret = Read-Host "Ethereum mainnet RPC URL" -AsSecureString
$env:ETHEREUM_RPC_URL = [System.Net.NetworkCredential]::new("", $secret).Password

.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Le service vérifie au démarrage le chain ID, le bytecode du contrat et le rôle
reporter du signataire. `GET /api/status` doit indiquer Sepolia et un service
blockchain connecté avant tout test d'alerte.

### Étape 8 : Parcours réel et vérification de l'événement

1. D'abord, lancez `.\scripts\test-ethereum-live.ps1` avec une adresse ayant
   une activité réelle. Ce test n'envoie aucune transaction et ne valide que
   l'analyse IA.
2. Dans l'interface, saisissez l'adresse mainnet à analyser. Laissez la case
   d'autorisation décochée pour une analyse sans écriture.
3. Une écriture Sepolia n'est autorisée qu'après consentement explicite pour
   cette analyse : cochez la case, puis soumettez. Elle n'a lieu que si le
   modèle retourne la classe positive. Une alerte positive n'est jamais une
   preuve de fraude.
4. Si l'API affiche « Alerte enregistrée » avec un hash, ouvrez
   `https://sepolia.etherscan.io/tx/<HASH>`. Vérifiez **Status: Success**, le
   contrat destinataire, puis **Logs** et l'événement `AlertRecorded`
   (identifiant d'analyse, adresse, score et reporter). Si aucun hash n'est
   renvoyé, ne déclarez pas l'alerte enregistrée.
5. Vérifiez aussi l'alerte dans l'onglet blockchain de l'application ; son
   réseau doit être Sepolia, et non Hardhat local.

Ne déclenchez pas une transaction uniquement pour obtenir une démonstration :
chaque alerte confirmée est publique et irréversible sur Sepolia.

## 3. Vérification de sécurité

### Ce qui NE JAMAIS faire

❌ Coller une clé privée dans le code
❌ Committer une clé dans Git
❌ Partager une clé dans une issue ou conversation
❌ Utiliser les clés Hardhat de développement sur un réseau réel
❌ Partager le fichier local `.env` ou le stocker dans un emplacement synchronisé non sécurisé

### Ce qui est SÉCURISÉ

✅ Variables d'environnement temporaires (session PowerShell)
✅ Keystore utilisateur chiffré de Hardhat (hors du dépôt)
✅ Fichier `.env` local, ignoré par Git et protégé comme un mot de passe
✅ Secrets CI/CD (GitHub Actions, GitLab CI)

## 4. Test de configuration

Après configuration, vérifiez :

```powershell
# Vérification Sepolia en lecture seule; aucune transaction n'est envoyée
npx hardhat --network sepolia run .\scripts\check-sepolia-config.ts
```

Pour l'analyse Ethereum, l'application exige `ETHERSCAN_API_KEY` et `ETHEREUM_RPC_URL`. Le fournisseur vérifie réellement que le RPC est sur Ethereum mainnet (chain ID 1) au premier accès; la vérification ci-dessus ne contacte pas Etherscan.

## 5. Nettoyage après utilisation

```powershell
# Effacer les variables d'environnement de la session
Remove-Item Env:ETHERSCAN_API_KEY
Remove-Item Env:ETHEREUM_RPC_URL
Remove-Item Env:BLOCKCHAIN_PRIVATE_KEY
Remove-Item Env:BLOCKCHAIN_REPORTER_ADDRESS
Remove-Item Env:BLOCKCHAIN_RPC_URL
Remove-Item Env:BLOCKCHAIN_CONTRACT_ADDRESS
Remove-Item Env:SEPOLIA_RPC_URL
Remove-Item Env:SEPOLIA_PRIVATE_KEY
```

## Résumé des clés nécessaires

| Usage | Variable | Source | Stockage |
|-------|----------|--------|----------|
| Analyse Ethereum live | `ETHERSCAN_API_KEY` | Etherscan | Fichier `.env` local ignoré |
| Analyse Ethereum live | `ETHEREUM_RPC_URL` | Alchemy/Infura | Fichier `.env` local ignoré |
| Déploiement / contrôle Sepolia | `SEPOLIA_RPC_URL` | Fournisseur RPC Sepolia | Keystore Hardhat recommandé |
| Déploiement / contrôle Sepolia | `SEPOLIA_PRIVATE_KEY` | Wallet de déploiement | Keystore Hardhat recommandé |
| Reporter API | `BLOCKCHAIN_RPC_URL` | Fournisseur RPC Sepolia | Session temporaire |
| Reporter API | `BLOCKCHAIN_CONTRACT_ADDRESS` | Adresse retournée au déploiement | Session temporaire |
| Reporter API | `BLOCKCHAIN_PRIVATE_KEY` | Wallet reporter distinct | Session temporaire |
| Enregistrement du reporter | `BLOCKCHAIN_REPORTER_ADDRESS` | Adresse publique du wallet reporter | Session temporaire |

`ANALYSIS_HISTORY_DB` est une variable facultative qui remplace le chemin local par défaut de la base d'historique; elle ne contient pas de secret.
