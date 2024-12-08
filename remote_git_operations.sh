#!/bin/bash

# Required inputs
LINE="$1"        # Line number to insert/update/remove
FILENAME="$2"    # Filename (relative path in the repo)
COMMAND="$3"     # insert/update/remove
CODE="$4"        # Code to insert or replace with
OPEN_PR="$5"     # Whether to open a PR (true/false)
COMMIT_PR="$6"   # Commit/PR name

# GitHub repo details
REPO=$GIT_REPO
TOKEN=$GIT_CREDENTIALS

# Temp files for processing
TEMP_FILE="temp_file"
TEMP_FILE_NEW="temp_file_new"

# Function to log and exit on error
log_error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Function to fetch the file content
fetch_file_content() {
    echo "Fetching file content for $FILENAME..." >&2
    curl -s -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/$REPO/contents/$FILENAME" | jq -r '.content' | base64 -d > "$TEMP_FILE" || log_error "Failed to fetch file content."
    if [[ ! -s $TEMP_FILE ]]; then
        log_error "File content for $FILENAME is empty or could not be fetched."
    fi
}

# Function to update the file content based on the command
update_file_content() {
    echo "Updating file content with command '$COMMAND'..." >&2
    echo "Source file: $TEMP_FILE" >&2
    echo "Target file: $TEMP_FILE_NEW" >&2
    echo "Line number: $LINE" >&2
    echo "Command: $COMMAND" >&2
    echo "Code to apply: '$CODE'" >&2

    cp "$TEMP_FILE" "$TEMP_FILE_NEW" || log_error "Failed to copy file content."

    case $COMMAND in
        insert)
            echo "Attempting to insert code at line $LINE..." >&2
            awk -v line="$LINE" -v code="$CODE" 'NR == line { print code } { print }' "$TEMP_FILE" > "$TEMP_FILE_NEW" || {
                echo "DEBUG: Contents of target file before failure:" >&2
                cat "$TEMP_FILE_NEW" >&2
                log_error "Failed to insert code at line $LINE."
            }
            ;;
        update)
            echo "Attempting to update line $LINE with code..." >&2
            awk -v line="$LINE" -v code="$CODE" 'NR == line { print code; next } { print }' "$TEMP_FILE" > "$TEMP_FILE_NEW" || {
                echo "DEBUG: Contents of target file before failure:" >&2
                cat "$TEMP_FILE_NEW" >&2
                log_error "Failed to update code at line $LINE."
            }
            ;;
        remove)
            echo "Attempting to remove line $LINE..." >&2
            awk -v line="$LINE" 'NR != line { print }' "$TEMP_FILE" > "$TEMP_FILE_NEW" || {
                echo "DEBUG: Contents of target file before failure:" >&2
                cat "$TEMP_FILE_NEW" >&2
                log_error "Failed to remove line $LINE."
            }
            ;;
        *)
            log_error "Invalid command. Use insert, update, or remove."
            ;;
    esac

    echo "DEBUG: Contents of target file after modification:" >&2
    cat "$TEMP_FILE_NEW" >&2
}

# Function to create a commit
create_commit() {
    echo "Creating a commit for changes to $FILENAME..." >&2
    BRANCH_NAME="feature/${COMMIT_PR// /_}"
    
    echo "Creating branch $BRANCH_NAME..." >&2
    curl -s -X POST -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"ref\": \"refs/heads/$BRANCH_NAME\",
            \"sha\": \"$(curl -s -H "Authorization: token $TOKEN" "https://api.github.com/repos/$REPO/git/refs/heads/master" | jq -r '.object.sha')\"
        }" "https://api.github.com/repos/$REPO/git/refs" || log_error "Failed to create branch $BRANCH_NAME."

    SHA=$(curl -s -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/$REPO/contents/$FILENAME" | jq -r '.sha')
    if [[ -z "$SHA" ]]; then
        log_error "Failed to fetch SHA for $FILENAME."
    fi

    CONTENT=$(base64 -w 0 "$TEMP_FILE_NEW")

    echo "Pushing changes to branch $BRANCH_NAME..." >&2
    curl -s -X PUT -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$COMMIT_PR\",
            \"content\": \"$CONTENT\",
            \"sha\": \"$SHA\",
            \"branch\": \"$BRANCH_NAME\"
        }" "https://api.github.com/repos/$REPO/contents/$FILENAME" || log_error "Failed to push changes to branch $BRANCH_NAME."
}

# Function to open a pull request
open_pull_request() {
    echo "Opening a pull request from branch $BRANCH_NAME to master..." >&2
    BRANCH_NAME="feature/${COMMIT_PR// /_}"
    curl -s -X POST -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"title\": \"$COMMIT_PR\",
            \"body\": \"Automated PR for $COMMIT_PR\",
            \"head\": \"$BRANCH_NAME\",
            \"base\": \"master\"
        }" "https://api.github.com/repos/$REPO/pulls" || log_error "Failed to open a pull request from $BRANCH_NAME to master."
}

# Main logic
fetch_file_content
update_file_content
create_commit

if [[ "$OPEN_PR" == "true" ]]; then
    open_pull_request
fi

# Cleanup
echo "Cleaning up temporary files..." >&2
rm -f "$TEMP_FILE" "$TEMP_FILE_NEW"
