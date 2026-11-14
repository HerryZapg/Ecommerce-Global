param(
  [switch]$Yes,
  [switch]$Strict
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($env:CI -eq "true" -or $env:CHECK_ENV_CI -eq "1") {
  $Yes = $true
}

function Write-Ctx7Highlight([string]$TechName, [string]$Message) {
  Write-Host ""
  Write-Host " CONTEXT7 " -NoNewline -ForegroundColor Black -BackgroundColor Yellow
  Write-Host " $TechName " -NoNewline -ForegroundColor Black -BackgroundColor Yellow
  Write-Host ""
  Write-Host $Message -ForegroundColor Yellow
  Write-Host " Investigate official docs before confirming deployment. " -ForegroundColor Yellow
  Write-Host ""
}

function Invoke-StackCheck {
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
    Write-Host "ERROR: Python required to run stack preflight (scripts/lib/stack_check.py)" -ForegroundColor Red
    exit 1
  }

  $script = Join-Path $Root "scripts\lib\stack_check.py"
  $allArgs = @($script) + $PyArgs
  $proc = & $runner[0] $runner[1..($runner.Length - 1)] @allArgs 2>&1
  $exitCode = $LASTEXITCODE

  foreach ($line in $proc) {
    if ($line -match '^@CTX7\|([^|]+)\|([^|]+)\|(.+)$') {
      Write-Ctx7Highlight $Matches[2] $Matches[3]
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

$argsList = @()
if ($Yes) { $argsList += "-y" }
if ($Strict) { $argsList += "--strict" }
if ($env:CHECK_ENV_CI -eq "1" -or $env:CI -eq "true") { $argsList += "--ci" }

$code = Invoke-StackCheck -PyArgs $argsList
exit $code
