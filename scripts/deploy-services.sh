#!/usr/bin/env bash
# Roll each service onto the newest task definition and wait for it to settle.
#
# A rollout that is not waited on is a deployment nobody verified. A service
# that will not stabilise fails the run, so the pipeline reports what actually
# happened rather than what it asked for.
#
# Required: CLUSTER, SERVICES (space or comma separated).

set -euo pipefail
export AWS_PAGER=""

CLUSTER="${CLUSTER:?a cluster is required}"
SERVICES="${SERVICES:?at least one service is required}"

read -r -a services <<< "${SERVICES//,/ }"

for service in "${services[@]}"; do
  echo "Rolling $service"
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$service" \
    --force-new-deployment >/dev/null
done

failed=0
for service in "${services[@]}"; do
  echo "Waiting for $service"
  if ! aws ecs wait services-stable --cluster "$CLUSTER" --services "$service"; then
    echo "error: $service did not become stable" >&2
    aws ecs describe-services --cluster "$CLUSTER" --services "$service" \
      --query 'services[0].events[:5].message' --output text >&2 || true
    failed=1
  fi
done

if (( failed )); then
  echo "Deploy the previous commit to go back." >&2
  exit 1
fi

echo "Every service is stable"
