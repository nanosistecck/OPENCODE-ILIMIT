$ErrorActionPreference = 'SilentlyContinue'

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Py      = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python315\python.exe'
$Url     = 'http://localhost:5173'

Write-Host ''
Write-Host '  =========================================='
Write-Host '   OPENCODE ILIMIT - iniciar projeto'
Write-Host '  =========================================='
Write-Host ''

# ---------- backend ----------
$backendProc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*uvicorn*app.main:app*' }

if (-not $backendProc) {
    Write-Host '  [1/3] Iniciando backend (127.0.0.1:8000)...'
    Start-Process -FilePath $Py `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory $Backend -WindowStyle Minimized | Out-Null
} else {
    Write-Host '  [1/3] Backend ja esta ativo.'
}

# ---------- frontend ----------
$frontendProc = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like '*vite*' -and $_.CommandLine -like '*OPENCODE-ILIMIT*' }

if (-not $frontendProc) {
    Write-Host '  [2/3] Iniciando frontend (127.0.0.1:5173)...'
    $node = (Get-Command node).Source
    $vite = Join-Path $Root 'node_modules\vite\bin\vite.js'
    Start-Process -FilePath $node `
        -ArgumentList "`"$vite`"", '--host', '127.0.0.1', '--port', '5173' `
        -WorkingDirectory $Root -WindowStyle Minimized | Out-Null
} else {
    Write-Host '  [2/3] Frontend ja esta ativo.'
}

# ---------- espera o servidor responder ----------
Write-Host '  [3/3] Aguardando o frontend responder...'
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host ''
    Write-Host '  AVISO: o frontend nao respondeu em 20s.'
    Write-Host '  Verifique as janelas minimizadas do backend e do Vite.'
    Write-Host ''
    Read-Host '  Pressione Enter para sair'
    exit 1
}

# ---------- abre o navegador ----------
Start-Process $Url
Write-Host ''
Write-Host "  Pronto! Navegador aberto em $Url"
Write-Host '  Para parar: feche as janelas minimizadas do backend e do Vite.'
Write-Host ''
