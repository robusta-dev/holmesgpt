# Safe Argo CD CLI commands and their allowed operations
SAFE_ARGOCD_COMMANDS = {
    # Application management (read-only)
    "app": {
        "list",
        "get",
        "resources",
        "diff",
        "history",
        "manifests",
        "logs",
        "wait",  # Wait for app to reach desired state (read-only monitoring)
    },
    # Cluster management (read-only)
    "cluster": {
        "list",
        "get",
    },
    # Project management (read-only)
    "proj": {
        "list",
        "get",
    },
    # Repository management (read-only)
    "repo": {
        "list",
        "get",
    },
    # Context management (read-only operations)
    "context": set(),  # No subcommands, just lists contexts
    # Version information (completely safe)
    "version": set(),  # No subcommands, just shows version
    # Account information (read-only)
    "account": {
        "list",
        "get",
        "get-user-info",
        "can-i",
    },
    # Administrative commands (limited read-only)
    "admin": {
        "dashboard",  # Starts read-only web UI
        "settings",  # Shows/validates settings (read-only)
    },
}

# Blocked Argo CD operations (state-modifying or sensitive)
BLOCKED_ARGOCD_OPERATIONS = {
    # Authentication operations (sensitive)
    "login",
    "logout",
    "relogin",
    # Application lifecycle operations (state-modifying)
    "create",
    "delete",
    "sync",
    "rollback",
    "edit",
    "set",
    "unset",
    "patch",
    "delete-resource",
    "terminate-op",
    "actions",  # Custom resource actions
    # Account management (sensitive)
    "generate-token",
    "delete-token",
    "update-password",
    "bcrypt",
    # Cluster management (state-modifying)
    "add",
    "rm",
    "set",
    "rotate-auth",
    # Project management (state-modifying)
    "create",
    "delete",
    "edit",
    "add-source",
    "remove-source",
    "add-destination",
    "remove-destination",
    "add-cluster-resource-whitelist",
    "remove-cluster-resource-whitelist",
    "add-namespace-resource-blacklist",
    "remove-namespace-resource-blacklist",
    "add-cluster-resource-blacklist",
    "remove-cluster-resource-blacklist",
    "add-namespace-resource-whitelist",
    "remove-namespace-resource-whitelist",
    "add-orphaned-ignore",
    "remove-orphaned-ignore",
    "add-signature-key",
    "remove-signature-key",
    "set-orphaned-ignore",
    "add-role",
    "remove-role",
    "add-role-token",
    "delete-role-token",
    "set-role",
    # Repository management (state-modifying)
    "add",
    "rm",
    # Context management (state-modifying)
    "context",  # When used with arguments to switch contexts
    # Certificate management
    "cert",
    # GPG key management
    "gpg",
    # Application set operations
    "appset",
    # Notification operations
    "notifications",
}
