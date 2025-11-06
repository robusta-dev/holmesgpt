import asyncio
import json
import logging
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from pydantic import BaseModel

from holmes.core.config import config_path_dir


logger = logging.getLogger(__name__)


class OAuthMetadata(BaseModel):
    """OAuth 2.0 Authorization Server Metadata"""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: Optional[str] = None
    scopes_supported: Optional[list[str]] = None


class MCPOAuthAuth(httpx.Auth):
    """OAuth authentication for MCP servers using Authlib"""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        # Extract the base domain for OAuth metadata discovery
        # e.g., https://mcp.atlassian.com/v1/sse -> https://mcp.atlassian.com
        from urllib.parse import urlparse

        parsed = urlparse(self.server_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"

        self.token_store_path = Path(config_path_dir) / "auth" / "mcp_tokens.json"
        self.token_store_path.parent.mkdir(parents=True, exist_ok=True)

        self.token: Optional[dict] = self._load_token()
        self.oauth_metadata: Optional[OAuthMetadata] = None
        self.oauth_client: Optional[AsyncOAuth2Client] = None
        self._callback_code: Optional[str] = None
        self._callback_error: Optional[str] = None
        self._callback_event = threading.Event()

    def _load_token(self) -> Optional[dict]:
        """Load token from storage"""
        if not self.token_store_path.exists():
            return None

        try:
            with open(self.token_store_path, "r") as f:
                tokens = json.load(f)
                token_data = tokens.get(self.server_url)
                if token_data:
                    return token_data
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
        return None

    def _save_token(self, token: dict) -> None:
        """Save token to storage"""
        tokens = {}
        if self.token_store_path.exists():
            try:
                with open(self.token_store_path, "r") as f:
                    tokens = json.load(f)
            except Exception:
                pass

        tokens[self.server_url] = token
        with open(self.token_store_path, "w") as f:
            json.dump(tokens, f, indent=2)

    def _is_token_expired(self, token: dict) -> bool:
        """Check if token is expired"""
        if "expires_at" not in token:
            return False  # No expiry info, assume valid

        return token["expires_at"] < time.time()

    def has_valid_token(self) -> bool:
        """Check if we have a valid (non-expired) token"""
        if not self.token:
            return False

        # Check if token is expired
        if self._is_token_expired(self.token):
            return False

        return True

    async def discover_oauth_metadata(self) -> OAuthMetadata:
        """Discover OAuth endpoints from .well-known/oauth-authorization-server"""
        # Try the standard oauth-authorization-server endpoint first (used by Atlassian)
        metadata_urls = [
            f"{self.base_url}/.well-known/oauth-authorization-server",
            f"{self.base_url}/.well-known/oauth-metadata",
        ]

        async with httpx.AsyncClient() as client:
            for metadata_url in metadata_urls:
                try:
                    response = await client.get(metadata_url)
                    response.raise_for_status()
                    data = response.json()
                    return OAuthMetadata(**data)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        continue  # Try next URL
                    raise

            # If we get here, none of the URLs worked
            raise Exception(
                "OAuth metadata discovery failed. Server doesn't support "
                ".well-known/oauth-authorization-server or .well-known/oauth-metadata"
            )

    async def _register_client(self, redirect_uri: str) -> dict:
        """Dynamically register OAuth client"""
        registration_data = {
            "client_name": "HolmesGPT MCP Client",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",  # Public client
        }

        if not self.oauth_metadata or not self.oauth_metadata.registration_endpoint:
            raise ValueError("OAuth metadata or registration endpoint not available")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.oauth_metadata.registration_endpoint,
                json=registration_data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    def authenticate(self) -> None:
        """Perform OAuth authentication flow"""
        # Run async authentication in sync context
        asyncio.run(self._authenticate_async())

    async def _authenticate_async(self) -> None:
        """Async OAuth authentication flow"""
        # Discover OAuth metadata
        print("Discovering OAuth configuration...")
        self.oauth_metadata = await self.discover_oauth_metadata()

        # Start callback server first to get the port
        server, port = self._start_callback_server()
        redirect_uri = f"http://localhost:{port}/callback"

        # Try to dynamically register client if registration endpoint exists
        client_id = "holmes-mcp-client"
        client_secret = None

        if self.oauth_metadata.registration_endpoint:
            print("Registering OAuth client...")
            try:
                client_info = await self._register_client(redirect_uri)
                client_id = client_info.get("client_id", client_id)
                client_secret = client_info.get("client_secret")
                print(f"Client registered successfully: {client_id}")
            except Exception as e:
                print(f"Client registration failed: {e}")
                print("Continuing with default client ID...")

        # Create OAuth client
        self.oauth_client = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            authorization_endpoint=self.oauth_metadata.authorization_endpoint,
            token_endpoint=self.oauth_metadata.token_endpoint,
        )

        try:
            # Generate authorization URL with PKCE
            authorization_url, state = self.oauth_client.create_authorization_url(
                self.oauth_metadata.authorization_endpoint, code_challenge_method="S256"
            )

            print("\nOpening browser for authentication...")
            print(f"If browser doesn't open, visit: {authorization_url}\n")

            # Open browser
            webbrowser.open(authorization_url)

            # Wait for callback
            print("Waiting for authentication...")
            self._callback_event.wait(timeout=300)  # 5 minute timeout

            if self._callback_error:
                raise Exception(f"OAuth error: {self._callback_error}")

            if not self._callback_code:
                raise Exception("No authorization code received")

            # Exchange code for token
            print("Exchanging authorization code for token...")
            token = await self.oauth_client.fetch_token(
                self.oauth_metadata.token_endpoint,
                authorization_response=f"http://localhost:{port}/callback?code={self._callback_code}&state={state}",
                include_client_id=True,
            )

            self.token = token
            self._save_token(self.token)
            print("Authentication successful!")

        finally:
            server.shutdown()

    def _start_callback_server(self) -> tuple[HTTPServer, int]:
        """Start local HTTP server for OAuth callback"""
        parent = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Parse query parameters
                query = urlparse(self.path).query
                params = parse_qs(query)

                # Extract code or error
                if "code" in params:
                    parent._callback_code = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>"
                    )
                else:
                    parent._callback_error = params.get("error", ["Unknown error"])[0]
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        f"<html><body><h1>Authentication failed</h1><p>Error: {parent._callback_error}</p></body></html>".encode()
                    )

                # Signal completion
                parent._callback_event.set()

            def log_message(self, format, *args):
                # Suppress request logging
                pass

        # Try to find an available port
        import socket

        for port in range(8080, 8090):
            try:
                server = HTTPServer(("localhost", port), CallbackHandler)
                thread = threading.Thread(target=server.serve_forever)
                thread.daemon = True
                thread.start()
                return server, port
            except socket.error:
                continue

        raise Exception("Could not find available port for OAuth callback server")

    def auth_flow(self, request: httpx.Request):
        """Implement httpx.Auth interface"""
        # Add bearer token if available
        if self.token:
            request.headers["Authorization"] = f"Bearer {self.token['access_token']}"
        yield request

    async def async_auth_flow(self, request: httpx.Request):
        """Async version of auth_flow for httpx async client"""
        # Check if token needs refresh
        if (
            self.token
            and self._is_token_expired(self.token)
            and "refresh_token" in self.token
        ):
            # Refresh token
            logger.info("Refreshing expired OAuth token")
            if not self.oauth_metadata:
                self.oauth_metadata = await self.discover_oauth_metadata()

            if not self.oauth_client:
                self.oauth_client = AsyncOAuth2Client(
                    client_id="holmes-mcp-client",
                    token=dict(self.token),
                    token_endpoint=self.oauth_metadata.token_endpoint,
                )

            new_token = await self.oauth_client.refresh_token(
                self.oauth_metadata.token_endpoint,
                refresh_token=self.token["refresh_token"],
            )
            self.token = new_token
            self._save_token(self.token)

        # Add bearer token if available
        if self.token:
            request.headers["Authorization"] = f"Bearer {self.token['access_token']}"
        yield request
