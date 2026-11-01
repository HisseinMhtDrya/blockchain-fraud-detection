# Modèle XGBoost Ethereum — résultats mesurés

- Révision du corpus : `6a7a517fbdbe2bcc4ec65bee4c0ff15f1c0a3c70`
- Lignes mensuelles agrégées : 1,491,498
- Période couverte par les features : 2015-08 à 2025-08
- Adresses ayant des caractéristiques publiées : 85,147
- Itération retenue par arrêt anticipé sur validation : 1732
- Seuil de classification : 0,5 (fixé avant évaluation)
- Entraînement et métriques principales portent uniquement sur les adresses ayant au moins une caractéristique d'activité non nulle ; l'API refuse de scorer une adresse sans activité observée.
- La classe positive signifie « étiquetée scam dans ce corpus », pas blanchiment prouvé.
- Les lignes sans caractéristiques mensuelles sont encodées comme zéros ; leur couverture diffère selon la classe et figure dans le JSON détaillé.
- La séparation aléatoire par adresse n'est pas une évaluation prospective : les dates de connaissance des labels sont absentes.
- Les caractéristiques d'entraînement s'arrêtent à la dernière fenêtre mensuelle publiée ; l'inférence sur l'historique actuel peut subir une dérive temporelle.
- Pour l'inférence Etherscan, les champs « type de contrepartie » et `is_contract` sont calculés depuis l'état RPC actuel, tandis que le corpus utilise des labels/contracts historiques ; cette différence doit être considérée dans l'interprétation.

## Métriques par partition

| Partition | Accuracy | Précision (scam) | Rappel (scam) | F1 (scam) | ROC-AUC | PR-AUC | Confusion [[TN, FP], [FN, TP]] |
|---|---:|---:|---:|---:|---:|---:|---|
| train | 0.9354 | 0.9213 | 0.8916 | 0.9062 | 0.9830 | 0.9707 | `[[37084, 1587], [2257, 18571]]` |
| validation | 0.9019 | 0.8759 | 0.8414 | 0.8583 | 0.9626 | 0.9410 | `[[7767, 540], [719, 3813]]` |
| test | 0.8991 | 0.8742 | 0.8340 | 0.8536 | 0.9605 | 0.9389 | `[[7750, 542], [750, 3767]]` |

Les précisions, rappels et F1 par classe, ainsi que les matrices détaillées, sont dans `ethereum_model_metrics.json`.

## Couverture des caractéristiques

| Partition | Total | Avec activité | Sans activité publiée |
|---|---:|---:|---:|
| train | 80,317 | 59,499 | 20,818 |
| validation | 17,211 | 12,839 | 4,372 |
| test | 17,211 | 12,809 | 4,402 |

Nombre d'adresses avec features par classe : train (non-scam=38,671, scam=20,828); validation (non-scam=8,307, scam=4,532); test (non-scam=8,292, scam=4,517)

## Faisabilité GNN

Le dépôt Hugging Face publie un artifact d'arêtes complet de 21 572 870 251 octets (~20,1 Gio), ainsi qu'un mapping de nœuds et des labels. Cet artifact n'a pas été téléchargé. L'environnement ne contient pas PyTorch ni PyTorch Geometric, et le budget de calcul/mémoire ne permet pas de charger ce graphe intégral ; aucun GNN n'est déclaré entraîné. Une suite nécessitera un snapshot temporel plus petit ou un échantillonnage de voisins, un split de graphe sans arêtes de fuite et un runtime GPU/graph dédié.


## Principales importances SHAP

| Caractéristique | Moyenne de |SHAP| sur un échantillon de test |
|---|---:|
| `tx_fee_eth_sum` | 0.135429 |
| `sessions_cnt` | 0.079593 |
| `internal_in_value_eth_sum` | 0.077054 |
| `internal_out_value_eth_sum` | 0.065492 |
| `erc20_unique_tokens_recv` | 0.060746 |
| `gas_used_sum` | 0.051923 |
| `burst_max_tx_5m` | 0.051276 |
| `active_span_min` | 0.051157 |
| `uniq_peers_cnt` | 0.039151 |
| `normal_to_contract_cnt` | 0.035783 |

SHAP décrit les contributions du modèle relativement au fond d'entraînement ; ce n'est pas une explication causale.

Les caractéristiques sont agrégées depuis le parquet mensuel publié. L'API
récupère les historiques natifs, internes et ERC-20 ; les transferts ERC-721 et
ERC-1155 ne sont pas introduits dans les colonnes ERC-20. Les 26
caractéristiques comportementales et `is_contract` sont dans le même ordre de
colonnes à l'entraînement et à l'inférence, et le même `signed_log1p` est
appliqué. Les unités et les agrégations live sont décrites dans
`ethereum_feature_contract.md`. L'équivalence sémantique complète ne peut pas
être prouvée à partir des seuls fichiers du dataset : les définitions de
génération historique sont incomplètes, et les types de contrats live sont
calculés à l'état RPC actuel, non historique.
