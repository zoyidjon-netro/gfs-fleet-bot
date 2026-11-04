$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
$runner = Join-Path $workspace 'run_background.py'
$command = '"' + $pythonw + '" "' + $runner + '"'
New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'GfsSpeakerBot' -Value $command -PropertyType String -Force | Out-Null
Start-Process -FilePath $pythonw -ArgumentList ('"' + $runner + '"') -WorkingDirectory $workspace -WindowStyle Hidden
Write-Output 'GFS background supervisor enabled for this Windows account.'
