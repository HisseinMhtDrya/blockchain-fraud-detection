# Contrat des caractéristiques Ethereum

## Schéma et transformations

Le modèle utilise **27 colonnes** dans cet ordre : 26 caractéristiques
comportementales produites par `extract_live_features`, puis `is_contract`.
Le prétraitement sauvegardé applique `sign(x) * log(1 + abs(x))` à chacune,
y compris au drapeau binaire. L'entraîneur et l'analyseur chargent tous deux
`ADDRESS_FEATURES`; l'analyseur refuse un bundle dont les noms ou l'ordre
diffèrent. Le test `test_feature_contract_contains_26_live_features_and_contract_flag`
verrouille cette cardinalité.

| Ordre | Nom | Unité / formule d'inférence | Agrégation à l'échelle de l'adresse |
|---:|---|---|---|
| 1 | `normal_sent_cnt` | Nombre de transactions natives sortantes | Somme |
| 2 | `normal_recv_cnt` | Nombre de transactions natives entrantes | Somme |
| 3 | `normal_total_cnt` | Sortantes + entrantes | Somme journalière |
| 4 | `normal_failed_cnt` | Transactions natives sortantes échouées selon `isError` / statut de reçu | Somme |
| 5 | `normal_to_contract_cnt` | Transactions sortantes vers un contrat selon `eth_getCode(..., latest)` | Somme |
| 6 | `normal_to_eoa_cnt` | Transactions sortantes vers une adresse sans code selon l'état RPC actuel | Somme |
| 7 | `eth_sent_sum` | ETH natif sortant, en ETH (`value` en wei / 10^18) | Somme |
| 8 | `eth_recv_sum` | ETH natif entrant, en ETH | Somme |
| 9 | `eth_net_flow` | `eth_recv_sum - eth_sent_sum`, en ETH | Somme journalière |
| 10 | `tx_fee_eth_sum` | Frais sortants, en ETH (`gasUsed * gasPrice / 10^18`) | Somme |
| 11 | `gas_used_sum` | Gaz utilisé par les transactions sortantes, en unités de gaz | Somme |
| 12 | `erc20_sent_cnt` | Événements de transfert ERC-20 sortants, via `tokentx` | Somme |
| 13 | `erc20_recv_cnt` | Événements de transfert ERC-20 entrants, via `tokentx` | Somme |
| 14 | `erc20_total_cnt` | ERC-20 sortants + entrants | Somme journalière |
| 15 | `erc20_unique_tokens_sent` | Adresses de contrats ERC-20 distinctes sortantes | Distinctes par mois, puis somme des mois |
| 16 | `erc20_unique_tokens_recv` | Adresses de contrats ERC-20 distinctes entrantes | Distinctes par mois, puis somme des mois |
| 17 | `internal_out_cnt` | Transactions internes sortantes réussies de valeur positive | Somme |
| 18 | `internal_in_cnt` | Transactions internes entrantes réussies de valeur positive | Somme |
| 19 | `internal_out_value_eth_sum` | Valeur interne sortante, en ETH | Somme |
| 20 | `internal_in_value_eth_sum` | Valeur interne entrante, en ETH | Somme |
| 21 | `uniq_peers_cnt` | Contreparties distinctes des transactions natives, internes et ERC-20 | Distinctes par mois, puis somme des mois |
| 22 | `uniq_contract_peers_cnt` | Contreparties distinctes classées contrat par l'état RPC courant | Distinctes par mois, puis somme des mois |
| 23 | `uniq_eoa_peers_cnt` | Contreparties distinctes classées EOA par l'état RPC courant | Distinctes par mois, puis somme des mois |
| 24 | `active_span_min` | Pour chaque jour actif, minutes entre le premier et le dernier événement natif/interne | Somme des jours |
| 25 | `burst_max_tx_5m` | Nombre maximal d'événements natifs/internes dans une fenêtre glissante de cinq minutes | Maximum sur l'historique |
| 26 | `sessions_cnt` | Sessions natives/internes séparées par un intervalle strictement supérieur à 30 minutes | Sessions calculées séparément par mois, puis somme |
| 27 | `is_contract` | 1 si `eth_getCode` au bloc `latest` est non vide, sinon 0 | Valeur actuelle, pas une somme |

## Validation de l'équivalence

- L'ordre et la transformation sont partagés entre entraînement et inférence,
  et contrôlés par le bundle et les tests.
- L'entraînement additionne les 25 colonnes mensuelles déclarées additives et
  prend le maximum de `burst_max_tx_5m`. Les données de base publiées ne
  fournissent pas, à elles seules, une définition suffisamment détaillée de
  chaque calcul quotidien/mensuel pour démontrer que l'inférence reconstruit
  exactement le processus de génération du corpus.
- Les champs de type contrat/contrepartie sont observés à l'état RPC actuel,
  alors que les caractéristiques du corpus sont historiques. Le type d'une
  adresse peut donc avoir changé depuis les transactions.
- Les transactions ERC-721 et ERC-1155 ne sont pas incluses dans les
  caractéristiques `erc20_*`; les requêtes ne collectent que `txlist`,
  `txlistinternal` et `tokentx`.
- Les statuts, horodatages, valeurs et adresses manquants ou malformés dans
  les réponses fournisseur sont rejetés (erreur 502), pas remplacés par zéro.
  Une adresse sans activité exploitable n'est pas scorée (erreur 422).
- Un résultat Etherscan vide est traité comme une activité absente. La
  pagination qui atteint la limite de sécurité ou un RPC incomplet interrompt
  l'analyse au lieu de renvoyer un score partiel.

**Conclusion scientifique :** les 27 colonnes et l'ordre du modèle sont
cohérents par construction, et plusieurs unités/agrégations ont été alignées.
L'équivalence sémantique complète avec les colonnes mensuelles publiées n'est
pas prouvée faute de spécification complète de leur génération. Les scores
live demeurent expérimentaux et ne sont ni une preuve de fraude ni une
détection spécifique du blanchiment.
