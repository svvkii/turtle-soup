# 海龟汤一键启动：本地服务 + Cloudflare 公网隧道
# 双击运行（或右键“使用 PowerShell 运行”）
$ErrorActionPreference = "SilentlyContinue"
$dir = $PSScriptRoot
$py = Join-Path $dir ".venv\Scripts\python.exe"
$cf = Join-Path $env:TEMP "opencode\cloudflared.exe"
$cflog = Join-Path $env:TEMP "opencode\cf.log"

Write-Host "== 海龟汤启动器 ==" -ForegroundColor Cyan

# 1) 本地服务
if (-not (Get-NetTCPConnection -LocalPort 7860 -State Listen)) {
    Write-Host "启动服务..." -ForegroundColor Yellow
    $args = '/c cd /d "' + $dir + '" && "' + $py + '" -m uvicorn main:app --host 127.0.0.1 --port 7860 1>"' + $dir + '\server.log" 2>"' + $dir + '\server.err.log"'
    Start-Process -FilePath "cmd.exe" -ArgumentList $args -WindowStyle Hidden
    Start-Sleep -Seconds 7
} else {
    Write-Host "服务已在运行" -ForegroundColor Green
}

# 2) cloudflared
if (-not (Test-Path $cf)) {
    Write-Host "下载 cloudflared..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path (Split-Path $cf) | Out-Null
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $cf
}
if (-not (Get-Process cloudflared)) {
    Write-Host "启动隧道..." -ForegroundColor Yellow
    Remove-Item $cflog -ErrorAction SilentlyContinue
    Start-Process -FilePath $cf `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:7860", "--no-autoupdate", "--logfile", $cflog `
        -WindowStyle Hidden
    Start-Sleep -Seconds 20
} else {
    Write-Host "隧道已在运行" -ForegroundColor Green
}

# 3) 校验并输出地址
try {
    $h = Invoke-RestMethod "http://127.0.0.1:7860/healthz" -TimeoutSec 10
    Write-Host ("服务状态: " + ($h | ConvertTo-Json -Compress)) -ForegroundColor Green
} catch {
    Write-Host "服务未就绪，请查看 server.err.log" -ForegroundColor Red
}
$url = (Select-String -Path $cflog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1).Matches.Value
Write-Host ""
if ($url) {
    Write-Host "本地地址: http://127.0.0.1:7860" -ForegroundColor Green
    Write-Host "公网地址: $url" -ForegroundColor Green
    Write-Host "（把这个公网地址发到微信群）" -ForegroundColor Cyan
} else {
    Write-Host "未取到公网地址，请稍等后重跑本脚本" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
