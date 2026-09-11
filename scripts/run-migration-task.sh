#!/usr/bin/env bash
# Apply the schema once, before any service moves.
#
# A migration in a container's start-up races every other task starting at the
# same moment, and a failure becomes a crash loop instead of a stopped
# rollout. This runs one task, waits for it, and reports its exit code.
#
# Required: CLUSTER, TASK_FAMILY, SUBNETS, SECURITY_GROUP.

set -euo pipefail
export AWS_PAGER=""

CLUSTER="${CLUSTER:?a cluster is required}"
TASK_FAMILY="${TASK_FAMILY:?a task family is required}"
SUBNETS="${SUBNETS:?at least one subnet is required}"
SECURITY_GROUP="${SECURITY_GROUP:?a security group is required}"

network="awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUP}],assignPublicIp=DISABLED}"

echo "Starting the migration task"
task_arn="$(
  aws ecs run-task \
    --cluster "$CLUSTER" \
    --task-definition "$TASK_FAMILY" \
    --launch-type FARGATE \
    --network-configuration "$network" \
    --started-by "deploy-${GITHUB_SHA:-manual}" \
    --query 'tasks[0].taskArn' \
    --output text
)"

if [[ -z "$task_arn" || "$task_arn" == "None" ]]; then
  echo "error: the task did not start" >&2
  exit 1
fi

echo "Waiting for $task_arn"
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$task_arn"

read -r exit_code reason < <(
  aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$task_arn" \
    --query 'tasks[0].containers[0].[exitCode,reason]' --output text
)

if [[ "$exit_code" != "0" ]]; then
  echo "error: the migration failed (exit ${exit_code}): ${reason}" >&2
  echo "The previous version keeps running against the previous schema." >&2
  exit 1
fi

echo "Schema is current"
