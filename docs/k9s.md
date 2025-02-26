# Using HolmesGPT in K9s

Add the following contents to the K9s plugin file, typically `~/.config/k9s/plugins.yaml` on Linux and `~/Library/Application Support/k9s/plugins.yaml` on Mac. Read more about K9s plugins [here](https://k9scli.io/topics/plugins/) and check your plugin path [here](https://github.com/derailed/k9s?tab=readme-ov-file#k9s-configuration).

**Note**: HolmesGPT must be installed and configured for the K9s plugin to work.

Basic plugin to run an investigation on any Kubernetes object, using the shortcut `Shift + H`:

```yaml
plugins:
  holmesgpt:
    shortCut: Shift-H
    description: Ask HolmesGPT
    scopes:
      - all
    command: bash
    background: false
    confirm: false
    args:
      - -c
      - |
        holmes ask "why is $NAME of $RESOURCE_NAME in -n $NAMESPACE not working as expected"
        echo "Press 'q' to exit"
        while : ; do
        read -n 1 k <&1
        if [[ $k = q ]] ; then
        break
        fi
        done
```

Advanced plugin that lets you modify the questions HolmesGPT asks about the LLM, using the shortcut `Shift + O`. (E.g. you can change the question to "generate an HPA for this deployment" and the AI will follow those instructions and output an HPA configuration.)
```yaml
plugins:
  custom-holmesgpt:
    shortCut: Shift-Q
    description: Custom HolmesGPT Ask
    scopes:
      - all
    command: bash

      - |
        INSTRUCTIONS="# Edit the line below. Lines starting with '#' will be ignored."
        DEFAULT_ASK_COMMAND="why is $NAME of $RESOURCE_NAME in -n $NAMESPACE not working as expected"
        QUESTION_FILE=$(mktemp)

        echo "$INSTRUCTIONS" > "$QUESTION_FILE"
        echo "$DEFAULT_ASK_COMMAND" >> "$QUESTION_FILE"

        # Open the line in the default text editor
        ${EDITOR:-nano} "$QUESTION_FILE"

        # Read the modified line, ignoring lines starting with '#'
        user_input=$(grep -v '^#' "$QUESTION_FILE")
        echo running: holmes ask "\"$user_input\""

        holmes ask "$user_input"
        echo "Press 'q' to exit"
        while : ; do
        read -n 1 k <&1
        if [[ $k = q ]] ; then
        break
        fi
        done
```
