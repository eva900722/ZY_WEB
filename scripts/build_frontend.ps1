param([switch]$Install)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    $nodeDirectoryFile = Join-Path $root '.tools/node-directory.txt'
    if (-not (Test-Path -LiteralPath $nodeDirectoryFile)) { throw '請安裝Node.js 24 LTS後重試。' }
    $portableName = (Get-Content -LiteralPath $nodeDirectoryFile -Raw).Trim()
    if ($portableName -notmatch '^node-v[0-9.]+-win-x64$') { throw 'Node便攜目錄名稱不正確。' }
    $env:Path = (Join-Path $root ('.tools/' + $portableName)) + ';' + $env:Path
}
$env:NODE_USE_SYSTEM_CA = '1'
Push-Location (Join-Path $root 'frontend')
try {
    if ($Install -or -not (Test-Path -LiteralPath 'node_modules')) {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw '前端依賴安裝失敗' }
    }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw '前端建置失敗' }
    Write-Output 'Vue/PWA已建置，使用backend/manage.py runserver開啟本機網站。'
} finally { Pop-Location }
