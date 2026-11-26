#!/usr/bin/env bash
# ------------------------------------------------------------------
# Creates the "ekswithavinash" EKS cluster.
# Works on: macOS (Intel + Apple Silicon), Linux, and Windows via
#           Git Bash / WSL. For native Windows PowerShell, use
#           eks-daily-create.ps1 in this folder instead.
#
# Run manually:
#   bash eks-daily-create.sh
#   DRY_RUN=1 bash eks-daily-create.sh   # checks everything, creates nothing
#
# Schedule (macOS/Linux cron, Mon-Fri 19:15 local time):
#   crontab -e
#   15 19 * * 1-5 /bin/bash "/full/path/eks-daily-create.sh" >> "$HOME/eks-daily-create.log" 2>&1
# ------------------------------------------------------------------

CLUSTER_NAME="ekswithavinash"
REGION="ap-south-1"

# --- Work out which OS we are on ---
case "$(uname -s)" in
    Darwin)               OS="macos" ;;
    Linux)                OS="linux" ;;
    MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
    *)                    OS="unknown" ;;
esac

# Cron runs with a minimal environment and does NOT load your shell
# profile, so add the usual install locations to PATH. Only folders
# that exist are added, and the existing PATH is kept after them.
EXTRA_PATHS=""
case "$OS" in
    macos)
        # On Apple Silicon, Homebrew's arm64 tools must win over any old
        # Intel binaries in /usr/local/bin ("Bad CPU type in executable").
        if [ "$(uname -m)" = "arm64" ]; then
            EXTRA_PATHS="/opt/homebrew/bin:/usr/local/bin"
        else
            EXTRA_PATHS="/usr/local/bin:/opt/homebrew/bin"
        fi
        ;;
    linux)
        EXTRA_PATHS="$HOME/.local/bin:/usr/local/bin:/home/linuxbrew/.linuxbrew/bin"
        ;;
    windows)
        # Typical installs: AWS CLI MSI, Chocolatey, Scoop, winget links.
        EXTRA_PATHS="/c/Program Files/Amazon/AWSCLIV2:/c/ProgramData/chocolatey/bin:$HOME/scoop/shims:$HOME/AppData/Local/Microsoft/WinGet/Links"
        ;;
esac
NEW_PATH=""
IFS=':'
for dir in $EXTRA_PATHS; do
    [ -d "$dir" ] && NEW_PATH="${NEW_PATH:+$NEW_PATH:}$dir"
done
unset IFS
export PATH="${NEW_PATH:+$NEW_PATH:}$PATH:/usr/bin:/bin:/usr/sbin:/sbin"

# HOME is set by cron and by Git Bash; the AWS CLI finds ~/.aws on its own.
export AWS_PROFILE="${AWS_PROFILE:-default}"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
fail() {
    echo "ERROR: $1"
    [ -n "$2" ] && echo "$2"
    echo "END (failed preflight): $(ts)"
    exit 1
}

echo "=================================================="
echo "START: $(ts)   (OS: $OS)"
echo "=================================================="

# --- Preflight: are eksctl and aws on PATH, and do they actually run? ---
for tool in eksctl aws; do
    command -v "$tool" >/dev/null 2>&1 \
        || fail "$tool not found on PATH." "PATH is: $PATH"
done
if ! EKSCTL_VERSION="$(eksctl version 2>&1)"; then
    fail "eksctl at $(command -v eksctl) will not run:" "$EKSCTL_VERSION
On Apple Silicon this usually means an Intel build. Fix: brew install eksctl"
fi
echo "Using eksctl $EKSCTL_VERSION at: $(command -v eksctl)"
echo "Using aws at: $(command -v aws)"

# --- Preflight: are AWS credentials working? ---
if ! IDENTITY="$(aws sts get-caller-identity --query Arn --output text 2>&1)"; then
    fail "AWS credentials not working for profile '$AWS_PROFILE'." "$IDENTITY"
fi
echo "AWS identity: $IDENTITY"

# --- Stop early if the cluster already exists ---
# A real "not found" is fine; any other error (network, permissions)
# is reported instead of being mistaken for "no cluster".
if STATUS="$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" \
        --query cluster.status --output text 2>&1)"; then
    fail "cluster '$CLUSTER_NAME' already exists in $REGION (status: $STATUS)." \
         "Delete it first with: eksctl delete cluster --name $CLUSTER_NAME --region $REGION"
elif ! echo "$STATUS" | grep -q "ResourceNotFoundException"; then
    fail "could not check whether '$CLUSTER_NAME' exists:" "$STATUS"
fi

CREATE_CMD=(eksctl create cluster
    --name "$CLUSTER_NAME"
    --version 1.36
    --region "$REGION"
    --zones=ap-south-1a,ap-south-1b
    --nodegroup-name mycustomng
    --nodes 2
    --node-type c7i-flex.large
    --node-ami-family=AmazonLinux2023
    --managed)

echo "--------------------------------------------------"
if [ -n "$DRY_RUN" ]; then
    echo "DRY RUN - would run:"
    echo "  ${CREATE_CMD[*]}"
    echo "END (dry run): $(ts)"
    exit 0
fi
echo "Running eksctl create cluster..."
echo "--------------------------------------------------"

"${CREATE_CMD[@]}"
EXIT_CODE=$?

echo "=================================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS: cluster created."
else
    echo "FAILED: eksctl exited with code $EXIT_CODE"
fi
echo "END: $(ts)"
echo "=================================================="
echo ""

exit $EXIT_CODE
