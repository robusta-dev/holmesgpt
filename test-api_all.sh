#set -e

while true; do
    ./test-api_investigate.sh
    ./test-api_health_check.sh
    ./test-api_chat.sh
    ./test-api_issue_conversation.sh
done
