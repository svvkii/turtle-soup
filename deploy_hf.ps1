# 一键部署到 Hugging Face Space（Docker SDK）
# 用法: .\deploy_hf.ps1 -Space 你的用户名/turtle-soup [-Dir space]
param(
    [Parameter(Mandatory = $true)]
    [string]$Space,
    [string]$Dir = "space"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "未检测到 git，请先安装: https://git-scm.com/download/win"
    exit 1
}

$url = "https://huggingface.co/spaces/$Space"

if (Test-Path (Join-Path $Dir ".git")) {
    Write-Host "[1/4] 复用本地仓库 $Dir，拉取最新..." -ForegroundColor Cyan
    git -C $Dir pull
} else {
    if (Test-Path $Dir) { Remove-Item -Recurse -Force $Dir }
    Write-Host "[1/4] 克隆 Space 仓库..." -ForegroundColor Cyan
    git clone $url $Dir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "克隆失败：请确认 Space 已创建，且本机有 HF 推送权限" -ForegroundColor Red
        Write-Host "（密码处粘贴 HF Access Token，需 write 权限: https://huggingface.co/settings/tokens）"
        exit 1
    }
}

Write-Host "[2/4] 复制项目文件（排除 .venv/.env/测试）..." -ForegroundColor Cyan
robocopy . $Dir /E `
    /XD .venv __pycache__ .git $Dir space `
    /XF .env deploy_hf.ps1 multi_test.py smoke_test.py `
    /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy 失败 (code=$LASTEXITCODE)"
    exit 1
}

Push-Location $Dir
Write-Host "[3/4] 提交..." -ForegroundColor Cyan
git add -A
git commit -m "deploy: turtle soup web" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "（无变更，跳过提交）" }

Write-Host "[4/4] 推送到 HF..." -ForegroundColor Cyan
git push
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败：密码处需粘贴 HF Access Token（write 权限）" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Host ""
Write-Host "✅ 已推送！查看构建: https://huggingface.co/spaces/$Space" -ForegroundColor Green
Write-Host "上线后地址: https://$($Space -replace '/','-').hf.space" -ForegroundColor Green
Write-Host "别忘记在 Space Settings -> Variables and secrets 配置 OPENAI_API_KEY 等环境变量（见 DEPLOY.md 第 3 步）"
