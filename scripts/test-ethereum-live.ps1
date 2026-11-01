param(
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$baseUrl = $ApiUrl.TrimEnd("/")

try {
    $status = Invoke-RestMethod -Uri "$baseUrl/api/status" -TimeoutSec 10
}
catch {
    throw "API unavailable at $baseUrl. Start it with the configured mainnet environment first."
}

if (-not $status.modele_ethereum_charge -or -not $status.analyseur_ethereum_disponible) {
    throw "Ethereum model or SHAP explainer is unavailable. Check /api/status."
}
if (-not $status.ethereum_provider_configured) {
    throw "Configure ETHERSCAN_API_KEY and ETHEREUM_RPC_URL in the API process before this test."
}

$address = Read-Host "Public Ethereum mainnet address with transaction history"
if ($address -notmatch '^0x[0-9a-fA-F]{40}$') {
    throw "Invalid Ethereum address format."
}

$requestBody = @{
    address = $address
    autoriser_enregistrement_alerte = $false
} | ConvertTo-Json -Compress

try {
    $result = Invoke-RestMethod `
        -Uri "$baseUrl/api/ethereum/analyze" `
        -Method Post `
        -ContentType "application/json" `
        -Body $requestBody `
        -TimeoutSec 300
}
catch {
    $apiError = $_.ErrorDetails.Message
    if ($apiError) {
        throw "Live Ethereum analysis failed: $apiError"
    }
    throw "Live Ethereum analysis failed: $($_.Exception.Message)"
}

if ($result.blockchain_enregistre) {
    throw "Safety check failed: the read-only test unexpectedly reports an on-chain alert."
}
if ($result.source_features.reseau -ne "Ethereum mainnet (chain ID 1)") {
    throw "The API response is not explicitly identified as Ethereum mainnet data."
}
if (-not $result.source_features -or $result.explications_shap.Count -lt 1) {
    throw "The API response is missing live feature counts or SHAP explanations."
}

$classification = if ($result.classe_predite -eq 1) {
    "Risque détecté (estimation expérimentale)"
}
else {
    "Risque non détecté par le modèle"
}

Write-Host "Analyse Ethereum mainnet terminée (données Etherscan/RPC, pas la démo synthétique)."
Write-Host "Adresse : $($result.adresse)"
Write-Host "Analyse locale enregistrée : #$($result.id_analyse)"
Write-Host "Classe : $classification"
Write-Host "Score de risque : $($result.score_risque_sur_100)/100"
Write-Host "Transactions normales : $($result.source_features.transactions_normales)"
Write-Host "Transactions internes : $($result.source_features.transactions_internes)"
Write-Host "Transferts ERC-20 : $($result.source_features.transferts_erc20)"
Write-Host "Explications SHAP : $($result.explications_shap.Count)"
foreach ($explanation in $result.explications_shap) {
    Write-Host "  $($explanation.feature) : contribution=$($explanation.contribution), valeur=$($explanation.value)"
}
Write-Host "Alerte on-chain : non envoyée (autorisation explicitement désactivée)."
Write-Host "Cette analyse réelle est ajoutée à l'historique SQLite local."
Write-Host "Avertissement : $($result.avertissement)"
