param(
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 8000,

    [ValidateRange(1, 65535)]
    [int]$RpcPort = 8545
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$hardhatCli = Join-Path $projectRoot "node_modules\hardhat\dist\src\cli.js"
$rpcUrl = "http://127.0.0.1:$RpcPort"

Set-Location $projectRoot

if (-not (Test-Path $python)) {
    throw "Python not found: $python. Create the .venv environment before starting."
}

if (-not (Test-Path $hardhatCli)) {
    throw "Hardhat not found. Run npm install from the project root."
}

function Test-HardhatRpc {
    try {
        $response = Invoke-RestMethod `
            -Uri $rpcUrl `
            -Method Post `
            -ContentType "application/json" `
            -Body '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' `
            -TimeoutSec 2

        return $response.result -eq "0x7a69"
    }
    catch {
        return $false
    }
}

if (-not (Test-HardhatRpc)) {
    $logPrefix = Join-Path $env:TEMP "blockchain-fraud-detection-hardhat-$PID"
    $stdoutLog = "$logPrefix.out.log"
    $stderrLog = "$logPrefix.err.log"
    $nodeArguments = '"{0}" node --hostname 127.0.0.1 --port {1}' -f $hardhatCli, $RpcPort

    Write-Host "Starting Hardhat node at $rpcUrl..."
    $nodeProcess = Start-Process `
        -FilePath "node.exe" `
        -ArgumentList $nodeArguments `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru

    $rpcReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($nodeProcess.HasExited) {
            $nodeOutput = ""
            if (Test-Path $stderrLog) {
                $nodeOutput = Get-Content $stderrLog -Raw
            }
            throw "Hardhat node exited during startup. $nodeOutput"
        }

        if (Test-HardhatRpc) {
            $rpcReady = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $rpcReady) {
        throw "Hardhat node did not respond at $rpcUrl after 60 seconds. Logs: $stdoutLog and $stderrLog"
    }
}
else {
    Write-Host "Hardhat node already available at $rpcUrl."
}

$env:BLOCKCHAIN_RPC_URL = $rpcUrl
Write-Host "Deploying TransactionAlerts..."
$deploymentOutput = & node $hardhatCli run .\ignition\deploy-transaction-alerts.ts --network localhost 2>&1
if ($LASTEXITCODE -ne 0) {
    $deploymentOutput | ForEach-Object { Write-Host $_ }
    throw "Contract deployment failed."
}

$deploymentText = $deploymentOutput -join "`n"
$addressMatch = [regex]::Match(
    $deploymentText,
    "CONTRACT_ADDRESS=(0x[a-fA-F0-9]{40})"
)
if (-not $addressMatch.Success) {
    $deploymentOutput | ForEach-Object { Write-Host $_ }
    throw "Deployment script did not return a contract address."
}

$env:BLOCKCHAIN_CONTRACT_ADDRESS = $addressMatch.Groups[1].Value

Write-Host "Contract ready: $env:BLOCKCHAIN_CONTRACT_ADDRESS"
Write-Host "API available at http://127.0.0.1:$ApiPort. Keep this window open."
& $python -m uvicorn api:app --host 127.0.0.1 --port $ApiPort --reload
exit $LASTEXITCODE
