#!/bin/bash

# Check if POD_NAME is passed as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 POD_NAME"
  exit 1
fi

# Assign the first argument to POD_NAME
POD_NAME="$1"

# Define the environment variable name for the token
TOKEN_ENV_VAR="CORALOGIX_TOKEN"

# Retrieve the token from the environment variable
TOKEN=$(printenv "$TOKEN_ENV_VAR")

# Check if the token is set
if [ -z "$TOKEN" ]; then
  echo "Environment variable $TOKEN_ENV_VAR is not set."
  exit 1
fi

END_DATE=$(date -u -v +3H +"%Y-%m-%dT%H:%M:%S.00Z")
START_DATE=$(date -u -v -8H +"%Y-%m-%dT%H:%M:%S.00Z")

# Define the curl command with the updated dates
curl --location 'https://ng-api-http.eu2.coralogix.com/api/v1/dataprime/query' \
--header "Authorization: Bearer $TOKEN" \
--header 'Content-Type: application/json' \
--data "{
  \"query\": \"source logs | lucene 'coralogix.metadata.applicationName:$POD_NAME' | limit 300\",
  \"metadata\": {
        \"syntax\": \"QUERY_SYNTAX_DATAPRIME\",
        \"startDate\": \"$START_DATE\",
        \"endDate\": \"$END_DATE\"
    }
}"  | jq -r '.result.results[].userData | fromjson | .text | fromjson | .log'
