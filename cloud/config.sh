# Налаштування кластера PARCS в AWS EC2. Змініть під себе.
REGION="${REGION:-eu-north-1}"                # Стокгольм (Free plan: лише регіон акаунта)
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"    # free-tier eligible
WORKERS="${WORKERS:-4}"                      # кількість воркер-процесів PARCS
# 1 = worker-1 запускається на VM master'а (квота Free plan 8 vCPU = 4 VM по 2 vCPU)
COLOCATED_WORKER="${COLOCATED_WORKER:-1}"
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
