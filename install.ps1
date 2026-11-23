<#
  HornVoice installer (per-user, no administrator rights).

  One line:
    irm https://raw.githubusercontent.com/KaeghanG/hornvoice/main/install.ps1 | iex

  With start-with-Windows:
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/KaeghanG/hornvoice/main/install.ps1))) -Startup

  What it does: installs uv (a small Python tool manager) if missing, installs HornVoice into its own isolated environment,
  and adds a Start menu shortcut (and, with -Startup, a start-with-Windows shortcut). Uninstall: uninstall.ps1.
#>
param([switch]$Startup, [string]$Source = 'git+https://github.com/KaeghanG/hornvoice')

$ErrorActionPreference = 'Stop'
function Step($m) { Write-Host "==> $m" -ForegroundColor Yellow }

# 1. uv
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
  Step 'Installing uv (Python tool manager)'
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
  if (-not $uv) { throw 'uv installed but is not on PATH yet. Open a new PowerShell window and run this installer again.' }
}

# 2. HornVoice
Step 'Installing HornVoice (Python 3.12 environment, about 300 MB of packages)'
# Windows PowerShell 5.1 turns a native program's normal progress output (stderr) into errors under 'Stop': relax it for this call.
$ErrorActionPreference = 'Continue'
& $uv tool install --python 3.12 --force $Source 2>&1 | ForEach-Object { "$_" } | Write-Host
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($code -ne 0) { throw 'uv tool install failed' }
$bin = (& $uv tool dir --bin).Trim()
$gui = Join-Path $bin 'hornvoice-gui.exe'
if (-not (Test-Path $gui)) { throw "Expected $gui after install" }

# 3. Shortcuts
$shell = New-Object -ComObject WScript.Shell
function Shortcut($path) {
  $l = $shell.CreateShortcut($path)
  $l.TargetPath = $gui
  $l.WorkingDirectory = $env:USERPROFILE
  $l.Description = 'HornVoice: local voice control'
  $l.WindowStyle = 7
  $l.Save()
}
Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'HornVoice.lnk')
Step 'Start menu shortcut created'
if ($Startup) {
  Shortcut (Join-Path ([Environment]::GetFolderPath('Startup')) 'HornVoice.lnk')
  Step 'Will start with Windows'
}

Step 'Done. Launch "HornVoice" from the Start menu, then hold Right Ctrl and speak. The first start downloads the speech model (about 500 MB).'
if (-not (Get-Process hornvoice-gui -ErrorAction SilentlyContinue)) { Start-Process $gui }
