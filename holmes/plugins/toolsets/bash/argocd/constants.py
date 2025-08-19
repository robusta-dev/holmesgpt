import re

# Regex patterns for validating Argo CD CLI parameters
SAFE_ARGOCD_APP_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SAFE_ARGOCD_PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SAFE_ARGOCD_CLUSTER_NAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-._]*[a-zA-Z0-9])?$"
)
SAFE_ARGOCD_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SAFE_ARGOCD_REPO_URL_PATTERN = re.compile(
    r"^https?://[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+$"
)

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

# Safe output formats for Argo CD CLI
SAFE_ARGOCD_OUTPUT_FORMATS = {
    "json",
    "yaml",
    "wide",
    "name",
    "tree",  # For app get command
}

# Safe global Argo CD CLI flags
SAFE_ARGOCD_GLOBAL_FLAGS = {
    # Output and formatting
    "--output",
    "-o",
    "--help",
    "-h",
    # Server connection (read-only context)
    "--server",
    "--insecure",
    "--grpc-web",
    "--grpc-web-root-path",
    "--plaintext",
    # Application context flags
    "--app-namespace",
    "-N",
    "--namespace",
    # Filtering and selection
    "--selector",
    "-l",
    "--project",
    "-p",
    "--cluster",
    "-c",
    "--repo",
    "-r",
    # Display options
    "--show-params",
    "--show-operation",
    "--refresh",
    # Log options
    "--tail",
    "--filter",
    "--container",
    "--group",
    "--kind",
    "--name",
    "--previous",
    "-p",
    "--since",
    "--since-time",
    "--timestamps",
    "--match-case",
    # History options
    "--revision",
    # Wait options
    "--timeout",
    "--health",
    "--sync",
    "--suspended",
    "--degraded",
    # Diff options
    "--revision",
    "--local",
    "--refresh",
    # Manifest options
    "--source",
    "--revision",
    "--local",
    # General options
    "--hard-refresh",
    "--config",
    "--client-crt",
    "--client-crt-key",
    "--client-key",
    "--config-password",
    "--core",
    "--logformat",
    "--loglevel",
    "--port-forward",
    "--port-forward-namespace",
    "--request-timeout",
    "--kube-context",
}

# Additional safe flags for specific commands
SAFE_ARGOCD_COMMAND_FLAGS = {
    # App-specific flags
    "--all-namespaces",
    "-A",
    "--cluster-name",
    "--repo-url",
    "--path",
    "--dest-server",
    "--dest-namespace",
    "--values",
    "--values-literal",
    "--parameter",
    "--helm-set",
    "--helm-set-string",
    "--helm-set-file",
    "--jsonnet-ext-str",
    "--jsonnet-ext-code",
    "--jsonnet-tla-str",
    "--jsonnet-tla-code",
    # Account flags
    "--user",
    "--action",
    "--resource",
    # Admin flags
    "--address",
    "--port",
    "--metrics-port",
    "--secure",
    # Repo flags
    "--type",
    "--ssh-private-key-path",
    "--tls-client-cert-path",
    "--tls-client-cert-key-path",
    "--proxy",
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

# Resource types that are safe to query
SAFE_ARGOCD_RESOURCE_TYPES = {
    "application",
    "appproject",
    "configmap",
    "secret",  # Metadata only, not content
    "service",
    "deployment",
    "replicaset",
    "pod",
    "job",
    "cronjob",
    "daemonset",
    "statefulset",
    "ingress",
    "persistentvolume",
    "persistentvolumeclaim",
    "namespace",
    "node",
    "serviceaccount",
    "role",
    "rolebinding",
    "clusterrole",
    "clusterrolebinding",
    "networkpolicy",
    "poddisruptionbudget",
    "horizontalpodautoscaler",
    "verticalpodautoscaler",
    "event",
}

# Common Argo CD application states (for validation)
ARGOCD_APP_HEALTH_STATES = {
    "Healthy",
    "Progressing",
    "Degraded",
    "Suspended",
    "Missing",
    "Unknown",
}

ARGOCD_APP_SYNC_STATES = {
    "Synced",
    "OutOfSync",
    "Unknown",
}

# Common Argo CD log levels
ARGOCD_LOG_LEVELS = {
    "debug",
    "info",
    "warn",
    "error",
    "fatal",
    "panic",
}

# Safe log formats
ARGOCD_LOG_FORMATS = {
    "text",
    "json",
}
