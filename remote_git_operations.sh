#!/bin/bash

# Required inputs
LINE="$1"        # Line number to insert/update/remove
FILENAME="$2"    # Filename (relative path in the repo)
COMMAND="$3"     # insert/update/remove
CODE="$4"        # Code to insert or replace with
OPEN_PR="$5"     # Whether to open a PR (true/false)
COMMIT_PR="$6"   # Commit/PR name
DRY_RUN="$7"   # Commit/PR name
COMMIT_NAME="$8"   # Commit/PR name

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
    cp "$TEMP_FILE" "$TEMP_FILE_NEW" || log_error "Failed to copy file content."

    case $COMMAND in
        insert)
            awk -v line="$LINE" -v code="$CODE" '
                NR == line { print code }
                { print }
            ' "$TEMP_FILE" > "$TEMP_FILE_NEW" || log_error "Failed to insert code."
            ;;
        update)
            awk -v line="$LINE" -v code="$CODE" '
                NR == line {
                    # Handle indentation
                    match($0, /^[[:space:]]+/)
                    indent = substr($0, RSTART, RLENGTH)
                    print indent code
                    next
                }
                { print }
            ' "$TEMP_FILE" > "$TEMP_FILE_NEW" || log_error "Failed to update code."
            ;;
        remove)
            awk -v line="$LINE" '
                NR != line { print }
            ' "$TEMP_FILE" > "$TEMP_FILE_NEW" || log_error "Failed to remove line."
            ;;
        *)
            log_error "Invalid command. Use insert, update, or remove."
            ;;
    esac

    echo "DEBUG: Updated file content:" >&2
    cat "$TEMP_FILE_NEW" >&2
}

# Function to sanitize the CODE input
sanitize_code() {
    CODE=$(echo "$CODE" | sed "s/^'//;s/'$//") # Remove surrounding single quotes
    echo "Sanitized CODE: $CODE" >&2
}

# Function to create a commit
create_commit() {
    echo "Creating a commit for changes to $FILENAME..." >&2
    BRANCH_NAME="feature/$(echo "$COMMIT_PR" | tr ' ' '_' | tr -d "'")"
    echo "Creating branch $BRANCH_NAME..." >&2

    curl -s -X POST -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"ref\": \"refs/heads/$BRANCH_NAME\",
            \"sha\": \"$(curl -s -H "Authorization: token $TOKEN" "https://api.github.com/repos/$REPO/git/refs/heads/$GIT_BRANCH" | jq -r '.object.sha')\"
        }" "https://api.github.com/repos/$REPO/git/refs" || log_error "Failed to create branch $BRANCH_NAME."

    SHA=$(curl -s -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/$REPO/contents/$FILENAME" | jq -r '.sha')
    if [[ -z "$SHA" ]]; then
        log_error "Failed to fetch SHA for $FILENAME."
    fi

    CONTENT=$(cat "$TEMP_FILE_NEW" | base64 | tr -d '\n')

    echo "DEBUG: JSON Payload:" >&2
    echo "{
        \"message\": \"$COMMIT_PR\",
        \"content\": \"$CONTENT\",
        \"sha\": \"$SHA\",
        \"branch\": \"$BRANCH_NAME\"
    }" >&2

    RESPONSE=$(curl -s -X PUT -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$COMMIT_PR\",
            \"content\": \"$CONTENT\",
            \"sha\": \"$SHA\",
            \"branch\": \"$BRANCH_NAME\"
        }" "https://api.github.com/repos/$REPO/contents/$FILENAME")

    if echo "$RESPONSE" | grep -q "\"message\": \"Problems parsing JSON\""; then
        echo "ERROR: Failed to push changes due to JSON parsing issues." >&2
        echo "Response: $RESPONSE" >&2
        exit 1
    fi
}


# Function to open a pull request
open_pull_request() {
    echo "Opening a pull request from branch $BRANCH_NAME to $GIT_BRANCH..." >&2
    BRANCH_NAME="feature/$(echo "$COMMIT_PR" | tr ' ' '_' | tr -d "'")"
    curl -s -X POST -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"title\": \"$COMMIT_PR\",
            \"body\": \"$COMMIT_NAME\",
            \"head\": \"$BRANCH_NAME\",
            \"base\": \"$GIT_BRANCH\"
        }" "https://api.github.com/repos/$REPO/pulls" || log_error "Failed to open a pull request from $BRANCH_NAME to $GIT_BRANCH."
}

# Main logic
# Function to check if the branch existed before running the script
check_branch_existence() {
    echo "Checking if branch $BRANCH_NAME existed prior to script execution..." >&2
    BRANCH_EXISTS=$(curl -s -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/$REPO/git/refs/heads/$BRANCH_NAME" | jq -r '.ref' | grep -c "$BRANCH_NAME")

    if [[ "$BRANCH_EXISTS" -eq 1 ]]; then
        echo "Branch $BRANCH_NAME existed prior to script execution." >&2
        PRE_EXISTING_BRANCH=true
    else
        echo "Branch $BRANCH_NAME did not exist prior to script execution." >&2
        PRE_EXISTING_BRANCH=false
    fi
}

# Function to delete remote branch
delete_remote_branch() {
    if [[ "$PRE_EXISTING_BRANCH" == "false" ]]; then
        echo "Deleting branch $BRANCH_NAME due to script failure..." >&2
        curl -s -X DELETE -H "Authorization: token $TOKEN" \
            "https://api.github.com/repos/$REPO/git/refs/heads/$BRANCH_NAME" || {
            echo "ERROR: Failed to delete branch $BRANCH_NAME." >&2
        }
    else
        echo "Branch $BRANCH_NAME will not be deleted as it existed prior to script execution." >&2
    fi
}

# Function to handle dry-run
dry_run_mode() {
    echo "Dry-run mode enabled. Parsing proposed changes directly..." >&2

    # Use existing fetch_file_content function
    fetch_file_content || log_error "Failed to fetch file content during dry-run."

    # Use sanitize_code to clean the input code
    sanitize_code

    # Apply changes using update_file_content
    update_file_content || log_error "Failed to update file content during dry-run."

    # Save the updated content to a dry-run output file
    DRY_RUN_OUTPUT_FILE="dry_run_output.yaml"
    echo "DEBUG: Writing updated file content to $DRY_RUN_OUTPUT_FILE..." >&2
    cp "$TEMP_FILE_NEW" "$DRY_RUN_OUTPUT_FILE" || log_error "Failed to write updated file content during dry-run."

    # Print the content to the terminal for verification
    echo "DEBUG: Printing updated file content for dry-run:" >&2
    cat "$DRY_RUN_OUTPUT_FILE" || log_error "Failed to read the updated file content during dry-run."

    # Cleanup temporary files
    echo "DEBUG: Cleaning up temporary files used during dry-run..." >&2
    rm -f "$TEMP_FILE" "$TEMP_FILE_NEW"

    echo "DEBUG: Dry-run completed successfully. No remote changes were made." >&2
    exit 0
}

# Main script logic
BRANCH_NAME="feature/$(echo "$COMMIT_PR" | tr ' ' '_' | tr -d "'")"

if [[ "$DRY_RUN" == "true" ]]; then
    dry_run_mode
fi


# Check if branch existed before script execution
check_branch_existence

# Fetch file content, process, and create commit
fetch_file_content || { delete_remote_branch; exit 1; }
sanitize_code
update_file_content || { delete_remote_branch; exit 1; }
create_commit || { delete_remote_branch; exit 1; }

# Open pull request if requested
if [[ "$OPEN_PR" == "true" ]]; then
    open_pull_request || { delete_remote_branch; exit 1; }
fi

# Cleanup
rm -f "$TEMP_FILE" "$TEMP_FILE_NEW"
