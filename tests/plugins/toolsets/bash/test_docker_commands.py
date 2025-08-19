"""
Tests for Docker CLI command parsing, validation, and stringification.

This module tests the Docker CLI integration in the bash toolset, ensuring:
1. Safe Docker commands are allowed and properly parsed
2. Unsafe Docker commands are blocked with appropriate error messages  
3. Docker command options are validated correctly
4. Commands are properly stringified back to safe command strings
"""

import argparse
import pytest
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.parse_command import make_command_safe


class TestDockerCliSafeCommands:
    """Test Docker CLI safe commands that should be allowed."""

    @pytest.mark.parametrize(
        "input_command,expected_output",
        [
            # Container listing and inspection
            ("docker ps", "docker ps"),
            ("docker ps -a", "docker ps -a"),
            ("docker ps --all", "docker ps --all"),
            ("docker ps --quiet", "docker ps --quiet"),
            ("docker ps -q", "docker ps -q"),
            ("docker ps --filter status=running", "docker ps --filter status=running"),
            ("docker ps --format table", "docker ps --format table"),
            ("docker ps --format json", "docker ps --format json"),
            ("docker ps --no-trunc", "docker ps --no-trunc"),
            ("docker ps --size", "docker ps --size"),
            ("docker ps -s", "docker ps -s"),
            ("docker ps --latest", "docker ps --latest"),
            ("docker ps -l", "docker ps -l"),
            
            # Container management (read-only)
            ("docker container ls", "docker container ls"),
            ("docker container list", "docker container list"),
            ("docker container ls -a", "docker container ls -a"),
            ("docker container inspect mycontainer", "docker container inspect mycontainer"),
            ("docker container logs mycontainer", "docker container logs mycontainer"),
            ("docker container logs mycontainer --tail 100", "docker container logs mycontainer --tail 100"),
            ("docker container logs mycontainer --follow", "docker container logs mycontainer --follow"),
            ("docker container logs mycontainer --timestamps", "docker container logs mycontainer --timestamps"),
            ("docker container logs mycontainer -t", "docker container logs mycontainer -t"),
            ("docker container logs mycontainer --since 1h", "docker container logs mycontainer --since 1h"),
            ("docker container logs mycontainer --until 2023-01-01", "docker container logs mycontainer --until 2023-01-01"),
            ("docker container stats", "docker container stats"),
            ("docker container stats mycontainer", "docker container stats mycontainer"),
            ("docker container stats --no-stream", "docker container stats --no-stream"),
            ("docker container top mycontainer", "docker container top mycontainer"),
            ("docker container port mycontainer", "docker container port mycontainer"),
            ("docker container port mycontainer 80", "docker container port mycontainer 80"),
            ("docker container diff mycontainer", "docker container diff mycontainer"),
            ("docker container export mycontainer", "docker container export mycontainer"),
            ("docker container export mycontainer --output container.tar", "docker container export mycontainer --output container.tar"),
            
            # Image listing and inspection
            ("docker images", "docker images"),
            ("docker images -a", "docker images -a"),
            ("docker images --all", "docker images --all"),
            ("docker images --quiet", "docker images --quiet"),
            ("docker images -q", "docker images -q"),
            ("docker images --no-trunc", "docker images --no-trunc"),
            ("docker images --filter dangling=true", "docker images --filter dangling=true"),
            ("docker images --format table", "docker images --format table"),
            ("docker images --format json", "docker images --format json"),
            ("docker image ls", "docker image ls"),
            ("docker image list", "docker image list"),
            ("docker image inspect nginx", "docker image inspect nginx"),
            ("docker image inspect nginx:latest", "docker image inspect nginx:latest"),
            ("docker image history nginx", "docker image history nginx"),
            ("docker image history nginx --no-trunc", "docker image history nginx --no-trunc"),
            ("docker image history nginx --quiet", "docker image history nginx --quiet"),
            ("docker image history nginx --format table", "docker image history nginx --format table"),
            
            # System information
            ("docker version", "docker version"),
            ("docker version --format json", "docker version --format json"),
            ("docker info", "docker info"),
            ("docker info --format json", "docker info --format json"),
            ("docker system info", "docker system info"),
            ("docker system events", "docker system events"),
            ("docker system events --since 1h", "docker system events --since 1h"),
            ("docker system events --until 2023-01-01", "docker system events --until 2023-01-01"),
            ("docker system events --filter type=container", "docker system events --filter type=container"),
            ("docker system df", "docker system df"),
            ("docker system df --verbose", "docker system df --verbose"),
            ("docker system prune --dry-run", "docker system prune --dry-run"),
            
            # Network inspection
            ("docker network ls", "docker network ls"),
            ("docker network list", "docker network list"),
            ("docker network ls --quiet", "docker network ls --quiet"),
            ("docker network ls -q", "docker network ls -q"),
            ("docker network ls --no-trunc", "docker network ls --no-trunc"),
            ("docker network ls --filter driver=bridge", "docker network ls --filter driver=bridge"),
            ("docker network ls --format table", "docker network ls --format table"),
            ("docker network inspect bridge", "docker network inspect bridge"),
            ("docker network inspect mynetwork", "docker network inspect mynetwork"),
            ("docker network inspect mynetwork --format json", "docker network inspect mynetwork --format json"),
            
            # Volume inspection
            ("docker volume ls", "docker volume ls"),
            ("docker volume list", "docker volume list"),
            ("docker volume ls --quiet", "docker volume ls --quiet"),
            ("docker volume ls -q", "docker volume ls -q"),
            ("docker volume ls --filter dangling=true", "docker volume ls --filter dangling=true"),
            ("docker volume ls --format table", "docker volume ls --format table"),
            ("docker volume inspect myvolume", "docker volume inspect myvolume"),
            ("docker volume inspect myvolume --format json", "docker volume inspect myvolume --format json"),
            
            # Registry operations (read-only)
            ("docker search nginx", "docker search nginx"),
            ("docker search nginx --limit 10", "docker search nginx --limit 10"),
            ("docker search nginx --stars 100", "docker search nginx --stars 100"),
            ("docker search nginx --automated", "docker search nginx --automated"),
            ("docker search nginx --official", "docker search nginx --official"),
            ("docker search nginx --no-trunc", "docker search nginx --no-trunc"),
            
            # Plugin inspection
            ("docker plugin ls", "docker plugin ls"),
            ("docker plugin list", "docker plugin list"),
            ("docker plugin ls --quiet", "docker plugin ls --quiet"),
            ("docker plugin ls -q", "docker plugin ls -q"),
            ("docker plugin ls --no-trunc", "docker plugin ls --no-trunc"),
            ("docker plugin inspect myplugin", "docker plugin inspect myplugin"),
            
            # Swarm information (read-only)
            ("docker node ls", "docker node ls"),
            ("docker node list", "docker node list"),
            ("docker node ls --quiet", "docker node ls --quiet"),
            ("docker node ls -q", "docker node ls -q"),
            ("docker node ls --filter role=manager", "docker node ls --filter role=manager"),
            ("docker node ls --format table", "docker node ls --format table"),
            ("docker node inspect mynode", "docker node inspect mynode"),
            ("docker node inspect self", "docker node inspect self"),
            
            # Service information (read-only)
            ("docker service ls", "docker service ls"),
            ("docker service list", "docker service list"),
            ("docker service ls --quiet", "docker service ls --quiet"),
            ("docker service ls -q", "docker service ls -q"),
            ("docker service ls --filter mode=replicated", "docker service ls --filter mode=replicated"),
            ("docker service ls --format table", "docker service ls --format table"),
            ("docker service inspect myservice", "docker service inspect myservice"),
            ("docker service logs myservice", "docker service logs myservice"),
            ("docker service logs myservice --tail 100", "docker service logs myservice --tail 100"),
            ("docker service logs myservice --follow", "docker service logs myservice --follow"),
            ("docker service logs myservice --timestamps", "docker service logs myservice --timestamps"),
            ("docker service ps myservice", "docker service ps myservice"),
            ("docker service ps myservice --quiet", "docker service ps myservice --quiet"),
            ("docker service ps myservice --no-trunc", "docker service ps myservice --no-trunc"),
            
            # Stack information (read-only)
            ("docker stack ls", "docker stack ls"),
            ("docker stack list", "docker stack list"),
            ("docker stack ls --format table", "docker stack ls --format table"),
            ("docker stack ps mystack", "docker stack ps mystack"),
            ("docker stack ps mystack --quiet", "docker stack ps mystack --quiet"),
            ("docker stack ps mystack --no-trunc", "docker stack ps mystack --no-trunc"),
            ("docker stack services mystack", "docker stack services mystack"),
            ("docker stack services mystack --quiet", "docker stack services mystack --quiet"),
            ("docker stack services mystack --format table", "docker stack services mystack --format table"),
            
            # Secret inspection (read-only metadata)
            ("docker secret ls", "docker secret ls"),
            ("docker secret list", "docker secret list"),
            ("docker secret ls --quiet", "docker secret ls --quiet"),
            ("docker secret ls -q", "docker secret ls -q"),
            ("docker secret ls --format table", "docker secret ls --format table"),
            ("docker secret inspect mysecret", "docker secret inspect mysecret"),
            
            # Config inspection (read-only)
            ("docker config ls", "docker config ls"),
            ("docker config list", "docker config list"),
            ("docker config ls --quiet", "docker config ls --quiet"),
            ("docker config ls -q", "docker config ls -q"),
            ("docker config ls --format table", "docker config ls --format table"),
            ("docker config inspect myconfig", "docker config inspect myconfig"),
            
            # Context information
            ("docker context ls", "docker context ls"),
            ("docker context list", "docker context list"),
            ("docker context ls --quiet", "docker context ls --quiet"),
            ("docker context ls -q", "docker context ls -q"),
            ("docker context ls --format table", "docker context ls --format table"),
            ("docker context inspect mycontext", "docker context inspect mycontext"),
            ("docker context show", "docker context show"),
            
            # Help commands
            ("docker --help", "docker --help"),
            ("docker -h", "docker -h"),
            ("docker ps --help", "docker ps --help"),
            ("docker images --help", "docker images --help"),
            
            # Commands with complex filters
            ("docker ps --filter status=running --filter name=web", "docker ps --filter status=running --filter name=web"),
            ("docker images --filter dangling=true --filter before=nginx", "docker images --filter dangling=true --filter before=nginx"),
            ("docker network ls --filter driver=bridge --filter scope=local", "docker network ls --filter driver=bridge --filter scope=local"),
            
            # Commands with multiple formatting options
            ("docker ps --format 'table {{.Names}}\\t{{.Status}}'", "docker ps --format 'table {{.Names}}\\t{{.Status}}'"),
            ("docker images --format 'table {{.Repository}}:{{.Tag}}\\t{{.Size}}'", "docker images --format 'table {{.Repository}}:{{.Tag}}\\t{{.Size}}'"),
        ],
    )
    def test_docker_safe_commands(self, input_command: str, expected_output: str):
        """Test that safe Docker commands are parsed and stringified correctly."""
        config = BashExecutorConfig()
        output_command = make_command_safe(input_command, config=config)
        assert output_command == expected_output


class TestDockerCliUnsafeCommands:
    """Test Docker CLI unsafe commands that should be rejected."""

    @pytest.mark.parametrize(
        "command,expected_exception,partial_error_message_content",
        [
            # Container lifecycle operations
            ("docker run nginx", ValueError, "blocked operation 'run'"),
            ("docker create nginx", ValueError, "blocked operation 'create'"),
            ("docker start mycontainer", ValueError, "blocked operation 'start'"),
            ("docker stop mycontainer", ValueError, "blocked operation 'stop'"),
            ("docker restart mycontainer", ValueError, "blocked operation 'restart'"),
            ("docker pause mycontainer", ValueError, "blocked operation 'pause'"),
            ("docker unpause mycontainer", ValueError, "blocked operation 'unpause'"),
            ("docker kill mycontainer", ValueError, "blocked operation 'kill'"),
            ("docker remove mycontainer", ValueError, "blocked operation 'remove'"),
            ("docker rm mycontainer", ValueError, "blocked operation 'rm'"),
            ("docker exec mycontainer ls", ValueError, "blocked operation 'exec'"),
            ("docker attach mycontainer", ValueError, "blocked operation 'attach'"),
            ("docker cp mycontainer:/file .", ValueError, "blocked operation 'cp'"),
            ("docker commit mycontainer", ValueError, "blocked operation 'commit'"),
            ("docker update mycontainer", ValueError, "blocked operation 'update'"),
            ("docker rename mycontainer newname", ValueError, "blocked operation 'rename'"),
            ("docker wait mycontainer", ValueError, "blocked operation 'wait'"),
            
            # Image operations
            ("docker build .", ValueError, "blocked operation 'build'"),
            ("docker pull nginx", ValueError, "blocked operation 'pull'"),
            ("docker push myimage", ValueError, "blocked operation 'push'"),
            ("docker tag nginx myimage", ValueError, "blocked operation 'tag'"),
            ("docker untag myimage", ValueError, "blocked operation 'untag'"),
            ("docker rmi nginx", ValueError, "blocked operation 'rmi'"),
            ("docker load < image.tar", ValueError, "blocked operation 'load'"),
            ("docker import image.tar", ValueError, "blocked operation 'import'"),
            ("docker save nginx", ValueError, "blocked operation 'save'"),
            
            # Network operations
            ("docker network create mynetwork", ValueError, "blocked operation 'network create'"),
            ("docker network rm mynetwork", ValueError, "blocked operation 'network rm'"),
            ("docker network remove mynetwork", ValueError, "blocked operation 'network remove'"),
            ("docker network connect mynetwork mycontainer", ValueError, "blocked operation 'network connect'"),
            ("docker network disconnect mynetwork mycontainer", ValueError, "blocked operation 'network disconnect'"),
            ("docker network prune", ValueError, "blocked operation 'network prune'"),
            
            # Volume operations
            ("docker volume create myvolume", ValueError, "blocked operation 'volume create'"),
            ("docker volume rm myvolume", ValueError, "blocked operation 'volume rm'"),
            ("docker volume remove myvolume", ValueError, "blocked operation 'volume remove'"),
            ("docker volume prune", ValueError, "blocked operation 'volume prune'"),
            
            # System operations
            ("docker system prune", ValueError, "blocked operation 'system prune'"),
            ("docker container prune", ValueError, "blocked operation 'container prune'"),
            ("docker image prune", ValueError, "blocked operation 'image prune'"),
            
            # Registry operations
            ("docker login", ValueError, "blocked operation 'login'"),
            ("docker logout", ValueError, "blocked operation 'logout'"),
            
            # Plugin operations
            ("docker plugin install myplugin", ValueError, "blocked operation 'plugin install'"),
            ("docker plugin enable myplugin", ValueError, "blocked operation 'plugin enable'"),
            ("docker plugin disable myplugin", ValueError, "blocked operation 'plugin disable'"),
            ("docker plugin upgrade myplugin", ValueError, "blocked operation 'plugin upgrade'"),
            ("docker plugin rm myplugin", ValueError, "blocked operation 'plugin rm'"),
            ("docker plugin remove myplugin", ValueError, "blocked operation 'plugin remove'"),
            ("docker plugin push myplugin", ValueError, "blocked operation 'plugin push'"),
            ("docker plugin create myplugin", ValueError, "blocked operation 'plugin create'"),
            ("docker plugin set myplugin", ValueError, "blocked operation 'plugin set'"),
            
            # Swarm operations
            ("docker swarm init", ValueError, "blocked operation 'swarm init'"),
            ("docker swarm join", ValueError, "blocked operation 'swarm join'"),
            ("docker swarm leave", ValueError, "blocked operation 'swarm leave'"),
            ("docker swarm update", ValueError, "blocked operation 'swarm update'"),
            ("docker swarm join-token", ValueError, "blocked operation 'swarm join-token'"),
            ("docker swarm unlock", ValueError, "blocked operation 'swarm unlock'"),
            ("docker swarm unlock-key", ValueError, "blocked operation 'swarm unlock-key'"),
            
            # Node operations
            ("docker node update mynode", ValueError, "blocked operation 'node update'"),
            ("docker node demote mynode", ValueError, "blocked operation 'node demote'"),
            ("docker node promote mynode", ValueError, "blocked operation 'node promote'"),
            ("docker node rm mynode", ValueError, "blocked operation 'node rm'"),
            ("docker node remove mynode", ValueError, "blocked operation 'node remove'"),
            
            # Service operations
            ("docker service create myservice", ValueError, "blocked operation 'service create'"),
            ("docker service update myservice", ValueError, "blocked operation 'service update'"),
            ("docker service scale myservice=3", ValueError, "blocked operation 'service scale'"),
            ("docker service rm myservice", ValueError, "blocked operation 'service rm'"),
            ("docker service remove myservice", ValueError, "blocked operation 'service remove'"),
            ("docker service rollback myservice", ValueError, "blocked operation 'service rollback'"),
            
            # Stack operations
            ("docker stack deploy mystack", ValueError, "blocked operation 'stack deploy'"),
            ("docker stack rm mystack", ValueError, "blocked operation 'stack rm'"),
            ("docker stack remove mystack", ValueError, "blocked operation 'stack remove'"),
            
            # Secret operations
            ("docker secret create mysecret", ValueError, "blocked operation 'secret create'"),
            ("docker secret rm mysecret", ValueError, "blocked operation 'secret rm'"),
            ("docker secret remove mysecret", ValueError, "blocked operation 'secret remove'"),
            
            # Config operations
            ("docker config create myconfig", ValueError, "blocked operation 'config create'"),
            ("docker config rm myconfig", ValueError, "blocked operation 'config rm'"),
            ("docker config remove myconfig", ValueError, "blocked operation 'config remove'"),
            
            # Context operations
            ("docker context create mycontext", ValueError, "blocked operation 'context create'"),
            ("docker context rm mycontext", ValueError, "blocked operation 'context rm'"),
            ("docker context remove mycontext", ValueError, "blocked operation 'context remove'"),
            ("docker context update mycontext", ValueError, "blocked operation 'context update'"),
            ("docker context use mycontext", ValueError, "blocked operation 'context use'"),
            ("docker context export mycontext", ValueError, "blocked operation 'context export'"),
            ("docker context import mycontext", ValueError, "blocked operation 'context import'"),
            
            # Buildx operations
            ("docker buildx build .", ValueError, "blocked operation 'buildx'"),
            ("docker buildx create", ValueError, "blocked operation 'buildx'"),
            
            # Compose operations
            ("docker compose up", ValueError, "blocked operation 'compose'"),
            ("docker compose down", ValueError, "blocked operation 'compose'"),
            
            # Trust operations
            ("docker trust sign myimage", ValueError, "blocked operation 'trust'"),
            ("docker trust revoke myimage", ValueError, "blocked operation 'trust'"),
            
            # Manifest operations
            ("docker manifest create mymanifest", ValueError, "blocked operation 'manifest'"),
            ("docker manifest push mymanifest", ValueError, "blocked operation 'manifest'"),
            
            # Checkpoint operations
            ("docker checkpoint create mycontainer", ValueError, "blocked operation 'checkpoint'"),
            ("docker checkpoint restore mycontainer", ValueError, "blocked operation 'checkpoint'"),
            
            # Invalid command
            ("docker nonexistent", ValueError, "not supported or command"),
            
            # Invalid format
            ("docker ps --format invalid", ValueError, "not allowed"),
            
            # Invalid resource name format
            ("docker container inspect 'invalid@name#'", ValueError, "Invalid Docker resource name format"),
            ("docker network inspect 'invalid network name'", ValueError, "Invalid Docker network name format"),
            ("docker volume inspect 'invalid@volume'", ValueError, "Invalid Docker volume name format"),
            
            # Unknown flags
            ("docker ps --malicious-flag", ValueError, "Unknown or unsafe"),
            ("docker images --evil-option value", ValueError, "Unknown or unsafe"),
        ],
    )
    def test_docker_unsafe_commands(
        self, command: str, expected_exception: type, partial_error_message_content: str
    ):
        """Test that unsafe Docker commands are properly rejected."""
        config = BashExecutorConfig()
        with pytest.raises(expected_exception) as exc_info:
            make_command_safe(command, config=config)

        if partial_error_message_content:
            assert partial_error_message_content in str(exc_info.value)


class TestDockerCliEdgeCases:
    """Test edge cases and error conditions for Docker CLI parsing."""

    def test_docker_with_grep_combination(self):
        """Test Docker commands combined with grep."""
        config = BashExecutorConfig()

        # Valid combination
        result = make_command_safe("docker ps | grep nginx", config=config)
        assert result == "docker ps | grep nginx"

        # Invalid - unsafe Docker command with grep
        with pytest.raises(ValueError):
            make_command_safe("docker run nginx | grep success", config=config)

    def test_docker_empty_command(self):
        """Test Docker commands with missing command."""
        config = BashExecutorConfig()

        # Missing command should fail at argument parsing level
        with pytest.raises((argparse.ArgumentError, ValueError)):
            make_command_safe("docker", config=config)

    def test_docker_help_commands(self):
        """Test Docker help commands are allowed."""
        config = BashExecutorConfig()

        # Global help
        result = make_command_safe("docker --help", config=config)
        assert result == "docker --help"

        # Command help
        result = make_command_safe("docker ps --help", config=config)
        assert result == "docker ps --help"

    def test_docker_complex_valid_parameters(self):
        """Test Docker commands with complex but valid parameters."""
        config = BashExecutorConfig()

        # Complex container listing with multiple filters
        complex_cmd = "docker ps --all --filter status=running --filter name=web --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}' --no-trunc"
        result = make_command_safe(complex_cmd, config=config)
        assert "docker ps" in result
        assert "--all" in result
        assert "--filter status=running" in result
        assert "--filter name=web" in result
        assert "--format" in result
        assert "--no-trunc" in result

    def test_docker_image_name_validation(self):
        """Test Docker image name validation."""
        config = BashExecutorConfig()

        # Valid image names
        valid_images = [
            "nginx", 
            "nginx:latest",
            "registry.io/nginx:v1.0",
            "localhost:5000/myapp",
        ]
        
        for image in valid_images:
            result = make_command_safe(f"docker image inspect {image}", config=config)
            assert f"docker image inspect {image}" == result

    def test_docker_container_name_validation(self):
        """Test Docker container name validation."""
        config = BashExecutorConfig()

        # Valid container names
        valid_names = [
            "mycontainer",
            "my-container",
            "my_container", 
            "container123",
            "web-server-1",
        ]
        
        for name in valid_names:
            result = make_command_safe(f"docker container inspect {name}", config=config)
            assert f"docker container inspect {name}" == result

    def test_docker_case_sensitivity(self):
        """Test that Docker commands are case-sensitive where appropriate."""
        config = BashExecutorConfig()

        # Commands should be lowercase
        with pytest.raises(ValueError):
            make_command_safe("docker PS", config=config)

        # Container names are case-sensitive (should be allowed)
        result = make_command_safe("docker container inspect MyContainer", config=config)
        assert result == "docker container inspect MyContainer"