# ------------------------------------------------------------------
# Creates the "ekswithavinash" EKS cluster - Windows PowerShell version.
# Works in Windows PowerShell 5.1 and PowerShell 7+.
# (macOS/Linux/Git Bash: use eks-daily-create.sh instead.)
#
# Run manually:
#   powershell -ExecutionPolicy Bypass -File .\eks-daily-create.ps1
#   powershell -ExecutionPolicy Bypass -File .\eks-daily-create.ps1 -DryRun
#
# Schedule (Task Scheduler, Mon-Fri 19:15 local time) - run once in PowerShell:
#   $script = "C:\full\path\eks-daily-create.ps1"
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#              -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"& '$script' *>> `$env:USERPROFILE\eks-daily-create.log`""
#   $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 7:15PM
#   Register-ScheduledTask -TaskName "EKS Daily Create" -Action $action -Trigger $trigger
# ------------------------------------------------------------------

param([switch]$DryRun)

$ClusterName = "ekswithavinash"
$Region      = "ap-south-1"

# Scheduled tasks may not see PATH changes made after login, so add the
# usual install locations (only the ones that exist).
$extra = @(
    "$env:ProgramFiles\Amazon\AWSCLIV2",
    "$env:ProgramData\chocolatey\bin",
    "$env:USERPROFILE\scoop\shims",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
) | Where-Object { Test-Path $_ }
if ($extra) { $env:PATH = ($extra -join ";") + ";" + $env:PATH }

if (-not $env:AWS_PROFILE) { $env:AWS_PROFILE = "default" }

function Ts { Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz" }
function Fail([string]$msg, [string]$detail) {
    Write-Output "ERROR: $msg"
    if ($detail) { Write-Output $detail }
    Write-Output "END (failed preflight): $(Ts)"
    exit 1
}

Write-Output "=================================================="
Write-Output "START: $(Ts)   (OS: windows)"
Write-Output "=================================================="

# --- Preflight: are eksctl and aws on PATH, and do they actually run? ---
foreach ($tool in "eksctl", "aws") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Fail "$tool not found on PATH." "PATH is: $env:PATH"
    }
}
$eksctlVersion = (& eksctl version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Fail "eksctl will not run:" $eksctlVersion }
Write-Output "Using eksctl $eksctlVersion at: $((Get-Command eksctl).Source)"
Write-Output "Using aws at: $((Get-Command aws).Source)"

# --- Preflight: are AWS credentials working? ---
$identity = (& aws sts get-caller-identity --query Arn --output text 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Fail "AWS credentials not working for profile '$env:AWS_PROFILE'." $identity }
Write-Output "AWS identity: $identity"

# --- Stop early if the cluster already exists ---
$status = (& aws eks describe-cluster --name $ClusterName --region $Region `
           --query cluster.status --output text 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -eq 0) {
    Fail "cluster '$ClusterName' already exists in $Region (status: $status)." `
         "Delete it first with: eksctl delete cluster --name $ClusterName --region $Region"
} elseif ($status -notmatch "ResourceNotFoundException") {
    Fail "could not check whether '$ClusterName' exists:" $status
}

$createArgs = @(
    "create", "cluster",
    "--name", $ClusterName,
    "--version", "1.36",
    "--region", $Region,
    "--zones=ap-south-1a,ap-south-1b",
    "--nodegroup-name", "mycustomng",
    "--nodes", "2",
    "--node-type", "c7i-flex.large",
    "--node-ami-family=AmazonLinux2023",
    "--managed"
)

Write-Output "--------------------------------------------------"
if ($DryRun) {
    Write-Output "DRY RUN - would run:"
    Write-Output "  eksctl $($createArgs -join ' ')"
    Write-Output "END (dry run): $(Ts)"
    exit 0
}
Write-Output "Running eksctl create cluster..."
Write-Output "--------------------------------------------------"

& eksctl @createArgs
$exitCode = $LASTEXITCODE

Write-Output "=================================================="
if ($exitCode -eq 0) {
    Write-Output "SUCCESS: cluster created."
} else {
    Write-Output "FAILED: eksctl exited with code $exitCode"
}
Write-Output "END: $(Ts)"
Write-Output "=================================================="
Write-Output ""

exit $exitCode
