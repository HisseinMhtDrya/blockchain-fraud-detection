# Phase 2 — Audit et préparation du jeu de données Ethereum

Date de l'audit : 2026-10-30

## Décision de corpus

Le corpus retenu provisoirement pour l'expérimentation est
[Ethereum Address Behavior Dataset — GNN + LSTM](https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity),
publié sur Hugging Face par `fesevu` et identifié par le DOI
[10.57967/hf/6373](https://doi.org/10.57967/hf/6373). La fiche déclare une
licence **CC BY 4.0**. Cette licence est celle déclarée pour le corpus publié ;
les licences des jeux de données amont ne sont pas toutes précisées dans sa
documentation et restent à vérifier avant toute redistribution.

Ce choix est limité à une tâche expérimentale de classement d'adresses
« scam étiqueté contre adresses sélectionnées non étiquetées comme scam ». Le
corpus ne contient pas une cible spécifique au blanchiment et ne permet pas de
présenter le score comme une probabilité générale d'activité illicite.

## Comparaison des candidats

| Corpus | Source, licence et volume vérifiés | Étiquettes et granularité | Décision et limites |
|---|---|---|---|
| [Ethereum Address Behavior Dataset](https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity) | Fiche Hugging Face et DOI ; licence déclarée CC BY 4.0. CSV compressé des adresses équilibrées : 3 851 967 octets. La fiche décrit environ 115 000 adresses et un jeu initial dépassant un million. Le jeu transactionnel brut annoncé est très volumineux ; le visualiseur Hugging Face déclare 1 616 802 731 lignes pour la configuration visible. | Adresse, `is_scam` (0/1), type contrat/EOA, description et dates d'activité. Les auteurs décrivent des sources telles que XBlock, PTXPhish, Forta, Etherscan Labels, CryptoScamDB et ScamSniffer. Des transactions Ethereum et des agrégats journaliers sont également publiés. | Meilleure correspondance technique au classement d'adresses et à une éventuelle comparaison tabulaire/GNN. Corpus composite, sans provenance de label par ligne dans le schéma publié ; la classe négative est une sélection, pas une preuve d'innocuité. Le volume brut est impraticable pour un téléchargement intégral dans cette phase. |
| [Ethereum Fraud Detection Dataset (Kaggle)](https://www.kaggle.com/datasets/vagifa/ethereum-frauddetection-dataset) | Métadonnées Kaggle : licence « Database: Open Database, Contents: Database Contents », un CSV de 2 880 761 octets. La page décrit des lignes par adresse avec des caractéristiques agrégées. | `Address`, `FLAG` présenté comme fraude/non-fraude et agrégats natifs/ERC-20 ; donc potentiellement une cible par adresse. | Petit et directement compatible avec une classification tabulaire, mais la page ne documente pas suffisamment la provenance des étiquettes, leur période ni le protocole de collecte. Non retenu comme corpus principal. Aucun fichier Kaggle n'a été téléchargé. |
| [Forta labelled-datasets](https://github.com/forta-network/labelled-datasets) | Dépôt public Forta ; licence du dépôt MIT. Ses fichiers Ethereum citent des labels Etherscan et des listes phishing/exploit. `etherscan_malicious_labels.csv` fait 678 922 octets selon l'API GitHub. | Labels positifs d'adresses/contrats ; pas de population bénigne appariée ni de variables transactionnelles dans ce fichier. | Source utile pour documenter des menaces ou faire une analyse positive/non étiquetée. Ne suffit pas à un apprentissage binaire ni à une évaluation supervisée autonome. Le dépôt ne confirme pas à lui seul les droits des sources tierces. |
| [Poison-Hunter (ACM CCS 2024)](https://github.com/DS2L/Poison-Hunter) | Dépôt des auteurs associé à une publication ; aucune licence de réutilisation explicite identifiée dans le dépôt. | README : 5 890 adresses phishing étiquetées par Etherscan et Forta, 1 154 adresses populaires dites bénignes, et un échantillon de 150 transferts. Cible étroite : address poisoning/phishing. | Provenance scientifique plus claire pour cette menace précise, mais négatifs très sélectionnés, exemples de transferts limités et licence à clarifier. Ne convient pas à une affirmation sur le blanchiment en général. |
| [PTXPhish (NDSS 2025)](https://github.com/blocksecteam/PTXPhish) | Dépôt de l'équipe de recherche et publication NDSS ; aucune licence de données explicite identifiée. | Le README annonce 5 000 transactions phishing réparties en catégories et 13 557 transactions bénignes. Granularité transaction, pas une étiquette générale d'adresse. | Source académique intéressante pour un futur test transactionnel de phishing, mais tâche et unité différentes ; ne peut être présentée comme un dataset d'adresses. |

## Vérification de l'artifact retenu

Seul l'artifact minimal `addr_labels_balanced.csv.zst` a été récupéré pour
inspection locale. Il n'a pas été ajouté au dépôt. L'empreinte SHA-256 mesurée
est `52941005bd44d2597037e2e1c932e4d25fcf9c855980f442896cb497d1827b39`,
identique à l'OID SHA-256 du fichier publié sur Hugging Face à la révision
`6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70`.

Après décompression, le CSV contient 114 771 lignes et six colonnes :

- `address` : adresse Ethereum.
- `is_scam` : cible binaire publiée.
- `is_contract` : indicateur de contrat.
- `description` : texte de label/source.
- `activity_start_ts` et `activity_end_ts` : métadonnées d'activité.

Résultats de l'inspection :

- 36 lignes concernent quatre adresses dupliquées (32 lignes en excès). Les
  doublons observés n'ont pas de conflit de classe ou de type. Après
  normalisation et déduplication, il reste 114 739 adresses : 60 086 `is_scam=0`
  et 54 653 `is_scam=1`.
- Les négatifs comprennent 30 027 contrats et 30 059 EOA après déduplication ;
  les positifs comprennent 39 671 contrats et 14 982 EOA. La balance des types
  n'est donc pas la même dans les deux classes.
- `description` est manquante pour 79,22 % des négatifs et 0,22 % des positifs.
  Les descriptions positives contiennent fréquemment des termes tels que
  `phishing`, `Scamming`, `ponzi` ou `rugpull`. C'est une fuite directe ou un
  proxy très fort du label : **cette colonne doit être exclue des prédicteurs**.
- Les dates d'activité sont manquantes pour 8,02 % des négatifs et 45,33 % des
  positifs. Leurs valeurs et indicateurs de présence ne seront pas des
  prédicteurs : ils peuvent refléter la source de l'étiquette plutôt que le
  comportement observable à l'instant de l'analyse.
- La sélection SQL publiée vise un équilibre et donne une priorité à des
  adresses associées à des exchanges dans les négatifs. Le corpus effectivement
  inspecté n'est pas exactement équilibré. Les métriques mesurées sur celui-ci
  ne seront pas des estimations de prévalence en production.

Le fichier de labels ne contient pas lui-même les caractéristiques de
transaction nécessaires à l'entraînement : elles se trouvent dans d'autres
artifacts volumineux. Le README du sous-dossier `lstm_dataset` est en outre une
copie de la description GNN ; le schéma des agrégats a donc été contrôlé dans
les requêtes SQL publiées plutôt que déduit de ce README.

Le README et le SQL de préparation exposent des agrégats journaliers par
adresse : nombres de transactions natives entrantes/sortantes, transactions
échouées, destinataires contrats/EOA, volumes ETH envoyés/reçus et flux net,
frais et gas, nombres de transferts ERC-20 et de tokens uniques, transferts
internes, contreparties uniques, durée active, rafales de transactions et
sessions. Le schéma des transactions GNN comprend aussi les adresses source et
destination, l'horodatage, le numéro de bloc, la valeur et les frais en wei, le
nonce, la taille des données d'entrée, la création de contrat et le hash.

Les noms de caractéristiques journalières documentés dans la requête SQL
`LSTM_ligth` sont :

```text
normal_sent_cnt, normal_recv_cnt, normal_total_cnt, normal_failed_cnt,
normal_to_contract_cnt, normal_to_eoa_cnt, eth_sent_sum, eth_recv_sum,
eth_net_flow, tx_fee_eth_sum, gas_used_sum, erc20_sent_cnt, erc20_recv_cnt,
erc20_total_cnt, erc20_unique_tokens_sent, erc20_unique_tokens_recv,
internal_out_cnt, internal_in_cnt, internal_out_value_eth_sum,
internal_in_value_eth_sum, uniq_peers_cnt, uniq_contract_peers_cnt,
uniq_eoa_peers_cnt, active_span_min, burst_max_tx_5m, sessions_cnt
```

Le SQL indique également qu'`age_days` peut être dérivé de la première date
d'activité. Ces noms sont un contrat de caractéristiques candidat, pas la
preuve que tous les champs sont présents dans chaque artifact Parquet ou
reconstructibles à l'identique depuis l'API choisie.

## Compatibilité avec une analyse en ligne

Les caractéristiques candidates à calculer à partir d'une adresse Ethereum
sont des agrégats sur une fenêtre d'observation explicitement définie :

1. nombre de transactions natives entrantes/sortantes, échouées et réussite ;
2. total, moyenne, médiane, minimum et maximum des montants entrants/sortants
   et du flux net ;
3. frais/gas, fréquence, durée d'activité, jours actifs et rafales ;
4. nombre de contreparties uniques et répartition vers contrats/EOA ;
5. nombre, fréquence et diversité des transferts ERC-20 ;
6. transferts internes uniquement si le fournisseur choisi expose une source
   compatible et documentée ;
7. type contrat/EOA si calculé à la date d'observation par l'état on-chain.

Les variables devront avoir les mêmes unités, définitions, règles d'échec,
fenêtres temporelles et valeurs manquantes à l'entraînement et à l'inférence.
L'historique normal, ERC-20 et interne accessible via un explorateur peut être
tronqué ou soumis à des quotas ; une extraction partielle ne doit pas être
présentée comme complète. Les agrégats Etherscan ne sont pas automatiquement
équivalents aux agrégats BigQuery du corpus. Les variables sans équivalent
fiable en ligne devront être supprimées du contrat de caractéristiques, puis
le modèle réentraîné.

`description`, `is_scam`, les dates de collecte/résolution de label et les
identifiants de ligne ne sont pas des prédicteurs. `is_contract` peut être
utilisé seulement si l'application calcule la même variable ; les résultats
devront alors être rapportés séparément pour les EOA et contrats, avec une
baseline utilisant uniquement ce type.

## Séparation des données et limites de fuite

Le script
[`scripts/prepare_ethereum_dataset.py`](../scripts/prepare_ethereum_dataset.py)
crée des partitions d'adresses, pas des partitions de lignes transactionnelles :

- normaliser les adresses en minuscules et vérifier le format Ethereum ;
- rejeter les labels/type manquants ou contradictoires ; dédupliquer par adresse ;
- stratifier avec la combinaison `(is_scam, is_contract)` pour préserver les
  quatre sous-populations ;
- partition déterministe 70 % entraînement, 15 % validation, 15 % test, seed 42 ;
- garantir qu'une adresse n'apparaît que dans une partition et enregistrer les
  effectifs ainsi que l'empreinte du fichier source dans un manifeste ;
- ajuster tout imputer, encodeur, normaliseur, sélection de variables ou
  rééchantillonnage exclusivement sur l'entraînement ; validation pour choix
  d'hyperparamètres, test final utilisé une seule fois.

Pour un GNN, une partition d'adresses ne suffit pas si les arêtes d'un même
graphe relient des nœuds de plusieurs partitions : les arêtes traversant les
frontières devront être bloquées pour le calcul de message passing, ou le
protocole devra faire l'objet d'une évaluation temporelle séparée.

Il n'existe pas dans le schéma de label une date fiable indiquant quand
l'étiquette est devenue connue. Les dates d'activité ne remplacent pas cette
date, et certaines sont nulles. La séparation proposée évite la fuite d'une
même adresse entre train/validation/test, mais ne permet pas de revendiquer une
évaluation prospective ou une absence totale de fuite temporelle. Il faudra
obtenir des snapshots de labels datés pour un tel résultat.

## Reproductibilité

Télécharger la version épinglée depuis la fiche Hugging Face, puis installer
l'option de préparation des données et lancer :

```powershell
New-Item -ItemType Directory -Force .\data\external\ethereum
Invoke-WebRequest `
  -Uri "https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity/resolve/6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70/addr_labels_balanced.csv.zst" `
  -OutFile .\data\external\ethereum\addr_labels_balanced.csv.zst
python -m pip install -r requirements-ethereum-data.txt
python scripts/prepare_ethereum_dataset.py `
  --input .\data\external\ethereum\addr_labels_balanced.csv.zst `
  --output-dir .\data\processed\ethereum-address-splits
```

Le script vérifie par défaut le SHA-256 attendu. Il ne modifie ni le modèle
Elliptic ni l'API, et n'exporte pas `description` ni les dates dans les
partitions. L'exécution sur l'artifact vérifié a produit 80 317 adresses
d'entraînement, 17 211 de validation et 17 211 de test (seed 42), avec
stratification sur les quatre combinaisons classe/type. Les identifiants
d'adresse et fichiers de split n'ont pas été ajoutés au dépôt. Le téléchargement
des historiques transactionnels complets, la reconstitution des
caractéristiques, l'entraînement XGBoost/GNN et la comparaison chiffrée
relèvent des phases suivantes.

## Références principales

- [Fiche Hugging Face et licence déclarée](https://huggingface.co/datasets/fesevu/ethereum_fraud_dataset_by_activity).
- [DOI du corpus](https://doi.org/10.57967/hf/6373).
- [Pipeline et requêtes BigQuery des auteurs](https://github.com/fesevu/eth-fraud-dataset-pipeline).
- [BigQuery public Ethereum](https://cloud.google.com/blockchain-analytics/docs/schema).
- [Forta labelled-datasets](https://github.com/forta-network/labelled-datasets).
- [Poison-Hunter, ACM CCS 2024](https://github.com/DS2L/Poison-Hunter).
- [PTXPhish, NDSS 2025](https://github.com/blocksecteam/PTXPhish).
- [Kaggle Ethereum Fraud Detection Dataset](https://www.kaggle.com/datasets/vagifa/ethereum-frauddetection-dataset).
