import requests
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

@dataclass
class InfraInsightsConfig:
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    enable_name_lookup: bool = True
    use_v2_api: bool = True

@dataclass 
class ServiceInstance:
    instanceId: str
    serviceType: str
    name: str
    description: str = ""
    environment: str = "production"
    status: str = "active"
    config: Dict[str, Any] = None
    ownerId: str = ""
    tags: List[str] = None
    healthCheck: Dict[str, Any] = None
    createdAt: str = ""
    updatedAt: str = ""

class InfraInsightsClientV2:
    """Updated InfraInsights client that supports name-based instance resolution"""
    
    def __init__(self, config: InfraInsightsConfig):
        self.config = config
        self.session = requests.Session()
        
        # Configure authentication
        if config.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json'
            })
        elif config.username and config.password:
            self.session.auth = (config.username, config.password)
            self.session.headers.update({'Content-Type': 'application/json'})
        
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info(f"InfraInsights Client V2 initialized - Name lookup: {config.enable_name_lookup}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to InfraInsights API"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, timeout=self.config.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"InfraInsights API request failed: {e}")
            raise Exception(f"Failed to connect to InfraInsights API: {e}")

    def health_check(self) -> bool:
        """Check if InfraInsights API is accessible"""
        try:
            logger.info(f"🔍 Health check: Calling {self.config.base_url}/api/health")
            response = self._make_request('GET', '/api/health')
            logger.info(f"🔍 Health check response: {response}")
            is_healthy = response.get('status') == 'healthy' or 'status' in response
            logger.info(f"🔍 Health check result: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_service_instances(self, service_type: Optional[str] = None, user_id: Optional[str] = None) -> List[ServiceInstance]:
        """Get service instances, optionally filtered by type and user access"""
        cache_key = f"instances:{service_type}:{user_id}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return cached_data

        try:
            # Build API endpoint
            if service_type:
                endpoint = f'/api/service-instances/{service_type}'
            else:
                endpoint = '/api/service-instances'
            
            # Make API request
            params = {}
            if user_id:
                params['userId'] = user_id
                
            data = self._make_request('GET', endpoint, params=params)
            
            # Parse response - handle both old and new response formats
            instances_data = data.get('data', data.get('instances', []))
            
            instances = []
            for instance_data in instances_data:
                try:
                    # Handle both old and new field names
                    instance = ServiceInstance(
                        instanceId=instance_data.get('instanceId', instance_data.get('id', '')),
                        serviceType=instance_data.get('serviceType', service_type or ''),
                        name=instance_data.get('name', ''),
                        description=instance_data.get('description', ''),
                        environment=instance_data.get('environment', 'production'),
                        status=instance_data.get('status', 'active'),
                        config=instance_data.get('config', {}),
                        ownerId=instance_data.get('ownerId', ''),
                        tags=instance_data.get('tags', []),
                        healthCheck=instance_data.get('healthCheck', {}),
                        createdAt=instance_data.get('createdAt', ''),
                        updatedAt=instance_data.get('updatedAt', '')
                    )
                    instances.append(instance)
                except Exception as e:
                    logger.warning(f"Failed to parse service instance: {e}")

            # Cache result
            self._cache[cache_key] = (instances, datetime.now())
            
            logger.info(f"Retrieved {len(instances)} {service_type or 'service'} instances")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to get service instances: {e}")
            return []

    def get_instance_by_id(self, instance_id: str, include_config: bool = True) -> Optional[ServiceInstance]:
        """Get a specific instance by ID"""
        try:
            params = {'includeConfig': 'true'} if include_config else {}
            data = self._make_request('GET', f'/api/service-instances/{instance_id}', params=params)
            
            instance_data = data.get('data', data)
            if instance_data:
                return ServiceInstance(
                    instanceId=instance_data.get('instanceId', instance_data.get('id', '')),
                    serviceType=instance_data.get('serviceType', ''),
                    name=instance_data.get('name', ''),
                    description=instance_data.get('description', ''),
                    environment=instance_data.get('environment', 'production'),
                    status=instance_data.get('status', 'active'),
                    config=instance_data.get('config', {}),
                    ownerId=instance_data.get('ownerId', ''),
                    tags=instance_data.get('tags', []),
                    healthCheck=instance_data.get('healthCheck', {}),
                    createdAt=instance_data.get('createdAt', ''),
                    updatedAt=instance_data.get('updatedAt', '')
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get instance by ID {instance_id}: {e}")
            return None

    def get_instance_by_name_and_type(self, service_type: str, name: str, include_config: bool = True) -> Optional[ServiceInstance]:
        """Get a specific instance by name and service type (NEW API ENDPOINT)"""
        if not self.config.enable_name_lookup:
            logger.warning("Name-based lookup is disabled")
            return None
            
        try:
            # Use the new backend endpoint that supports name lookup
            params = {'includeConfig': 'true'} if include_config else {}
            endpoint = f'/api/service-instances/{service_type}/{name}'
            
            logger.info(f"🔍 Constructing URL with service_type='{service_type}', name='{name}'")
            logger.info(f"🔍 Final endpoint: {endpoint}")
            logger.info(f"🔍 Full URL: {self.config.base_url}{endpoint}")
            data = self._make_request('GET', endpoint, params=params)
            
            # CRITICAL DEBUG: Show raw API response
            logger.info(f"🔍 RAW API RESPONSE: {json.dumps(data, indent=2)}")
            
            instance_data = data.get('data', data)
            if instance_data:
                # CRITICAL DEBUG: Show instance data before ServiceInstance creation
                logger.info(f"🔍 INSTANCE DATA: {json.dumps(instance_data, indent=2)}")
                logger.info(f"🔍 CONFIG IN INSTANCE DATA: {instance_data.get('config', {})}")
                instance = ServiceInstance(
                    instanceId=instance_data.get('instanceId', instance_data.get('id', '')),
                    serviceType=instance_data.get('serviceType', service_type),
                    name=instance_data.get('name', name),
                    description=instance_data.get('description', ''),
                    environment=instance_data.get('environment', 'production'),
                    status=instance_data.get('status', 'active'),
                    config=instance_data.get('config', {}),
                    ownerId=instance_data.get('ownerId', ''),
                    tags=instance_data.get('tags', []),
                    healthCheck=instance_data.get('healthCheck', {}),
                    createdAt=instance_data.get('createdAt', ''),
                    updatedAt=instance_data.get('updatedAt', '')
                )
                logger.info(f"✅ Found instance by name: {name} -> {instance.instanceId}")
                return instance
            return None
        except Exception as e:
            logger.error(f"Failed to get instance by name {name} in service type {service_type}: {e}")
            return None

    def resolve_instance(self, service_type: str, identifier: str, user_id: Optional[str] = None) -> Optional[ServiceInstance]:
        """
        Resolve an instance by identifier (could be ID or name)
        This method tries multiple strategies to find the instance
        """
        logger.info(f"Resolving {service_type} instance: '{identifier}'")
        
        # Strategy 1: Try direct ID lookup first
        try:
            instance = self.get_instance_by_id(identifier, include_config=True)
            if instance and instance.serviceType == service_type:
                logger.info(f"✅ Resolved by ID: {identifier}")
                return instance
        except Exception as e:
            logger.debug(f"ID lookup failed: {e}")

        # Strategy 2: Try name-based lookup (if enabled)
        if self.config.enable_name_lookup:
            try:
                instance = self.get_instance_by_name_and_type(service_type, identifier, include_config=True)
                if instance:
                    logger.info(f"✅ Resolved by name: {identifier} -> {instance.instanceId}")
                    return instance
            except Exception as e:
                logger.debug(f"Name lookup failed: {e}")

        # Strategy 3: Search through all instances of the service type
        try:
            instances = self.get_service_instances(service_type, user_id)
            
            # Try exact name match
            for instance in instances:
                if instance.name == identifier:
                    logger.info(f"✅ Resolved by search (exact name): {identifier}")
                    return instance
            
            # Try case-insensitive name match
            identifier_lower = identifier.lower()
            for instance in instances:
                if instance.name.lower() == identifier_lower:
                    logger.info(f"✅ Resolved by search (case-insensitive): {identifier}")
                    return instance
            
            # Try partial name match
            for instance in instances:
                if identifier_lower in instance.name.lower():
                    logger.info(f"✅ Resolved by search (partial match): {identifier} -> {instance.name}")
                    return instance
                    
        except Exception as e:
            logger.error(f"Search through instances failed: {e}")

        logger.warning(f"❌ Could not resolve instance: {identifier}")
        return None

    def identify_instance_from_prompt(self, prompt: str, service_type: str, user_id: Optional[str] = None) -> Optional[ServiceInstance]:
        """Identify instance from user prompt using smart parsing"""
        if not prompt:
            return None

        try:
            # Simple pattern matching for instance names
            import re
            
            # Enhanced patterns to capture instance names in various formats
            patterns = [
                # Specific name patterns with colons (highest priority)
                r'cluster_name:\s*([a-zA-Z0-9\-_]+)',
                r'instance_name:\s*([a-zA-Z0-9\-_]+)',
                r'service_name:\s*([a-zA-Z0-9\-_]+)',
                
                # Direct mentions with service types
                r'([a-zA-Z0-9\-_]+)\s+elasticsearch(?:\s+cluster)?',
                r'([a-zA-Z0-9\-_]+)\s+kafka(?:\s+cluster)?',
                r'([a-zA-Z0-9\-_]+)\s+mongodb(?:\s+cluster)?',
                r'([a-zA-Z0-9\-_]+)\s+redis(?:\s+cluster)?',
                r'([a-zA-Z0-9\-_]+)\s+kubernetes(?:\s+cluster)?',
                
                # "my" patterns
                r'my\s+([a-zA-Z0-9\-_]+)(?:\s+(?:instance|cluster|service))?',
                
                # Generic patterns (lower priority)
                r'(?:instance|cluster|service)\s+([a-zA-Z0-9\-_]+)',
                r'([a-zA-Z0-9\-_]{3,})(?:\s+(?:instance|cluster|service))',
            ]
            
            logger.info(f"🔍 Parsing prompt for {service_type} instance: '{prompt}'")
            
            for i, pattern in enumerate(patterns):
                matches = re.findall(pattern, prompt.lower())
                logger.info(f"🔍 Pattern {i+1}: '{pattern}' -> matches: {matches}")
                
                for match in matches:
                    if len(match) > 2:  # Skip very short matches
                        logger.info(f"🔍 Trying to resolve: '{match}'")
                        instance = self.resolve_instance(service_type, match, user_id)
                        if instance:
                            logger.info(f"✅ SUCCESS: Identified from prompt: '{match}' -> {instance.name}")
                            return instance
                        else:
                            logger.info(f"❌ No instance found for: '{match}'")
            
            return None
        except Exception as e:
            logger.error(f"Failed to identify instance from prompt: {e}")
            return None

    def get_service_instance_summary(self, service_type: str) -> Dict[str, Any]:
        """Get a summary of available instances for a service type"""
        try:
            instances = self.get_service_instances(service_type)
            
            summary = {
                "service_type": service_type,
                "total_instances": len(instances),
                "active_instances": len([i for i in instances if i.status == 'active']),
                "environments": list(set(i.environment for i in instances if i.environment)),
                "instance_names": [i.name for i in instances],
                "api_accessible": True,
                "name_lookup_enabled": self.config.enable_name_lookup
            }
            
            return summary
        except Exception as e:
            return {
                "service_type": service_type,
                "total_instances": 0,
                "active_instances": 0,
                "environments": [],
                "instance_names": [],
                "api_accessible": False,
                "name_lookup_enabled": self.config.enable_name_lookup,
                "error": str(e)
            }

    def get_elasticsearch_health(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch cluster health for a specific instance"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            es_url = instance.config.get('elasticsearchUrl')
            username = instance.config.get('username')
            password = instance.config.get('password')
            service_type = instance.config.get('type', 'elasticsearch').lower()
            
            if not es_url:
                raise Exception("Elasticsearch/OpenSearch URL not found in instance configuration")
            
            logger.info(f"🔍 Detected service type: {service_type}")
            
            # Configure client based on service type
            client_config = {
                'hosts': [es_url],
                'verify_certs': False,
                'request_timeout': 30
            }
            
            # Create appropriate client based on service type
            if service_type == 'opensearch':
                logger.info("🔍 Using OpenSearch client")
                try:
                    from opensearchpy import OpenSearch
                    
                    # OpenSearch client uses different auth parameter format
                    if username and password:
                        client_config['http_auth'] = (username, password)
                        logger.info(f"🔍 OpenSearch auth configured: username={username}")
                    
                    config_display = {k: ('***' if k == 'http_auth' else v) for k, v in client_config.items()}
                    logger.info(f"🔍 OpenSearch client config: {config_display}")
                    client = OpenSearch(**client_config)
                except ImportError:
                    logger.warning("OpenSearch client not available, falling back to direct HTTP requests")
                    # For OpenSearch, we can use requests directly or try compatibility mode
                    import requests
                    import json as json_lib
                    
                    # Use direct HTTP request for OpenSearch compatibility
                    auth = (username, password) if username and password else None
                    health_url = f"{es_url.rstrip('/')}/_cluster/health"
                    
                    response = requests.get(health_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    health_response = response.json()
                    
                    return {
                        'instance_name': instance.name,
                        'instance_id': instance.instanceId,
                        'cluster_name': health_response.get('cluster_name'),
                        'status': health_response.get('status'),
                        'number_of_nodes': health_response.get('number_of_nodes'),
                        'active_primary_shards': health_response.get('active_primary_shards'),
                        'active_shards': health_response.get('active_shards'),
                        'relocating_shards': health_response.get('relocating_shards'),
                        'initializing_shards': health_response.get('initializing_shards'),
                        'unassigned_shards': health_response.get('unassigned_shards'),
                        'delayed_unassigned_shards': health_response.get('delayed_unassigned_shards'),
                        'number_of_pending_tasks': health_response.get('number_of_pending_tasks'),
                        'number_of_in_flight_fetch': health_response.get('number_of_in_flight_fetch'),
                        'task_max_waiting_in_queue_millis': health_response.get('task_max_waiting_in_queue_millis'),
                        'active_shards_percent_as_number': health_response.get('active_shards_percent_as_number'),
                        'service_type': 'opensearch'
                    }
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                # Elasticsearch client uses basic_auth parameter
                if username and password:
                    client_config['basic_auth'] = (username, password)
                    logger.info(f"🔍 Elasticsearch auth configured: username={username}")
                
                config_display = {k: ('***' if k == 'basic_auth' else v) for k, v in client_config.items()}
                logger.info(f"🔍 Elasticsearch client config: {config_display}")
                client = Elasticsearch(**client_config)
            
            # Get cluster health using the appropriate client
            if service_type != 'opensearch' or 'client' in locals():
                health_response = client.cluster.health()
                
                return {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'cluster_name': health_response.get('cluster_name'),
                    'status': health_response.get('status'),
                    'number_of_nodes': health_response.get('number_of_nodes'),
                    'active_primary_shards': health_response.get('active_primary_shards'),
                    'active_shards': health_response.get('active_shards'),
                    'relocating_shards': health_response.get('relocating_shards'),
                    'initializing_shards': health_response.get('initializing_shards'),
                    'unassigned_shards': health_response.get('unassigned_shards'),
                    'delayed_unassigned_shards': health_response.get('delayed_unassigned_shards'),
                    'number_of_pending_tasks': health_response.get('number_of_pending_tasks'),
                    'number_of_in_flight_fetch': health_response.get('number_of_in_flight_fetch'),
                    'task_max_waiting_in_queue_millis': health_response.get('task_max_waiting_in_queue_millis'),
                    'active_shards_percent_as_number': health_response.get('active_shards_percent_as_number'),
                    'service_type': service_type
                }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch health for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch cluster health: {str(e)}")

    def get_elasticsearch_indices(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch indices for a specific instance"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            es_url = instance.config.get('elasticsearchUrl')
            username = instance.config.get('username')
            password = instance.config.get('password')
            service_type = instance.config.get('type', 'elasticsearch').lower()
            
            if not es_url:
                raise Exception("Elasticsearch/OpenSearch URL not found in instance configuration")
            
            logger.info(f"🔍 Detected service type: {service_type}")
            
            # Configure client based on service type
            client_config = {
                'hosts': [es_url],
                'verify_certs': False,
                'request_timeout': 30
            }
            
            # Create appropriate client based on service type
            if service_type == 'opensearch':
                logger.info("🔍 Using OpenSearch-compatible approach")
                try:
                    from opensearchpy import OpenSearch
                    
                    # OpenSearch client uses different auth parameter format
                    if username and password:
                        client_config['http_auth'] = (username, password)
                        logger.info(f"🔍 OpenSearch auth configured: username={username}")
                    
                    config_display = {k: ('***' if k == 'http_auth' else v) for k, v in client_config.items()}
                    logger.info(f"🔍 OpenSearch client config: {config_display}")
                    client = OpenSearch(**client_config)
                    indices_response = client.cat.indices(format='json', v=True)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    # Use direct HTTP request for OpenSearch compatibility
                    import requests
                    
                    auth = (username, password) if username and password else None
                    indices_url = f"{es_url.rstrip('/')}/_cat/indices?format=json&v=true"
                    
                    response = requests.get(indices_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    indices_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                # Elasticsearch client uses basic_auth parameter
                if username and password:
                    client_config['basic_auth'] = (username, password)
                    logger.info(f"🔍 Elasticsearch auth configured: username={username}")
                
                config_display = {k: ('***' if k == 'basic_auth' else v) for k, v in client_config.items()}
                logger.info(f"🔍 Elasticsearch client config: {config_display}")
                client = Elasticsearch(**client_config)
                indices_response = client.cat.indices(format='json', v=True)
            
            # Format indices data (same format for both)
            indices = []
            for index_info in indices_response:
                indices.append({
                    'index': index_info.get('index'),
                    'health': index_info.get('health'),
                    'status': index_info.get('status'),
                    'docs_count': index_info.get('docs.count'),
                    'docs_deleted': index_info.get('docs.deleted'),
                    'store_size': index_info.get('store.size'),
                    'pri_store_size': index_info.get('pri.store.size')
                })
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'total_indices': len(indices),
                'indices': indices,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch indices for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch indices: {str(e)}") 