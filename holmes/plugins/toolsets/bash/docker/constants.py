
# Safe Docker commands - read-only and inspection operations
SAFE_DOCKER_COMMANDS = {
    # Container management (read-only)
    "ps",
    "container ls",
    "container list", 
    "container inspect",
    "container logs",
    "container stats",
    "container top",
    "container port",
    "container diff",
    "container export",
    
    # Image management (read-only)
    "images",
    "image ls",
    "image list",
    "image inspect",
    "image history",
    
    # System information
    "version",
    "info",
    "system info",
    "system events",
    "system df",
    "system prune --dry-run",
    
    # Network inspection
    "network ls",
    "network list",
    "network inspect",
    
    # Volume inspection  
    "volume ls",
    "volume list",
    "volume inspect",
    
    # Registry operations (read-only)
    "search",
    
    # Plugin inspection
    "plugin ls",
    "plugin list", 
    "plugin inspect",
    
    # Node information (Swarm read-only)
    "node ls",
    "node list",
    "node inspect",
    
    # Service information (Swarm read-only)
    "service ls", 
    "service list",
    "service inspect",
    "service logs",
    "service ps",
    
    # Stack information (read-only)
    "stack ls",
    "stack list",
    "stack ps",
    "stack services",
    
    # Secret inspection (read-only metadata)
    "secret ls",
    "secret list",
    "secret inspect",
    
    # Config inspection (read-only)
    "config ls", 
    "config list",
    "config inspect",
    
    # Context information
    "context ls",
    "context list",
    "context inspect",
    "context show",
}

# Safe output formats for Docker CLI
SAFE_DOCKER_OUTPUT_FORMATS = {
    "table",
    "json", 
    "yaml",
    "wide",
}


# Blocked Docker operations (state-modifying or dangerous)
BLOCKED_DOCKER_OPERATIONS = {
    # Container lifecycle operations
    "run",
    "create", 
    "start",
    "stop",
    "restart",
    "pause",
    "unpause", 
    "kill",
    "remove",
    "rm",
    "exec",
    "attach",
    "cp",
    "commit",
    "update",
    "rename",
    "wait",
    
    # Image operations
    "build",
    "pull",
    "push", 
    "tag",
    "untag",
    "rmi",
    "load",
    "import",
    "save",
    
    # Network operations
    "network create",
    "network rm", 
    "network remove",
    "network connect",
    "network disconnect",
    "network prune",
    
    # Volume operations
    "volume create",
    "volume rm",
    "volume remove", 
    "volume prune",
    
    # System operations
    "system prune",
    "container prune",
    "image prune", 
    "volume prune",
    "network prune",
    
    # Registry operations
    "login",
    "logout",
    
    # Plugin operations
    "plugin install",
    "plugin enable",
    "plugin disable",
    "plugin upgrade", 
    "plugin rm",
    "plugin remove",
    "plugin push",
    "plugin create",
    "plugin set",
    
    # Swarm operations
    "swarm init",
    "swarm join",
    "swarm leave",
    "swarm update",
    "swarm join-token",
    "swarm unlock",
    "swarm unlock-key",
    
    # Node operations
    "node update",
    "node demote", 
    "node promote",
    "node rm",
    "node remove",
    
    # Service operations  
    "service create",
    "service update",
    "service scale",
    "service rm",
    "service remove",
    "service rollback",
    
    # Stack operations
    "stack deploy",
    "stack rm",
    "stack remove",
    
    # Secret operations
    "secret create",
    "secret rm",
    "secret remove",
    
    # Config operations
    "config create", 
    "config rm",
    "config remove",
    
    # Context operations
    "context create",
    "context rm", 
    "context remove",
    "context update",
    "context use",
    "context export",
    "context import",
    
    # Checkpoint operations
    "checkpoint",
    
    # Buildx operations
    "buildx",
    
    # Compose operations  
    "compose",
    
    # Trust operations
    "trust",
    
    # Manifest operations
    "manifest",
}