$ErrorActionPreference = 'Continue'
$root = 'E:\EDR\EDRTest\automation'
Set-Location $root
$cases = 'FILE-CREATE-001','FILE-OPEN-001','FILE-DELETE-001','FILE-MODIFY-001','FILE-RENAME-001'
$logDir = Join-Path $root 'file_rerun_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$out = Join-Path $logDir 'batch_run.log'
"=== batch start $(Get-Date -Format o) ===" | Out-File $out -Encoding utf8
foreach ($c in $cases) {
  "[$(Get-Date -Format 'HH:mm:ss')] running $c" | Out-File $out -Append -Encoding utf8
  python runner\telemetry_runner.py run --case $c >> $out 2>&1
  "[$(Get-Date -Format 'HH:mm:ss')] done $c exit=$LASTEXITCODE" | Out-File $out -Append -Encoding utf8
}
"=== batch end $(Get-Date -Format o) ===" | Out-File $out -Append -Encoding utf8
