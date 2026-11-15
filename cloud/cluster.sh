#!/bin/bash
# Керування кластером:
#   bash cloud/cluster.sh status   # VM + зареєстровані воркери
#   bash cloud/cluster.sh ip       # публічна IP master'а
#   bash cloud/cluster.sh stop     # зупинити VM (CPU не тарифікується)
#   bash cloud/cluster.sh start    # запустити знову
#   bash cloud/cluster.sh delete   # видалити VM і security group
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh

ids() {
  awsq ec2 describe-instances \
    --filters Name=tag:Project,Values="$PROJECT_TAG" Name=instance-state-name,Values="${1:-pending,running,stopping,stopped}" \
    --query 'Reservations[].Instances[].InstanceId' --output text
}

master_ip() {
  awsq ec2 describe-instances \
    --filters Name=tag:Project,Values="$PROJECT_TAG" Name=tag:Role,Values=master Name=instance-state-name,Values=running \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
}

sg_id() {
  awsq ec2 describe-security-groups --filters Name=group-name,Values="$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' --output text
}

case "${1:-status}" in
  status)
    aws ec2 describe-instances --filters Name=tag:Project,Values="$PROJECT_TAG" \
      Name=instance-state-name,Values=pending,running,stopping,stopped \
      --query 'sort_by(Reservations[].Instances[], &Tags[?Key==`Name`]|[0].Value)[].{Name:Tags[?Key==`Name`]|[0].Value,Id:InstanceId,Type:InstanceType,State:State.Name,PrivateIP:PrivateIpAddress,PublicIP:PublicIpAddress}' \
      --output table
    curl -fs --max-time 5 "http://$(master_ip):8080/api/worker" || echo "master ще не відповідає"
    echo ;;
  ip) master_ip ;;
  stop) aws ec2 stop-instances --instance-ids $(ids running) --query 'StoppingInstances[].InstanceId' --output text ;;
  start)
    aws ec2 start-instances --instance-ids $(ids stopped) --query 'StartingInstances[].InstanceId' --output text
    aws ec2 wait instance-running --instance-ids $(ids)
    # публічна IP змінюється після зупинки; ваша IP могла теж змінитись — додаємо доступ
    aws ec2 authorize-security-group-ingress --group-id "$(sg_id)" --protocol tcp --port 8080 \
      --cidr "$(curl -fs https://checkip.amazonaws.com | tr -d '\r\n')/32" >/dev/null 2>&1 || true
    echo "Master: http://$(master_ip):8080/workers" ;;
  delete)
    ALL="$(ids)"
    if [ -n "$ALL" ]; then
      aws ec2 terminate-instances --instance-ids $ALL --query 'TerminatingInstances[].InstanceId' --output text
      aws ec2 wait instance-terminated --instance-ids $ALL
    fi
    SG="$(sg_id)"
    [ "$SG" = "None" ] || aws ec2 delete-security-group --group-id "$SG"
    echo "Кластер видалено" ;;
  *) echo "usage: $0 status|ip|stop|start|delete"; exit 1 ;;
esac
