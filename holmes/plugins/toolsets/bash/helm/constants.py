import re

# Regex patterns for validating Helm CLI parameters
SAFE_HELM_RELEASE_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SAFE_HELM_CHART_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._/-]+$")
SAFE_HELM_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SAFE_HELM_REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
SAFE_HELM_REPO_URL_PATTERN = re.compile(r"^https?://[a-zA-Z0-9.-]+(/.*)?$")

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

# Safe output formats for Helm CLI
SAFE_HELM_OUTPUT_FORMATS = {
    "table",
    "json",
    "yaml",
}

# Safe global Helm CLI options/flags
SAFE_HELM_GLOBAL_FLAGS = {
    "--help", "-h",
    "--version",
    "--debug",
    "--kube-context",
    "--kube-config", "--kubeconfig",
    "--kube-apiserver",
    "--kube-ca-file",
    "--kube-token",
    "--kube-as-user",
    "--kube-as-group",
    "--namespace", "-n",
    "--registry-config",
    "--repository-config",
    "--repository-cache",
    "--add-dir-header",
    "--alsologtostderr",
    "--log-backtrace-at",
    "--log-dir",
    "--log-file",
    "--log-file-max-size",
    "--logtostderr",
    "--stderrthreshold",
    "--vmodule", "-v",
}

# Additional safe flags for specific Helm commands
SAFE_HELM_COMMAND_FLAGS = {
    # List/Status flags
    "--all-namespaces", "-A",
    "--output", "-o",
    "--short", "-q",
    "--date",
    "--deployed",
    "--failed", 
    "--pending",
    "--superseded",
    "--uninstalled",
    "--filter",
    "--selector", "-l",
    "--max",
    "--offset",
    "--reverse", "-r",
    "--time-format",
    
    # Get/Show flags
    "--revision",
    "--template",
    "--all",
    
    # Search flags
    "--max-col-width",
    "--devel",
    "--version",
    "--versions",
    "--regexp", "-r",
    
    # Template flags
    "--dry-run",
    "--include-crds",
    "--is-upgrade",
    "--kube-version",
    "--name-template",
    "--no-hooks",
    "--output-dir",
    "--post-renderer",
    "--release-name",
    "--set",
    "--set-file", 
    "--set-string",
    "--show-only",
    "--skip-crds",
    "--skip-tests",
    "--validate",
    "--values", "-f",
    "--api-versions",
    
    # Lint flags
    "--strict",
    "--with-subcharts",
    "--quiet",
    
    # Dependency flags
    "--keyring",
    "--skip-refresh",
    "--verify",
    
    # Repository flags
    "--url",
    "--force-update",
    
    # Plugin flags
    "--plugin",
    
    # History flags
    "--max-history",
    
    # Verify flags
    "--keyring",
    
    # Version flags
    "--short",
    "--client",
    "--template",
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

# Common Helm chart repositories for validation
SAFE_HELM_REPOSITORIES = {
    "https://charts.helm.sh/stable",
    "https://charts.helm.sh/incubator", 
    "https://kubernetes-charts.storage.googleapis.com",
    "https://charts.bitnami.com/bitnami",
    "https://helm.nginx.com/stable",
    "https://prometheus-community.github.io/helm-charts",
    "https://grafana.github.io/helm-charts",
    "https://charts.jetstack.io",
    "https://kubernetes.github.io/ingress-nginx",
    "https://cert-manager.io/charts",
    "https://elastic.github.io/helm-charts",
    "https://istio-release.storage.googleapis.com/charts",
    "https://argoproj.github.io/argo-helm",
}

# Valid Helm chart archive extensions
SAFE_HELM_CHART_EXTENSIONS = {
    ".tgz",
    ".tar.gz",
}