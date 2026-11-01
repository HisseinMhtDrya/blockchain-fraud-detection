# Rapport académique de projet

## Détection expérimentale du risque d'activité illicite sur Bitcoin et Ethereum

- **Établissement :** Université de Kinshasa — Faculté des Sciences et Technologies
- **Formation :** Master 1, Mathématiques, Statistiques et Informatique
- **Cours :** Blockchain et cryptomonnaies
- **Étudiant(e) :** à compléter
- **Encadreur :** à compléter
- **Année académique :** à compléter
- **Version du rapport :** 1.0
- **Date de rédaction :** 1er novembre 2026
- **Dépôt du code :** [github.com/HisseinMhtDrya/blockchain-fraud-detection](https://github.com/HisseinMhtDrya/blockchain-fraud-detection)
- **Révision du dépôt examinée :** [`0467e6c`](https://github.com/HisseinMhtDrya/blockchain-fraud-detection/commit/0467e6c81dc909502f0e39d9882cd4e26311f3c7)

> **Statut du livrable.** Ce document décrit l'état réellement vérifié du
> prototype. Il distingue les fonctionnalités implémentées, les résultats
> expérimentaux, les essais bloqués et les exigences restant à satisfaire.
> Aucun déploiement public, testnet public, audit Slither, résultat Bitcoin ou
> coût de gas non mesuré n'est présenté comme accompli.

---

## Résumé

Ce projet étudie la réalisation d'un prototype d'aide à la détection
expérimentale d'activités potentiellement illicites à partir de données
blockchain. Il associe un classifieur XGBoost Bitcoin préexistant, entraîné sur
166 variables du jeu Elliptic, à un second modèle XGBoost qui classe des
adresses Ethereum selon 26 caractéristiques comportementales et un indicateur
de contrat. Le modèle Ethereum a été entraîné sur un corpus public d'adresses
étiquetées et d'agrégats mensuels, puis évalué sur une séparation déterministe
par adresse. Sur les 12 809 adresses actives du jeu de test, il obtient une
exactitude de 0,8991, une précision positive de 0,8742, un rappel positif de
0,8340, un F1 positif de 0,8536, une ROC-AUC de 0,9605 et une
average precision de 0,9389 au seuil 0,5.

L'application comporte une API FastAPI, une interface web locale, un historique
SQLite, des explications SHAP et le contrat Solidity `TransactionAlerts`.
L'écriture d'une alerte est distincte de l'analyse et exige une autorisation
explicite dans l'interface. Les tests Python et Hardhat passent ; la compilation
Solidity de production et le contrôle TypeScript passent également. En revanche,
le modèle de graphe envisagé n'a pas été entraîné, les métriques du modèle
Bitcoin ne sont pas disponibles, Slither n'a pas été exécuté, et le contrat
n'est ni déployé ni vérifié sur Sepolia. L'analyse Ethereum live a été tentée,
mais l'accès RPC Alchemy a répondu HTTP 401 ; elle n'a donc pas été validée de
bout en bout sur mainnet. L'application n'est pas publiée sur un hébergeur
public.

**Mots-clés :** blockchain, Ethereum, Bitcoin, détection de risque, XGBoost,
SHAP, Solidity, FastAPI, apprentissage supervisé.

## Abstract

This project presents an experimental prototype for identifying potentially
illicit blockchain activity. It combines an existing Bitcoin XGBoost classifier
based on 166 Elliptic features with an Ethereum address classifier based on 26
behavioral features and a contract indicator. The Ethereum model was trained on
a public labeled-address corpus and evaluated using deterministic,
address-level train, validation, and test splits. On 12,809 active test
addresses, it achieved 0.8991 accuracy, 0.8742 positive-class precision,
0.8340 recall, 0.8536 F1-score, 0.9605 ROC-AUC, and 0.9389 average precision at
a 0.5 threshold.

The prototype includes a FastAPI backend, a local web interface, SQLite
analysis history, SHAP explanations, and a Solidity alert registry. Alert
submission is separate from analysis and requires explicit authorization. The
Python and Hardhat tests pass, as do the production Solidity build and
TypeScript type-check. The proposed graph neural network has not been trained;
Bitcoin evaluation metrics are unavailable; Slither has not been run; and the
contract has not been deployed or verified on Sepolia. A live Ethereum analysis
was attempted, but the Alchemy RPC returned HTTP 401, so no successful
mainnet end-to-end result is claimed. The application is not publicly hosted.

**Keywords:** blockchain, Ethereum, Bitcoin, risk detection, XGBoost, SHAP,
Solidity, FastAPI, supervised learning.

---

## Table des matières

1. [Introduction générale](#chapitre-1--introduction-générale)
2. [Contexte et exigences du projet](#chapitre-2--contexte-et-exigences-du-projet)
3. [Données et méthodologie expérimentale](#chapitre-3--données-et-méthodologie-expérimentale)
4. [Architecture et réalisation du prototype](#chapitre-4--architecture-et-réalisation-du-prototype)
5. [Contrat intelligent et sécurité](#chapitre-5--contrat-intelligent-et-sécurité)
6. [Résultats et validation](#chapitre-6--résultats-et-validation)
7. [Discussion, limites et conformité](#chapitre-7--discussion-limites-et-conformité)
8. [Conclusion et perspectives](#chapitre-8--conclusion-et-perspectives)
9. [Références](#références-bibliographiques)
10. [Annexes](#annexes)

---

## Chapitre 1 — Introduction générale

### 1.1 Contexte

Les registres publics de Bitcoin et d'Ethereum rendent observables de nombreux
événements et transferts. Leur transparence permet l'analyse de comportements
agrégés, mais la taille des historiques, la pseudonymité des adresses et la
diversité des usages compliquent l'identification de motifs atypiques.
L'apprentissage automatique peut classer des transactions ou des adresses à
partir de données déjà étiquetées ; il ne remplace ni une enquête, ni la
vérification de la provenance des étiquettes, ni une décision juridique.

La blockchain fournit par ailleurs un mécanisme de journalisation vérifiable.
Elle ne calcule pas directement une prédiction issue d'un modèle Python :
un service hors chaîne doit transmettre l'alerte au contrat. Le prototype
sépare donc l'analyse hors chaîne de l'inscription facultative d'une alerte
sur chaîne.

### 1.2 Problématique

Comment construire un prototype combinant analyse statistique d'activité,
explication d'une prédiction et journalisation contrôlée d'alertes, tout en
rendant visibles les limites des corpus, des mesures et du déploiement ?

### 1.3 Objectif général

Concevoir et évaluer un prototype de détection expérimentale de risques
d'activité sur Bitcoin et Ethereum, puis examiner comment une alerte produite
hors chaîne peut être consignée par un contrat intelligent.

### 1.4 Objectifs spécifiques

- exploiter le classifieur Bitcoin disponible et contrôler son interface API ;
- préparer des caractéristiques agrégées par adresse Ethereum ;
- entraîner et évaluer un classifieur XGBoost Ethereum ;
- produire des explications locales et globales avec SHAP ;
- offrir une API et un tableau de bord permettant une analyse ;
- développer un registre d'alertes Solidity avec contrôle d'accès ;
- automatiser les tests des fonctionnalités principales ;
- documenter les exigences non satisfaites et les limites scientifiques.

### 1.5 Périmètre et terminologie

Dans le corpus Ethereum, la classe positive correspond à une adresse
**étiquetée « scam » par les sources du jeu de données**. La classe négative
correspond à une adresse sélectionnée et non étiquetée comme scam ; elle ne
constitue pas une preuve d'innocuité. Le projet n'établit ni la culpabilité
d'une personne, ni une détection spécifique du blanchiment. Un score est un
indicateur expérimental, pas une preuve.

Le prototype fournit une analyse Bitcoin fondée sur des caractéristiques
fournies, une analyse Ethereum fondée sur un historique d'adresse, une
simulation locale synthétique et un registre d'alertes. Il ne transfère pas de
cryptomonnaie. L'inscription d'une alerte est une écriture blockchain distincte
et opt-in.

---

## Chapitre 2 — Contexte et exigences du projet

### 2.1 Exigences de la consigne

Le texte de référence demande un prototype de blockchain ou d'application
décentralisée, accessible en ligne, avec données de démonstration et pouvant
évoluer vers la production. Il demande au minimum un contrat déployé sur un
réseau public de test ou une blockchain privée, une interface web ou API
documentée, des tests automatisés, une analyse de sécurité, des métriques IA,
une documentation d'architecture, des menaces, des coûts et une feuille de
route. Les livrables demandés comprennent également des liens publics, des
adresses de contrats, des captures et des informations de démonstration sans
secret.

### 2.2 Matrice de conformité

| Exigence demandée | Réalisation constatée | État |
|---|---|---|
| Au moins un contrat intelligent | `TransactionAlerts.sol`, compilation Solidity 0.8.34 et tests locaux Hardhat | **Réalisé en local** |
| Déploiement testnet public ou réseau privé accessible | Aucun déploiement Sepolia ou autre testnet n'est présent ni revendiqué | **Non réalisé** |
| Source de contrat vérifiée sur l'explorateur | Aucune adresse de contrat de testnet ; aucune vérification Etherscan | **Non réalisé** |
| Interface web et API documentée | Interface HTML/JavaScript locale, API FastAPI et documentation OpenAPI à `/docs` | **Réalisé localement ; non hébergé** |
| Portefeuille DApp connecté | Aucune intégration MetaMask/WalletConnect nécessaire au parcours actuel | **Non réalisé ; API signataire séparée** |
| Tests automatisés | 39 tests Python et 9 tests Hardhat réussis au contrôle du 1er novembre 2026 | **Réalisé** |
| Analyse Slither ou équivalente | Tests de permissions et validations présents ; Slither et audit statique n'ont pas été exécutés | **Partiel ; audit formel manquant** |
| Modèles, données et métriques documentés | Modèle Ethereum, corpus, partitions et métriques documentés ; métriques Bitcoin non disponibles | **Partiel** |
| Comparaison XGBoost et réseau de neurones/GNN | XGBoost Ethereum évalué ; aucun modèle neuronal/GNN entraîné | **Non réalisé** |
| Architecture on-chain/hors chaîne | API, fournisseur, modèle, historique et contrat décrits dans ce rapport | **Réalisé** |
| Tokenomics | Aucun jeton ni mécanisme économique n'est prévu | **Sans objet pour le prototype** |
| Coûts en gas mesurés | Aucune estimation reproductible ou mesure de gas n'est jointe | **Non réalisé** |
| Menaces, limites, feuille de route | Présentées aux chapitres 5, 7 et 8 | **Réalisé** |
| URL publique de l'application et de l'API | Seules des adresses `127.0.0.1` sont documentées | **Non réalisé** |
| Dépôt GitHub public | Dépôt fourni et branche `master` poussée | **Réalisé** |
| Adresse Sepolia et lien explorateur du contrat | Aucun déploiement de testnet | **Non réalisé** |
| Captures d'écran et comptes de démonstration | Non inclus dans les livrables contrôlés | **À compléter** |

Cette matrice évite de confondre une compilation ou un déploiement local avec
un déploiement public. Le dépôt GitHub est disponible à
[github.com/HisseinMhtDrya/blockchain-fraud-detection](https://github.com/HisseinMhtDrya/blockchain-fraud-detection).
Le code actuellement poussé ne constitue pas, à lui seul, une application
accessible publiquement.

---

## Chapitre 3 — Données et méthodologie expérimentale

### 3.1 Corpus Bitcoin : Elliptic

Le dépôt contient un modèle `XGBClassifier` sérialisé par joblib, avec
166 caractéristiques et deux classes (`0` et `1`). Le test d'API utilise la
première ligne du fichier de caractéristiques Elliptic disponible dans
l'environnement local afin de vérifier la prédiction, les explications SHAP
et l'enregistrement de l'analyse.

La version du corpus/source d'entraînement, les détails de prétraitement, une
séparation train/validation/test et un rapport de métriques du modèle Bitcoin
ne sont pas fournis dans les artefacts vérifiés. Par conséquent, aucune
accuracy, précision, rappel, F1 ou AUC Bitcoin n'est annoncée dans ce rapport.
L'existence de l'artefact et un test fonctionnel d'inférence ne constituent pas
une évaluation indépendante de ses performances.

### 3.2 Corpus Ethereum

Le corpus retenu est l'[Ethereum Address Behavior Dataset publié sur Hugging
Face](https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity),
identifié dans les artefacts par la révision
`6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70` et le DOI
[10.57967/hf/6373](https://doi.org/10.57967/hf/6373). La fiche du jeu déclare
une licence CC BY 4.0 ; les licences et droits des sources amont ne sont pas
tous établis par cette seule déclaration.

L'audit du fichier d'étiquettes rapporte 114 771 lignes brutes ; après
normalisation et déduplication, 114 739 adresses sont retenues : 60 086
adresses de classe négative sélectionnée et 54 653 adresses étiquetées scam.
Les variables textuelles `description`, dates de labels et identifiants de
ligne sont exclues des prédicteurs, notamment parce que la description peut
révéler directement la classe.

Le jeu d'agrégats comporte 1 491 498 lignes mensuelles et des caractéristiques
publiées pour 85 147 adresses, de 2015-08 à 2025-08. Les fichiers sources
volumineux et les partitions d'adresses ne sont pas conservés dans le dépôt
Git ; la révision et les empreintes des artefacts sont gérées par le script
d'entraînement et les rapports du projet.

### 3.3 Partitionnement et population évaluée

Les adresses sont séparées de manière déterministe en train, validation et
test selon une répartition 70 % / 15 % / 15 %, avec la graine 42 et une
stratification sur la paire `(is_scam, is_contract)`. Une même adresse ne doit
pas apparaître dans plusieurs partitions.

Une adresse est considérée active si au moins une caractéristique d'activité
comportementale est non nulle, en excluant le seul indicateur `is_contract`.
Seules ces adresses actives sont utilisées pour l'entraînement et le calcul des
métriques ; le code d'inférence refuse également de scorer une adresse sans
activité exploitable.

| Partition | Adresses | Actives évaluées | Sans caractéristique d'activité | Classe négative active | Classe positive active |
|---|---:|---:|---:|---:|---:|
| Entraînement | 80 317 | 59 499 | 20 818 | 38 671 | 20 828 |
| Validation | 17 211 | 12 839 | 4 372 | 8 307 | 4 532 |
| Test | 17 211 | 12 809 | 4 402 | 8 292 | 4 517 |

Le taux de données sans activité publiée est important, particulièrement pour
la classe positive. Ces adresses ne participent pas aux métriques ci-dessous ;
les scores ne doivent donc pas être généralisés à l'ensemble des 114 739
adresses étiquetées.

### 3.4 Caractéristiques Ethereum

Le modèle utilise 27 entrées ordonnées : 26 caractéristiques live et
`is_contract`. Les agrégats couvrent les transactions natives, les flux ETH,
les frais et le gaz, les transferts ERC-20, les transactions internes, les
contreparties et le rythme d'activité.

```text
normal_sent_cnt, normal_recv_cnt, normal_total_cnt, normal_failed_cnt,
normal_to_contract_cnt, normal_to_eoa_cnt, eth_sent_sum, eth_recv_sum,
eth_net_flow, tx_fee_eth_sum, gas_used_sum, erc20_sent_cnt, erc20_recv_cnt,
erc20_total_cnt, erc20_unique_tokens_sent, erc20_unique_tokens_recv,
internal_out_cnt, internal_in_cnt, internal_out_value_eth_sum,
internal_in_value_eth_sum, uniq_peers_cnt, uniq_contract_peers_cnt,
uniq_eoa_peers_cnt, active_span_min, burst_max_tx_5m, sessions_cnt,
is_contract
```

Le prétraitement appliqué à chacune des entrées est :

```text
signed_log1p(x) = sign(x) × log(1 + abs(x))
```

Le schéma, l'ordre des colonnes et la transformation sont contrôlés au
chargement du modèle. La définition exacte et les unités de chaque colonne
sont détaillées dans [`reports/ethereum_feature_contract.md`](./reports/ethereum_feature_contract.md).

### 3.5 Modèle et protocole d'apprentissage

Le modèle est un `XGBClassifier` avec objectif `binary:logistic`, `tree_method`
`hist`, profondeur maximale 5, taux d'apprentissage 0,05, `min_child_weight`
5, `subsample` 0,85, `colsample_bytree` 0,85 et `reg_lambda` 2. L'arrêt anticipé
est réglé sur 40 itérations à partir de la validation. La meilleure itération
est 1 732 ; le modèle final utilise 1 733 estimateurs. La graine est 42 et le
seuil de classification est fixé à 0,5.

Le modèle Bitcoin est un artefact séparé et préexistant. Il ne faut pas le
confondre avec l'expérience d'entraînement Ethereum décrite ci-dessus.

### 3.6 Définitions des indicateurs

Pour la classe positive étiquetée scam :

- **Précision** = TP / (TP + FP), parmi les adresses signalées positives,
  proportion d'adresses effectivement étiquetées positives ;
- **Rappel** = TP / (TP + FN), parmi les positives du test, proportion
  détectée par le modèle ;
- **F1** = moyenne harmonique de la précision et du rappel ;
- **Exactitude (accuracy)** = (TP + TN) / N ;
- **ROC-AUC** mesure le classement positif/négatif sur les seuils ;
- **Average precision (AP)** résume la courbe précision-rappel par la
  définition de scikit-learn ; elle est rapportée comme AP et ne doit pas être
  interprétée comme une estimation de prévalence en production.

Les matrices sont présentées dans l'ordre `[[TN, FP], [FN, TP]]`. Les mesures
dépendent du seuil 0,5 et des labels/proportions spécifiques au corpus.

---

## Chapitre 4 — Architecture et réalisation du prototype

### 4.1 Composants

| Couche | Réalisation | Responsabilité |
|---|---|---|
| Interface | HTML, CSS, JavaScript et graphiques | Saisie, affichage des résultats, état des services et historique |
| API | FastAPI / Python | Validation, orchestration, réponses REST et documentation OpenAPI |
| Modèle Bitcoin | XGBoost chargé depuis joblib | Classification de 166 caractéristiques fournies |
| Modèle Ethereum | XGBoost, transformation partagée, SHAP | Classification d'adresse à partir de 27 colonnes |
| Fournisseurs live | Etherscan API V2 et RPC Ethereum | Historique transactionnel et état de contrat |
| Historique | SQLite | Analyses, scores, type d'analyse et état de l'inscription |
| Contrat | Solidity `TransactionAlerts` | Journal public des alertes autorisées |
| Réseau de développement | Hardhat local, chain ID 31337 | Compilation, essais et démonstration locale |

### 4.2 Parcours d'une analyse Ethereum

1. L'utilisateur soumet une adresse Ethereum à `POST /api/ethereum/analyze`.
2. Le service vérifie que le modèle et les accès fournisseur sont disponibles.
3. Etherscan fournit les historiques natifs, internes et ERC-20 ; les appels
   RPC vérifient le chain ID et le code des adresses.
4. Le backend valide les données, calcule les caractéristiques et refuse les
   réponses incomplètes ou une activité nulle.
5. Le modèle calcule la classe, les probabilités, un score sur 100 et les
   contributions SHAP.
6. Le résultat est conservé dans l'historique local SQLite.
7. Aucune écriture blockchain n'est faite par défaut. Une alerte positive ne
   peut être proposée à l'inscription qu'après autorisation explicite.

Les ERC-721/ERC-1155 ne sont pas introduits dans les colonnes ERC-20. Une
pagination qui dépasse la limite, des champs fournisseur manquants ou un
chain ID RPC différent de 1 interrompent l'analyse au lieu de produire un
score sur des données partielles.

### 4.3 Parcours Bitcoin et simulation

Le parcours Bitcoin reçoit un identifiant facultatif et 166 valeurs, vérifie
les nombres finis, produit une prédiction et des explications SHAP, puis
conserve le résultat localement. Un test API utilise un échantillon Elliptic
présent dans l'environnement de test. L'interface dispose aussi d'un exemple
synthétique Ethereum local, séparé du parcours live et sans inscription
blockchain ni sauvegarde historique.

### 4.4 API exposée

| Route | Méthode | Fonction |
|---|---|---|
| `/predict` | POST | Analyser une transaction Bitcoin |
| `/api/ethereum/analyze` | POST | Analyser une adresse Ethereum live |
| `/api/ethereum/demo` | POST | Tester l'analyseur avec un exemple synthétique local |
| `/api/ethereum/metrics` | GET | Lire les métriques Ethereum générées |
| `/api/ethereum/shap-importance` | GET | Lire les importances globales SHAP |
| `/api/history` | GET | Consulter l'historique paginé et filtrable |
| `/api/analytics` | GET | Statistiques agrégées du tableau de bord |
| `/api/alerts` | GET | Consulter les alertes disponibles sur le réseau connecté |
| `/api/status` | GET | Vérifier les services et l'état de configuration |
| `/health` | GET | Contrôle d'état simplifié |
| `/docs` | GET | Documentation interactive FastAPI/OpenAPI |

### 4.5 Configuration des secrets

Le fichier `.env` local est ignoré par Git. Le backend charge ses valeurs au
démarrage et ne doit pas publier de clés dans le code ou les réponses API.
L'analyse mainnet nécessite séparément `ETHERSCAN_API_KEY` et
`ETHEREUM_RPC_URL`. Les valeurs de l'analyse en lecture seule sont distinctes
des variables de signature Sepolia (`BLOCKCHAIN_RPC_URL`,
`BLOCKCHAIN_CONTRACT_ADDRESS` et `BLOCKCHAIN_PRIVATE_KEY`). Les clés de
fournisseur précédemment partagées doivent être révoquées et remplacées.

Au contrôle final précédant ce rapport, une tentative d'analyse live a échoué
avec `Configured Ethereum RPC returned HTTP 401`. Une réponse 401 signifie
que l'accès RPC configuré n'a pas été accepté ; aucune analyse live réussie
sur une adresse réelle n'est donc revendiquée.

---

## Chapitre 5 — Contrat intelligent et sécurité

### 5.1 Registre `TransactionAlerts`

Le contrat [`contracts/TransactionAlerts.sol`](./contracts/TransactionAlerts.sol)
stocke une séquence d'alertes comprenant un identifiant, un score de 0 à 100,
une classe binaire, un horodatage et l'adresse du reporter. Il expose
`getAlert` et `getAlertCount`, ainsi que les opérations de gestion de rôle.

Le déployeur devient propriétaire et reporter initial. Le propriétaire peut
autoriser/révoquer des reporters et transférer la propriété. L'ancien
propriétaire perd son rôle de reporter lors du transfert. Le contrat refuse
les identifiants vides ou de plus de 128 octets, les scores supérieurs à 100
et les reporters non autorisés. Les événements `AlertRecorded`,
`ReporterUpdated` et `OwnershipTransferred` assurent la traçabilité.

### 5.2 Relation entre IA et blockchain

Le modèle et le calcul SHAP s'exécutent hors chaîne. L'API joue le rôle de
service oracle : après analyse, elle peut appeler `recordAlert`. Le contrat
ne vérifie pas lui-même la prédiction du modèle ; il vérifie principalement
l'autorisation du reporter et les bornes des entrées. L'utilisateur doit
autoriser séparément l'inscription depuis l'interface. Cette architecture ne
rend pas le modèle décentralisé et ne transforme pas le score en preuve.

Les chaînes publiques rendent les événements et les identifiants inscrits
visibles et durablement consultables. Il ne faut y inscrire aucune information
personnelle, confidentielle ou non nécessaire. Même une adresse blockchain
est publiquement corrélable à son historique.

### 5.3 Réseaux et contraintes d'écriture

Le contrat a été compilé et testé sur Hardhat local (chain ID 31337). Aucun
déploiement Sepolia n'est établi. Le service de signature limite le réseau
externe pris en charge à Sepolia (chain ID 11155111) et exige un signataire
configuré et autorisé. Le RPC Alchemy mainnet est destiné à la lecture/analyse ;
il ne doit pas être confondu avec le réseau d'écriture du reporter.

### 5.4 Analyse de sécurité réalisée et manquante

Contrôles effectivement observés :

- compilation Solidity avec le profil de production ;
- tests des droits owner/reporter, transfert de propriété, scores et
  identifiants invalides, événements et écritures autorisées ;
- validation des entrées de l'API et refus des réponses fournisseur
  incomplètes ;
- exclusion Git des secrets, données locales et environnements ajoutée ou
  maintenue pour les fichiers pertinents ;
- séparation de l'analyse en lecture seule et de l'inscription opt-in.

Contrôles non réalisés :

- Slither n'est pas installé et n'a pas été exécuté ;
- aucun audit indépendant ni rapport formel de vulnérabilités n'est fourni ;
- aucun déploiement public n'a été inspecté sur explorateur ;
- aucune mesure de gas n'a été collectée ;
- le modificateur `nonReentrant` existe, mais aucune interaction externe n'est
  effectuée dans `recordAlert` et aucun audit ne démontre à lui seul une
  propriété de sécurité.

Les tests automatisés sont des vérifications fonctionnelles ciblées ; ils ne
remplacent pas une revue de sécurité professionnelle.

---

## Chapitre 6 — Résultats et validation

### 6.1 Résultats du modèle Ethereum

Les métriques suivantes sont issues de
[`reports/ethereum_model_metrics.json`](./reports/ethereum_model_metrics.json).
Les valeurs sont arrondies à quatre décimales ; les effectifs correspondent
uniquement aux adresses actives évaluées.

| Partition | N actif | Accuracy | Précision positive | Rappel positif | F1 positif | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | 59 499 | 0,9354 | 0,9213 | 0,8916 | 0,9062 | 0,9830 | 0,9707 |
| Validation | 12 839 | 0,9019 | 0,8759 | 0,8414 | 0,8583 | 0,9626 | 0,9410 |
| Test | 12 809 | 0,8991 | 0,8742 | 0,8340 | 0,8536 | 0,9605 | 0,9389 |

#### Matrices de confusion

Ordre des classes : `0 = selected_non_scam`, `1 = labeled_scam`.

| Partition | Matrice `[[TN, FP], [FN, TP]]` | TN | FP | FN | TP |
|---|---|---:|---:|---:|---:|
| Train | `[[37084, 1587], [2257, 18571]]` | 37 084 | 1 587 | 2 257 | 18 571 |
| Validation | `[[7767, 540], [719, 3813]]` | 7 767 | 540 | 719 | 3 813 |
| Test | `[[7750, 542], [750, 3767]]` | 7 750 | 542 | 750 | 3 767 |

Sur le jeu de test, le rapport de classification donne pour la classe
négative une précision de 0,9118, un rappel de 0,9346 et un F1 de 0,9231.
Pour la classe positive, il donne 0,8742, 0,8340 et 0,8536 respectivement.
Le rappel positif inférieur à la précision indique que 750 exemples positifs
du test n'ont pas été détectés au seuil choisi ; 542 négatifs ont été classés
à tort comme positifs.

L'écart train/test est compatible avec une généralisation inférieure aux
résultats d'entraînement, mais ne permet pas de quantifier la performance en
production. La ROC-AUC et l'average precision élevées décrivent le classement
sur cette sélection de corpus et ne prouvent ni une probabilité calibrée, ni
la capacité de détection de blanchiment.

### 6.2 Explicabilité SHAP

L'importance globale est calculée par la moyenne de la valeur absolue SHAP sur
un échantillon de test de 1 000 adresses, avec un fond de 100 exemples
d'entraînement. Les cinq variables les plus contributives sont :

| Rang | Variable | Moyenne de `|SHAP|` |
|---:|---|---:|
| 1 | `tx_fee_eth_sum` | 0,135429 |
| 2 | `sessions_cnt` | 0,079593 |
| 3 | `internal_in_value_eth_sum` | 0,077054 |
| 4 | `internal_out_value_eth_sum` | 0,065492 |
| 5 | `erc20_unique_tokens_recv` | 0,060746 |

SHAP décrit les contributions du modèle relativement au fond d'entraînement.
Il n'établit ni causalité, ni motif juridique. L'interface retourne les
principales contributions par analyse ; le parcours live reste non validé
tant que l'accès RPC répond 401.

### 6.3 Résultats Bitcoin

L'artefact Bitcoin est bien un `XGBClassifier` binaire contenant
166 caractéristiques (`models/xgboost_blockchain.pkl`). Le test d'API
fonctionnel vérifie la prédiction sur un exemple Elliptic disponible,
l'obtention de huit contributions SHAP et la persistance locale.

Les métriques du modèle Bitcoin — accuracy, précision, rappel, F1, ROC-AUC,
average precision et matrice de confusion — ne figurent pas dans les rapports
ou artefacts de résultats vérifiés. Elles ne peuvent pas être reconstituées
de façon fiable avec le seul fichier de modèle et un exemple d'inférence.
Elles sont donc **non disponibles**, et non égales à zéro. Un protocole de
test étiqueté indépendant est requis avant de revendiquer des performances.

### 6.4 Tests logiciels et construction

Contrôles exécutés le 1er novembre 2026 :

| Commande | Résultat |
|---|---|
| `npm run test:python` | **39 tests réussis** |
| `npm run test:hardhat` | **9 tests réussis** (3 Solidity, 6 Node.js/TypeScript) |
| `npm run build:production` | **Réussi**, compilation de 3 fichiers Solidity avec solc 0.8.34 |
| `npm run typecheck` | **Réussi**, `tsc --noEmit` |

Les tests couvrent notamment l'API Bitcoin/Ethereum, l'historique, les
caractéristiques, les refus d'entrées ou réponses invalides, l'accès aux
alertes et les événements du contrat. Des avertissements de dépréciation de
dépendances Python ont été émis par l'environnement de test ; ils n'ont pas
fait échouer la suite.

### 6.5 Tests d'intégration et déploiement

| Scénario | État vérifié |
|---|---|
| Application et API en local | Fonctionnalités locales et endpoints testés |
| Analyse Bitcoin sur exemple Elliptic | Test API réussi sur l'échantillon local disponible |
| Contrat sur Hardhat local | Compilation et tests automatisés réussis |
| Analyse Ethereum synthétique locale | Parcours de démonstration testé sans fournisseur externe |
| Analyse Ethereum live Etherscan/RPC | **Échec : RPC Alchemy HTTP 401**, aucun score live revendiqué |
| Contrat sur Sepolia | **Non déployé** |
| Vérification du contrat sur explorateur | **Non réalisée** |
| Déploiement public de l'interface/API | **Non réalisé** |
| Coûts de gas d'une transaction Sepolia | **Non mesurés** |

Les réponses `200` observées sur les routes de tableau de bord ne prouvent pas
que l'analyse live fonctionne : elles concernent des endpoints distincts.

---

## Chapitre 7 — Discussion, limites et conformité

### 7.1 Validité des étiquettes et généralisation

Le corpus Ethereum combine des sources de labels multiples et ne fournit pas
de date fiable de connaissance de chaque label. Une adresse négative signifie
« non étiquetée comme scam dans la sélection », non « vérifiée comme licite ».
La sélection des adresses et la proportion de classes ne reproduisent pas une
prévalence de terrain ; précision et score ne doivent pas être interprétés
comme des mesures directement opérationnelles.

La séparation est faite par adresse et non dans le temps. Elle empêche qu'une
même adresse soit répartie entre partitions, mais ne constitue pas une
évaluation prospective. Des labels datés et des snapshots temporels seraient
nécessaires pour mesurer la dérive et réduire le risque de fuite temporelle.

### 7.2 Compatibilité entraînement–inférence

Le modèle conserve le même ordre de 27 colonnes et la même transformation
`signed_log1p` à l'entraînement et en inférence. Cependant, le détail des
agrégations publiées n'est pas suffisamment complet pour prouver leur
équivalence sémantique aux valeurs recalculées depuis Etherscan. Les types de
contrats et de contreparties live proviennent de l'état RPC actuel, tandis que
les données d'apprentissage sont historiques. Les fenêtres temporelles, la
pagination et les sources de transactions peuvent aussi différer.

### 7.3 Limites de l'analyse live

À la rédaction, le fournisseur Alchemy refuse la requête RPC avec HTTP 401.
Cela bloque la vérification du chain ID et des types de contrats, donc le
parcours réel de l'adresse jusqu'au score. L'exemple synthétique teste
l'intégration du modèle mais ne remplace pas un test mainnet.

L'API Etherscan a en outre des quotas et limites de pagination ; les limites de
sécurité du code peuvent interrompre l'analyse si l'historique est trop grand.
Le comportement fail-closed est préférable à la production silencieuse d'un
score sur un historique tronqué, mais réduit le nombre d'adresses analysables.

### 7.4 Limites Bitcoin et comparaison de modèles

Le modèle Bitcoin dispose d'un artefact et d'un test d'inférence, mais sans
protocole reproductible ni métriques, son niveau de performance ne peut être
comparé à celui du modèle Ethereum. Aucune comparaison XGBoost–réseau neuronal
ou XGBoost–GNN n'a été réalisée.

Le corpus d'arêtes complet mentionné par le projet est d'environ 20,1 Gio et
n'a pas été téléchargé. PyTorch/PyTorch Geometric et un environnement de
calcul graphe adapté ne sont pas disponibles dans cette phase. Le coût
mémoire, le partitionnement des arêtes et les fuites par message passing
devraient être traités avant toute expérience GNN.

### 7.5 Limites opérationnelles et de sécurité

- L'interface et l'API sont documentées et exécutables localement, pas
  hébergées sur Vercel, Render ou un autre service public.
- Le contrat est validé sur Hardhat local ; son adresse locale n'est pas une
  adresse Sepolia.
- L'analyse Slither et la revue indépendante demandées ne sont pas fournies.
- Les coûts de gas ne sont pas rapportés.
- Aucun portefeuille n'est connecté à la DApp ; le service API contrôle le
  signataire reporter.
- Une écriture sur chaîne est publique et irréversible ; le score seul ne
  justifie pas une accusation ou une action coercitive.
- Les clés API déjà partagées doivent être révoquées ; aucune clé n'est
  publiée dans le dépôt Git.

### 7.6 Ce que les résultats permettent d'affirmer

Le projet permet d'affirmer qu'un modèle XGBoost Ethereum a été entraîné et
évalué sur une partition de test spécifique, qu'il atteint les métriques du
chapitre 6, et qu'une architecture locale d'analyse, d'explication et de
journalisation d'alertes a été implémentée et testée.

Il ne permet pas d'affirmer que le système détecte le blanchiment en production,
que les métriques reflètent la prévalence réelle, que l'analyse Ethereum live
fonctionne actuellement, que le contrat est déployé sur Sepolia ou qu'il a fait
l'objet d'un audit de sécurité statique.

---

## Chapitre 8 — Conclusion et perspectives

### 8.1 Conclusion

Le prototype relie deux pipelines de classification à une API, des explications
SHAP, un historique local et un contrat de journalisation des alertes. Le
résultat quantitatif principal est l'évaluation du modèle XGBoost Ethereum sur
12 809 adresses actives de test : accuracy 0,8991, précision positive 0,8742,
rappel 0,8340 et F1 positif 0,8536. Ces chiffres sont reproductibles depuis
les artefacts de métriques mais restent propres à un jeu sélectionné, une
séparation aléatoire par adresse et un seuil fixe.

Les tests logiciels et la compilation sont réussis. Toutefois, plusieurs
exigences de remise demeurent ouvertes : résoudre l'accès RPC live, exécuter
une analyse sur adresse réelle, déployer et vérifier le contrat sur Sepolia,
publier l'application, conduire un audit de sécurité et documenter les frais
de gas. L'absence de métriques Bitcoin et d'une comparaison neuronale doit
également être traitée avant une conclusion expérimentale comparative.

### 8.2 Travaux futurs prioritaires

1. Corriger l'accès RPC Alchemy et valider l'analyse live en lecture seule,
   sans publier les clés ni autoriser une écriture.
2. Ajouter un jeu de test Bitcoin étiqueté, définir son protocole, et publier
   les métriques par classe et les matrices de confusion.
3. Comparer XGBoost à une baseline simple puis à un réseau neuronal adapté ;
   envisager le GNN seulement avec un sous-graphe exploitable et une stratégie
   anti-fuite.
4. Effectuer un split temporel dès que les dates d'étiquettes sont disponibles.
5. Exécuter Slither ou un outil équivalent, traiter ses constats et faire
   revoir le contrat.
6. Déployer le contrat sur Sepolia après autorisation, vérifier sa source,
   enregistrer l'adresse et mesurer le gas sur reçus de testnet.
7. Héberger l'API et l'interface, protéger les clés par secrets de plateforme
   et tester les URL publiques sans accès privilégié.
8. Ajouter captures d'écran, instructions de démonstration et informations
   non sensibles nécessaires à la remise.

---

## Références bibliographiques

1. Weber, M. et al. (2019). *Anti-Money Laundering in Bitcoin: Experimenting
   with Graph Convolutional Networks for Financial Forensics*. KDD 2019
   Workshop on Anomaly Detection in Finance.
2. Chen, T. et Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting
   System*. Proceedings of the 22nd ACM SIGKDD International Conference on
   Knowledge Discovery and Data Mining, p. 785–794.
   DOI : [10.1145/2939672.2939785](https://doi.org/10.1145/2939672.2939785).
3. Lundberg, S. M. et Lee, S.-I. (2017). *A Unified Approach to Interpreting
   Model Predictions*. Advances in Neural Information Processing Systems 30.
4. `fesevu`. *Ethereum Address Behavior Dataset — GNN + LSTM*.
   [Fiche Hugging Face](https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity),
   DOI [10.57967/hf/6373](https://doi.org/10.57967/hf/6373), révision
   `6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70`. La fiche déclare CC BY 4.0 ;
   les sources amont restent à examiner séparément.
5. Elliptic. *Elliptic Data Set*.
   [Kaggle](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set).
6. Solidity. *Documentation du langage Solidity*.
   [soliditylang.org](https://docs.soliditylang.org/).
7. Hardhat. *Documentation Hardhat 3*.
   [hardhat.org](https://hardhat.org/docs).
8. Etherscan. *API Documentation*.
   [docs.etherscan.io](https://docs.etherscan.io/).
9. Les dépendances et versions utilisées sont déclarées dans
   [`requirements-app.txt`](./requirements-app.txt),
   [`requirements-ethereum-data.txt`](./requirements-ethereum-data.txt) et
   [`package.json`](./package.json).

---

## Annexes

### Annexe A — Commandes de validation

Depuis la racine du dépôt sous Windows :

```powershell
npm run test:python
npm run test:hardhat
npm run build:production
npm run typecheck
```

Pour démarrer la démonstration sur Hardhat local :

```powershell
npm run start:local
```

Le serveur local n'est pas un déploiement public et les données de la chaîne
Hardhat ne doivent pas être confondues avec des données Sepolia.

### Annexe B — Fichiers de résultats et d'implémentation

- [`reports/ethereum_model_training.md`](./reports/ethereum_model_training.md) :
  hyperparamètres, métriques, couverture, limites et importances SHAP.
- [`reports/ethereum_model_metrics.json`](./reports/ethereum_model_metrics.json) :
  métriques détaillées par partition et par classe.
- [`reports/ethereum_dataset_audit.md`](./reports/ethereum_dataset_audit.md) :
  audit des sources, labels, doublons et séparations.
- [`reports/ethereum_feature_contract.md`](./reports/ethereum_feature_contract.md) :
  définitions et unités des caractéristiques.
- [`CONFIGURATION_GUIDE.md`](./CONFIGURATION_GUIDE.md) : configuration
  locale et séparation entre RPC d'analyse et de signature.
- [`contracts/TransactionAlerts.sol`](./contracts/TransactionAlerts.sol) :
  contrat de journalisation.
- [`api.py`](./api.py), [`ethereum_features.py`](./ethereum_features.py) et
  [`etherscan_provider.py`](./etherscan_provider.py) : API, extraction et
  fournisseur Ethereum.

### Annexe C — Informations à compléter avant la remise académique

- nom de l'étudiant(e), membres du groupe et matricules ;
- nom de l'encadreur et année académique ;
- captures d'écran et déroulé de démonstration ;
- URL publique de l'application et documentation API hébergée ;
- adresse du contrat déployé sur Sepolia et lien de vérification ;
- rapport Slither ou audit équivalent ;
- coûts en gas mesurés ;
- métriques reproductibles du modèle Bitcoin et résultat de comparaison avec
  le modèle neuronal demandé ;
- confirmation de la rotation des clés exposées et vérification de la
  configuration RPC live.

**Fin du rapport.**
