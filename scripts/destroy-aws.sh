#!/usr/bin/env bash
# Remove everything this project created in AWS.
#
# Order matters. The environment is destroyed first, because its state lives in
# the bucket the bootstrap configuration owns: remove the bucket first and
# nothing can be destroyed afterwards except by hand, resource by resource.
#
# The state bucket itself is deliberately NOT destroyed here. It is protected,
# it holds the history of every apply, and it costs fractions of a cent. Ending
# it is a separate, deliberate act; the closure note explains how.
#
# Usage:
#   scripts/destroy-aws.sh            # show what would go
#   scripts/destroy-aws.sh --apply    # actually destroy

set -euo pipefail
export AWS_PAGER=""

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ENVIRONMENT_DIR="infra/environments/dev"

if [[ ! -f "$ENVIRONMENT_DIR/backend.hcl" ]]; then
  echo "error: $ENVIRONMENT_DIR/backend.hcl is missing; nothing can be read" >&2
  exit 1
fi

echo "Account:"
aws sts get-caller-identity --query '[Account,Arn]' --output text

echo
echo "Initialising"
terraform -chdir="$ENVIRONMENT_DIR" init -backend-config=backend.hcl -input=false >/dev/null

echo
echo "What would be destroyed:"
terraform -chdir="$ENVIRONMENT_DIR" plan -destroy -input=false -no-color \
  | grep -E "^Plan:|will be destroyed" \
  | sed 's/^/  /'

if (( ! APPLY )); then
  echo
  echo "Nothing was changed. Re-run with --apply to destroy."
  exit 0
fi

cat <<'WARNING'

This removes, permanently:

  - the supplier documents bucket and everything in it
  - the user pool, and both operator accounts
  - the job queue and its dead-letter queue
  - the container registry repositories
  - the IAM roles, the network, the secret containers and the budget

Stored documents and accounts are not recoverable.

WARNING

read -r -p "Type the account id to continue: " confirmation
expected="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$confirmation" != "$expected" ]]; then
  echo "Stopped: that is not this account." >&2
  exit 1
fi

terraform -chdir="$ENVIRONMENT_DIR" destroy -input=false -auto-approve

echo
echo "The environment is gone. The state bucket remains, holding the history"
echo "and the ability to recreate. See the closure note to end that too."
