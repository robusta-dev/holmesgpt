# Safe Helm commands - read-only and inspection operations
SAFE_HELM_COMMANDS = {
    # Release management (read-only)
    "list",
    "ls",
    "get",
    "status",
    "history",
    "diff",
    # Chart operations (read-only)
    "show",
    "inspect",
    "search",
    "template",
    "lint",
    "verify",
    "dependency list",
    "dependency build --dry-run",
    # Repository operations (read-only)
    "repo list",
    "repo index --dry-run",
    "search repo",
    # Help and information
    "help",
    "version",
    "env",
    # Plugin operations (read-only)
    "plugin list",
    # Completion
    "completion",
}

# Safe Helm get subcommands
SAFE_HELM_GET_SUBCOMMANDS = {
    "all",
    "hooks",
    "manifest",
    "notes",
    "values",
    "metadata",
}

# Safe Helm show subcommands
SAFE_HELM_SHOW_SUBCOMMANDS = {
    "all",
    "chart",
    "readme",
    "values",
    "crds",
}

# Blocked Helm operations (state-modifying or dangerous)
BLOCKED_HELM_OPERATIONS = {
    # Release lifecycle operations
    "install",
    "upgrade",
    "uninstall",
    "delete",
    "rollback",
    "test",
    # Repository management
    "repo add",
    "repo remove",
    "repo rm",
    "repo update",
    "repo index",
    # Chart packaging and publishing
    "create",
    "package",
    "push",
    "pull",
    "fetch",
    "dependency update",
    "dependency build",
    # Plugin management
    "plugin install",
    "plugin uninstall",
    "plugin update",
    # Registry operations
    "registry login",
    "registry logout",
    # Environment modification
    "env set",
    "env unset",
    # Configuration modification
    "config",
    # Mapkubeapis operations
    "mapkubeapis",
}
