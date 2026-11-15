#!/bin/bash
# Створює security group, parcs-master і parcs-worker-1..WORKERS в AWS EC2.
#   bash cloud/create_cluster.sh
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh

echo "Account: $(awsq sts get-caller-identity --query Account --output text), region $REGION"

VPC="$(awsq ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[ "$VPC" != "None" ] || { echo "Немає default VPC: aws ec2 create-default-vpc"; exit 1; }

# Security group: ноди бачать одна одну повністю (Flask 8080 + випадкові порти Pyro4),
# а веб-інтерфейс master'а доступний лише з вашої IP-адреси
SG="$(awsq ec2 describe-security-groups --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC" \
      --query 'SecurityGroups[0].GroupId' --output text)"
if [ "$SG" = "None" ]; then
  SG="$(awsq ec2 create-security-group --group-name "$SG_NAME" --description "PARCS cluster" \
        --vpc-id "$VPC" --query GroupId --output text)"
  aws ec2 authorize-security-group-ingress --group-id "$SG" \
    --ip-permissions "IpProtocol=-1,UserIdGroupPairs=[{GroupId=$SG}]" >/dev/null
fi
MY_IP="$(curl -fs https://checkip.amazonaws.com | tr -d '\r\n')"
aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 8080 \
  --cidr "$MY_IP/32" >/dev/null 2>&1 || true
echo "Security group $SG, UI доступний з $MY_IP"

mkdir -p .build
make_userdata() {  # $1 = role, $2 = master private ip
  { echo '#!/bin/bash'
    echo "ROLE=$1"; echo "MASTER=$2"; echo "REPO=$REPO_URL"; echo "BRANCH=$REPO_BRANCH"
    tail -n +2 node_setup.sh
  } > ".build/userdata_$1.sh"
}

launch() {  # $1 = name, $2 = role
  awsq ec2 run-instances --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
    --security-group-ids "$SG" --user-data "file://.build/userdata_$2.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$1},{Key=Project,Value=$PROJECT_TAG},{Key=Role,Value=$2}]" \
    --query 'Instances[0].InstanceId' --output text
}

make_userdata master ""
MASTER_ID="$(launch parcs-master master)"
MASTER_IP="$(awsq ec2 describe-instances --instance-ids "$MASTER_ID" \
             --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)"
echo "parcs-master: $MASTER_ID ($MASTER_IP)"

make_userdata worker "$MASTER_IP"
IDS=("$MASTER_ID")
for i in $(seq 1 "$WORKERS"); do
  ID="$(launch "parcs-worker-$i" worker)"
  echo "parcs-worker-$i: $ID"
  IDS+=("$ID")
done

aws ec2 wait instance-running --instance-ids "${IDS[@]}"
bash ./cluster.sh status
echo "Через 2-3 хв (поки VM ставлять пакети) відкрийте: http://$(bash ./cluster.sh ip):8080/workers"
