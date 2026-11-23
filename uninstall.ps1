# Removes HornVoice (the app, its shortcuts). Pass -Data to also delete your settings, log and the downloaded speech model.
param([switch]$Data)
$ErrorActionPreference = 'Continue'
Get-Process hornvoice-gui, hornvoice -ErrorAction SilentlyContinue | Stop-Process -Force
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($uv) { & $uv tool uninstall hornvoice }
foreach ($dir in 'Programs', 'Startup') {
  $p = Join-Path ([Environment]::GetFolderPath($dir)) 'HornVoice.lnk'
  if (Test-Path $p) { Remove-Item $p -Force }
}
if ($Data) {
  Remove-Item "$env:APPDATA\HornVoice" -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item "$env:USERPROFILE\.cache\huggingface\hub\models--Systran--faster-whisper-*" -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'HornVoice removed.'
