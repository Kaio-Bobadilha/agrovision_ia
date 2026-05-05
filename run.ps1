# Script para executar o AgroVision
param(
    [switch]$Foreground
)

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectDir ".venv\Scripts\Activate.ps1"
$uvicornExe = Join-Path $projectDir ".venv\Scripts\uvicorn.exe"

# Ativar ambiente virtual
& $venvPath

function Get-PortOwnerProcess {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    }
    return $null
}

function Stop-ExistingPortOwner {
    param([int]$Port)
    $proc = Get-PortOwnerProcess -Port $Port
    if ($proc) {
        if ($proc.ProcessName -match 'python|uvicorn') {
            Write-Host "Port $Port is already in use by process $($proc.ProcessName) (PID $($proc.Id)). Stopping it..."
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            return $true
        }
        Write-Warning "Port $Port is already in use by another process ($($proc.ProcessName) PID $($proc.Id)). Please free the port or change the port in run.ps1."
        return $false
    }
    return $true
}

# Free port 8001 if an old uvicorn/python instance is still running
if (-not (Stop-ExistingPortOwner -Port 8001)) {
    exit 1
}

# Verificar se Ollama está rodando
$ollamaProcess = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProcess) {
    Write-Host "Iniciando Ollama..."
    Start-Process ollama -ArgumentList "serve" -NoNewWindow
    Start-Sleep -Seconds 5
}

# Verificar modelo
Write-Host "Verificando modelo tinyllama..."
ollama pull tinyllama

if ($Foreground) {
    Write-Host "Iniciando FastAPI (uvicorn) em foreground..."
    Write-Host "Use Ctrl + C para encerrar o servidor."
    try {
        & $uvicornExe "app.main:app" "--host" "127.0.0.1" "--port" "8001" "--reload"
    } finally {
        if ($ollamaProcess) {
            Stop-Process -Id $ollamaProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "Iniciando FastAPI em background..."
    $job = Start-Job -ScriptBlock {
        param($uvicornExe, $projectDir)
        Set-Location $projectDir
        & $uvicornExe "app.main:app" "--host" "127.0.0.1" "--port" "8001" "--reload"
    } -ArgumentList $uvicornExe, $projectDir

    Write-Host "Servidor iniciado. Acesse http://127.0.0.1:8001"
    Write-Host "Para parar: Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)"
}