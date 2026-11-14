param(
  [switch]$Init,
  [string]$Summary = "",
  [string]$RequirementsPath = "docs\stack-requirements.json"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Write-GapHighlight([string]$TechName, [string]$Message) {
  Write-Host ""
  Write-Host " REQUIREMENTS GAP " -NoNewline -ForegroundColor Black -BackgroundColor Yellow
  Write-Host " $TechName " -NoNewline -ForegroundColor Black -BackgroundColor Yellow
  Write-Host ""
  Write-Host $Message -ForegroundColor Yellow
  Write-Host " Add to manifests or update docs/stack-requirements.json before deploy. " -ForegroundColor Yellow
  Write-Host ""
}

function Invoke-StackRequirements {
  param([string[]]$PyArgs)

  $pyCode = 'import sys; print(sys.version_info.major, sys.version_info.minor)'
  $runner = $null
  foreach ($tag in @("3.13", "3.12", "3.11", "3.10", "3.9")) {
    try {
      $null = & py "-$tag" -c $pyCode 2>$null
      if ($LASTEXITCODE -eq 0) {
        $runner = @("py", "-$tag")
        break
      }
    } catch { }
  }
  if (-not $runner) {
    foreach ($bin in @("python3", "python")) {
      if (Get-Command $bin -ErrorAction SilentlyContinue) {
        $runner = @($bin)
        break
      }
    }
  }
  if (-not $runner) {
    Write-Host "ERROR: Python required for stack-requirements" -ForegroundColor Red
    exit 1
  }

  $script = Join-Path $Root "scripts\lib\stack_requirements.py"
  $allArgs = @($script) + $PyArgs
  $proc = & $runner[0] $runner[1..($runner.Length - 1)] @allArgs 2>&1
  $exitCode = $LASTEXITCODE

  foreach ($line in $proc) {
    if ($line -match '^@GAP\|([^|]+)\|([^|]+)\|(.+)$') {
      Write-GapHighlight $Matches[2] $Matches[3]
      continue
    }
    if ($line -match '^@REQ_OK\|(.+)$') {
      Write-Host "REQ OK: $($Matches[1])" -ForegroundColor Green
      continue
    }
    if ($line -match '^@OK\|(.+)$') {
      Write-Host "OK: $($Matches[1])" -ForegroundColor Green
      continue
    }
    if ($line -match '^@WARN\|(.+)$') {
      Write-Host "WARNING: $($Matches[1])" -ForegroundColor Yellow
      continue
    }
    if ($line -match '^@ERR\|(.+)$') {
      Write-Host "ERROR: $($Matches[1])" -ForegroundColor Red
      continue
    }
    if ($line -match '^@INFO\|(.+)$') {
      Write-Host "INFO: $($Matches[1])" -ForegroundColor DarkGray
      continue
    }
    Write-Host $line
  }
  return $exitCode
}

$argsList = @("--requirements", $RequirementsPath)
if ($Init) {
  $argsList += "--init"
  if ($Summary) { $argsList += "--summary"; $argsList += $Summary }
}
$code = Invoke-StackRequirements -PyArgs $argsList
exit $code
