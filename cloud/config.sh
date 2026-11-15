# Налаштування кластера PARCS в AWS EC2. Змініть під себе.
REGION="${REGION:-eu-central-1}"              # Франкфурт
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"    # free-tier; при квоті 5 vCPU — t2.micro (1 vCPU)
WORKERS="${WORKERS:-4}"
# Офіційний образ Debian 12 (id береться з публічного параметра SSM)
AMI="${AMI:-resolve:ssm:/aws/service/debian/release/12/latest/amd64}"

# Публічний репозиторій з цим проєктом (звідси VM беруть код PARCS)
REPO_URL="${REPO_URL:-https://github.com/BohdanKnuSecond/dijkstra-parcs.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

PROJECT_TAG="parcs"
SG_NAME="parcs-sg"

export AWS_DEFAULT_REGION="$REGION"
export AWS_PAGER=""
export MSYS_NO_PATHCONV=1   # Git Bash на Windows: не переписувати аргументи вигляду /a/b

# aws CLI на Windows може повертати \r у текстовому виводі
awsq() { aws "$@" | tr -d '\r'; }
