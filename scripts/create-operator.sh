#!/usr/bin/env bash
# Create an operator account in a Cognito user pool and put it in a role group.
#
# Sign-in messages are suppressed and the password is set directly, so no mail
# is ever sent to the address. Re-running for an existing account updates the
# group membership and the password instead of failing.
#
# Usage:
#   scripts/create-operator.sh <pool-id> <email> <reviewer|viewer> [password]
#
# With no password, one is generated and printed once.

set -euo pipefail
export AWS_PAGER=""

POOL_ID="${1:?a user pool id is required}"
EMAIL="${2:?an email address is required}"
GROUP="${3:?a group is required: reviewer or viewer}"
PASSWORD="${4:-}"

case "$GROUP" in
  reviewer | viewer) ;;
  *)
    echo "group must be reviewer or viewer, got '$GROUP'" >&2
    exit 2
    ;;
esac

if [[ -z "$PASSWORD" ]]; then
  # The pool requires at least 12 characters with mixed case, a digit and a
  # symbol. The random part is captured whole rather than piped through `head`,
  # which would raise SIGPIPE and abort the script under `pipefail`.
  RANDOM_PART="$(openssl rand -base64 24 | tr -d '/+=[:space:]')"
  PASSWORD="${RANDOM_PART:0:20}#aA1"
fi

if aws cognito-idp admin-get-user \
  --user-pool-id "$POOL_ID" --username "$EMAIL" >/dev/null 2>&1; then
  echo "account already exists: $EMAIL"
else
  aws cognito-idp admin-create-user \
    --user-pool-id "$POOL_ID" \
    --username "$EMAIL" \
    --user-attributes "Name=email,Value=$EMAIL" "Name=email_verified,Value=true" \
    --message-action SUPPRESS >/dev/null
  echo "created account: $EMAIL"
fi

aws cognito-idp admin-set-user-password \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --password "$PASSWORD" \
  --permanent

aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --group-name "$GROUP"

echo "group:    $GROUP"
echo "password: $PASSWORD"
echo "Store the password now; it is not recoverable from here."
