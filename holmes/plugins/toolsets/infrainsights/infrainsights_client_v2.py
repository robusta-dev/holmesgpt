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

    def get_elasticsearch_cluster_stats(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch cluster-wide statistics"""
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
                    
                    client = OpenSearch(**client_config)
                    stats_response = client.cluster.stats()
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    stats_url = f"{es_url.rstrip('/')}/_cluster/stats"
                    
                    response = requests.get(stats_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    stats_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                # Elasticsearch client uses basic_auth parameter
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                stats_response = client.cluster.stats()
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'cluster_stats': stats_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch cluster stats for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch cluster stats: {str(e)}")

    def get_elasticsearch_node_stats(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch node statistics"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    stats_response = client.nodes.stats()
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    stats_url = f"{es_url.rstrip('/')}/_nodes/stats"
                    
                    response = requests.get(stats_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    stats_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                stats_response = client.nodes.stats()
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'node_stats': stats_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch node stats for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch node stats: {str(e)}")

    def get_elasticsearch_index_stats(self, instance: ServiceInstance, index_name: Optional[str] = None) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch index statistics"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    if index_name:
                        stats_response = client.indices.stats(index=index_name)
                    else:
                        stats_response = client.indices.stats()
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    if index_name:
                        stats_url = f"{es_url.rstrip('/')}/{index_name}/_stats"
                    else:
                        stats_url = f"{es_url.rstrip('/')}/_stats"
                    
                    response = requests.get(stats_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    stats_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                if index_name:
                    stats_response = client.indices.stats(index=index_name)
                else:
                    stats_response = client.indices.stats()
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'index_name': index_name or 'all',
                'index_stats': stats_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch index stats for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch index stats: {str(e)}")

    def get_elasticsearch_shard_allocation(self, instance: ServiceInstance, index_name: Optional[str] = None) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch shard allocation information"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    if index_name:
                        shards_response = client.cat.shards(index=index_name, format='json', v=True)
                    else:
                        shards_response = client.cat.shards(format='json', v=True)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    if index_name:
                        shards_url = f"{es_url.rstrip('/')}/_cat/shards/{index_name}?v&format=json"
                    else:
                        shards_url = f"{es_url.rstrip('/')}/_cat/shards?v&format=json"
                    
                    response = requests.get(shards_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    shards_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                if index_name:
                    shards_response = client.cat.shards(index=index_name, format='json', v=True)
                else:
                    shards_response = client.cat.shards(format='json', v=True)
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'index_name': index_name or 'all',
                'shard_allocation': shards_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch shard allocation for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch shard allocation: {str(e)}")

    def get_elasticsearch_tasks(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch running tasks"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    tasks_response = client.tasks.list(detailed=True)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    tasks_url = f"{es_url.rstrip('/')}/_tasks?detailed"
                    
                    response = requests.get(tasks_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    tasks_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                tasks_response = client.tasks.list(detailed=True)
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'tasks': tasks_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch tasks for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch tasks: {str(e)}")

    def get_elasticsearch_pending_tasks(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch pending tasks"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    pending_response = client.cluster.pending_tasks()
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    pending_url = f"{es_url.rstrip('/')}/_cluster/pending_tasks"
                    
                    response = requests.get(pending_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    pending_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                pending_response = client.cluster.pending_tasks()
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'pending_tasks': pending_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch pending tasks for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch pending tasks: {str(e)}")

    def get_elasticsearch_thread_pool_stats(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch thread pool statistics"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    stats_response = client.nodes.stats(metric='thread_pool')
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    stats_url = f"{es_url.rstrip('/')}/_nodes/stats/thread_pool"
                    
                    response = requests.get(stats_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    stats_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                stats_response = client.nodes.stats(metric='thread_pool')
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'thread_pool_stats': stats_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch thread pool stats for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch thread pool stats: {str(e)}")

    def get_elasticsearch_index_mapping(self, instance: ServiceInstance, index_name: str) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch index mapping"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    mapping_response = client.indices.get_mapping(index=index_name)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    mapping_url = f"{es_url.rstrip('/')}/{index_name}/_mapping"
                    
                    response = requests.get(mapping_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    mapping_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                mapping_response = client.indices.get_mapping(index=index_name)
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'index_name': index_name,
                'mapping': mapping_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch index mapping for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch index mapping: {str(e)}")

    def get_elasticsearch_index_settings(self, instance: ServiceInstance, index_name: str) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch index settings"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    settings_response = client.indices.get_settings(index=index_name)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    settings_url = f"{es_url.rstrip('/')}/{index_name}/_settings"
                    
                    response = requests.get(settings_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    settings_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                settings_response = client.indices.get_settings(index=index_name)
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'index_name': index_name,
                'settings': settings_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch index settings for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch index settings: {str(e)}")

    def get_elasticsearch_hot_threads(self, instance: ServiceInstance, node_name: Optional[str] = None) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch hot threads analysis"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    if node_name:
                        hot_threads_response = client.nodes.hot_threads(node_id=node_name, threads=3)
                    else:
                        hot_threads_response = client.nodes.hot_threads(threads=3)
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    if node_name:
                        hot_threads_url = f"{es_url.rstrip('/')}/_nodes/{node_name}/hot_threads?threads=3"
                    else:
                        hot_threads_url = f"{es_url.rstrip('/')}/_nodes/hot_threads?threads=3"
                    
                    response = requests.get(hot_threads_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    hot_threads_response = response.text  # Hot threads returns text, not JSON
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                if node_name:
                    hot_threads_response = client.nodes.hot_threads(node_id=node_name, threads=3)
                else:
                    hot_threads_response = client.nodes.hot_threads(threads=3)
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'node_name': node_name or 'all',
                'hot_threads': hot_threads_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch hot threads for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch hot threads: {str(e)}")

    def get_elasticsearch_snapshot_status(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Elasticsearch/OpenSearch snapshot status"""
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
                    
                    if username and password:
                        client_config['http_auth'] = (username, password)
                    
                    client = OpenSearch(**client_config)
                    snapshot_response = client.snapshot.status()
                except ImportError:
                    logger.warning("OpenSearch client not available, using direct HTTP request")
                    import requests
                    
                    auth = (username, password) if username and password else None
                    snapshot_url = f"{es_url.rstrip('/')}/_snapshot/_status"
                    
                    response = requests.get(snapshot_url, auth=auth, verify=False, timeout=30)
                    response.raise_for_status()
                    snapshot_response = response.json()
            else:
                logger.info("🔍 Using Elasticsearch client")
                from elasticsearch import Elasticsearch
                
                if username and password:
                    client_config['basic_auth'] = (username, password)
                
                client = Elasticsearch(**client_config)
                snapshot_response = client.snapshot.status()
            
            return {
                'instance_name': instance.name,
                'instance_id': instance.instanceId,
                'snapshot_status': snapshot_response,
                'service_type': service_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get Elasticsearch/OpenSearch snapshot status for {instance.name}: {e}")
            raise Exception(f"Failed to get Elasticsearch/OpenSearch snapshot status: {str(e)}")

    # MongoDB client methods
    def get_mongodb_health(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get MongoDB instance health and server status"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Connecting to MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
                
                # Parse connection string and create client
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                
                # Test connection and get server status
                db = client[database]
                server_status = db.command("serverStatus")
                is_master = db.command("isMaster")
                
                # Get basic health metrics
                health_data = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'connection_status': 'healthy',
                    'server_status': {
                        'version': server_status.get('version'),
                        'uptime': server_status.get('uptime'),
                        'connections': server_status.get('connections'),
                        'mem': server_status.get('mem'),
                        'extra_info': server_status.get('extra_info'),
                        'host': server_status.get('host'),
                        'process': server_status.get('process')
                    },
                    'replica_set_status': {
                        'ismaster': is_master.get('ismaster'),
                        'secondary': is_master.get('secondary'),
                        'setName': is_master.get('setName'),
                        'hosts': is_master.get('hosts', []),
                        'primary': is_master.get('primary')
                    },
                    'timestamp': server_status.get('localTime')
                }
                
                client.close()
                return health_data
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            except ServerSelectionTimeoutError:
                raise Exception("Failed to connect to MongoDB server - timeout")
            except OperationFailure as e:
                raise Exception(f"MongoDB operation failed: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB health for {instance.name}: {e}")
            raise Exception(f"Failed to get MongoDB health: {str(e)}")

    def get_mongodb_databases(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get list of databases in MongoDB instance"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Getting databases for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                
                # List all databases
                db_list = client.list_database_names()
                
                databases_info = []
                for db_name in db_list:
                    db = client[db_name]
                    try:
                        stats = db.command("dbStats")
                        db_info = {
                            'name': db_name,
                            'sizeOnDisk': stats.get('storageSize', 0),
                            'dataSize': stats.get('dataSize', 0),
                            'indexSize': stats.get('indexSize', 0),
                            'collections': stats.get('collections', 0),
                            'objects': stats.get('objects', 0),
                            'avgObjSize': stats.get('avgObjSize', 0),
                            'indexes': stats.get('indexes', 0)
                        }
                        databases_info.append(db_info)
                    except Exception as e:
                        # Some databases might not allow dbStats
                        databases_info.append({
                            'name': db_name,
                            'error': f"Unable to get stats: {str(e)}"
                        })
                
                client.close()
                
                return {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'total_databases': len(databases_info),
                    'databases': databases_info
                }
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB databases for {instance.name}: {e}")
            raise Exception(f"Failed to get MongoDB databases: {str(e)}")

    def get_mongodb_collection_stats(self, instance: ServiceInstance, database_name: str, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get MongoDB collection statistics"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Getting collection stats for MongoDB instance: {instance.name}, database: {database_name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database_name]
                
                collections_stats = []
                
                if collection_name:
                    # Get stats for specific collection
                    collection_names = [collection_name]
                else:
                    # Get stats for all collections
                    collection_names = db.list_collection_names()
                
                for coll_name in collection_names:
                    try:
                        collection = db[coll_name]
                        stats = db.command("collStats", coll_name)
                        
                        # Get index information
                        indexes = list(collection.list_indexes())
                        
                        coll_stats = {
                            'name': coll_name,
                            'count': stats.get('count', 0),
                            'size': stats.get('size', 0),
                            'storageSize': stats.get('storageSize', 0),
                            'totalIndexSize': stats.get('totalIndexSize', 0),
                            'avgObjSize': stats.get('avgObjSize', 0),
                            'nindexes': stats.get('nindexes', 0),
                            'indexes': [
                                {
                                    'name': idx.get('name'),
                                    'key': idx.get('key'),
                                    'unique': idx.get('unique', False),
                                    'sparse': idx.get('sparse', False)
                                } for idx in indexes
                            ]
                        }
                        collections_stats.append(coll_stats)
                        
                    except Exception as e:
                        collections_stats.append({
                            'name': coll_name,
                            'error': f"Unable to get stats: {str(e)}"
                        })
                
                client.close()
                
                return {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'database_name': database_name,
                    'collection_name': collection_name or 'all',
                    'total_collections': len(collections_stats),
                    'collections': collections_stats
                }
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB collection stats for {instance.name}: {e}")
            raise Exception(f"Failed to get MongoDB collection stats: {str(e)}")

    def get_mongodb_performance_metrics(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get MongoDB performance metrics and server statistics"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Getting performance metrics for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                # Get comprehensive server status
                server_status = db.command("serverStatus")
                
                # Extract key performance metrics
                performance_metrics = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'opcounters': server_status.get('opcounters', {}),
                    'opcountersRepl': server_status.get('opcountersRepl', {}),
                    'connections': server_status.get('connections', {}),
                    'memory': server_status.get('mem', {}),
                    'globalLock': server_status.get('globalLock', {}),
                    'locks': server_status.get('locks', {}),
                    'network': server_status.get('network', {}),
                    'metrics': {
                        'cursor': server_status.get('metrics', {}).get('cursor', {}),
                        'document': server_status.get('metrics', {}).get('document', {}),
                        'operation': server_status.get('metrics', {}).get('operation', {}),
                        'queryExecutor': server_status.get('metrics', {}).get('queryExecutor', {}),
                        'repl': server_status.get('metrics', {}).get('repl', {})
                    },
                    'wiredTiger': server_status.get('wiredTiger', {}),
                    'extra_info': server_status.get('extra_info', {}),
                    'timestamp': server_status.get('localTime')
                }
                
                client.close()
                return performance_metrics
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB performance metrics for {instance.name}: {e}")
            raise Exception(f"Failed to get MongoDB performance metrics: {str(e)}")

    def get_mongodb_slow_queries(self, instance: ServiceInstance, database_name: Optional[str] = None, slow_threshold_ms: int = 100) -> Dict[str, Any]:
        """Get MongoDB slow queries analysis"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            admin_db = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing slow queries for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                
                # Set profiling level to capture slow operations
                if database_name:
                    databases = [database_name]
                else:
                    databases = client.list_database_names()
                
                slow_queries_data = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'slow_threshold_ms': slow_threshold_ms,
                    'databases_analyzed': [],
                    'total_slow_queries': 0
                }
                
                for db_name in databases:
                    if db_name in ['admin', 'local', 'config']:
                        continue
                        
                    try:
                        db = client[db_name]
                        
                        # Check current profiling status
                        profile_status = db.command("profile", -1)
                        
                        # Get profiler data if available
                        if 'system.profile' in db.list_collection_names():
                            profile_collection = db['system.profile']
                            
                            # Query for slow operations
                            slow_ops = list(profile_collection.find({
                                'millis': {'$gte': slow_threshold_ms}
                            }).sort('ts', -1).limit(50))
                            
                            db_analysis = {
                                'database': db_name,
                                'profiling_level': profile_status.get('was'),
                                'slow_operations_count': len(slow_ops),
                                'slow_operations': [
                                    {
                                        'timestamp': op.get('ts'),
                                        'operation': op.get('op'),
                                        'namespace': op.get('ns'),
                                        'duration_ms': op.get('millis'),
                                        'command': op.get('command', {}),
                                        'docsExamined': op.get('docsExamined'),
                                        'docsReturned': op.get('docsReturned'),
                                        'planSummary': op.get('planSummary')
                                    } for op in slow_ops
                                ]
                            }
                            
                            slow_queries_data['databases_analyzed'].append(db_analysis)
                            slow_queries_data['total_slow_queries'] += len(slow_ops)
                        
                    except Exception as e:
                        slow_queries_data['databases_analyzed'].append({
                            'database': db_name,
                            'error': f"Unable to analyze: {str(e)}"
                        })
                
                client.close()
                return slow_queries_data
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB slow queries for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB slow queries: {str(e)}")

    def get_mongodb_index_analysis(self, instance: ServiceInstance, database_name: str, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get MongoDB index analysis and optimization recommendations"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing indexes for MongoDB instance: {instance.name}, database: {database_name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database_name]
                
                if collection_name:
                    collection_names = [collection_name]
                else:
                    collection_names = db.list_collection_names()
                
                index_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'database_name': database_name,
                    'collection_name': collection_name or 'all',
                    'collections_analyzed': []
                }
                
                for coll_name in collection_names:
                    try:
                        collection = db[coll_name]
                        
                        # Get all indexes
                        indexes = list(collection.list_indexes())
                        
                        # Get index usage statistics if available
                        try:
                            index_stats = db.command("collStats", coll_name, indexDetails=True)
                        except:
                            index_stats = {}
                        
                        collection_analysis = {
                            'collection': coll_name,
                            'total_indexes': len(indexes),
                            'indexes': [
                                {
                                    'name': idx.get('name'),
                                    'key': idx.get('key'),
                                    'unique': idx.get('unique', False),
                                    'sparse': idx.get('sparse', False),
                                    'partialFilterExpression': idx.get('partialFilterExpression'),
                                    'expireAfterSeconds': idx.get('expireAfterSeconds'),
                                    'background': idx.get('background', False)
                                } for idx in indexes
                            ],
                            'recommendations': []
                        }
                        
                        # Add basic recommendations
                        if len(indexes) == 1:  # Only _id index
                            collection_analysis['recommendations'].append(
                                "Consider adding indexes for frequently queried fields"
                            )
                        elif len(indexes) > 10:
                            collection_analysis['recommendations'].append(
                                "High number of indexes detected - review if all are necessary"
                            )
                        
                        index_analysis['collections_analyzed'].append(collection_analysis)
                        
                    except Exception as e:
                        index_analysis['collections_analyzed'].append({
                            'collection': coll_name,
                            'error': f"Unable to analyze: {str(e)}"
                        })
                
                client.close()
                return index_analysis
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB indexes for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB indexes: {str(e)}")

    def get_mongodb_replica_set_status(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get MongoDB replica set status and configuration"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Getting replica set status for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                try:
                    # Get replica set status
                    rs_status = db.command("replSetGetStatus")
                    rs_config = db.command("replSetGetConfig")
                    
                    replica_set_data = {
                        'instance_name': instance.name,
                        'instance_id': instance.instanceId,
                        'replica_set_name': rs_status.get('set'),
                        'status': {
                            'ok': rs_status.get('ok'),
                            'date': rs_status.get('date'),
                            'myState': rs_status.get('myState'),
                            'term': rs_status.get('term'),
                            'heartbeatIntervalMillis': rs_status.get('heartbeatIntervalMillis')
                        },
                        'members': [
                            {
                                'name': member.get('name'),
                                'health': member.get('health'),
                                'state': member.get('state'),
                                'stateStr': member.get('stateStr'),
                                'uptime': member.get('uptime'),
                                'optimeDate': member.get('optimeDate'),
                                'lastHeartbeat': member.get('lastHeartbeat'),
                                'lastHeartbeatRecv': member.get('lastHeartbeatRecv'),
                                'pingMs': member.get('pingMs'),
                                'electionTime': member.get('electionTime'),
                                'electionDate': member.get('electionDate')
                            } for member in rs_status.get('members', [])
                        ],
                        'config': {
                            'version': rs_config.get('config', {}).get('version'),
                            'members': [
                                {
                                    'id': member.get('_id'),
                                    'host': member.get('host'),
                                    'priority': member.get('priority'),
                                    'votes': member.get('votes'),
                                    'arbiterOnly': member.get('arbiterOnly', False),
                                    'hidden': member.get('hidden', False)
                                } for member in rs_config.get('config', {}).get('members', [])
                            ]
                        }
                    }
                    
                except Exception as rs_error:
                    # Not a replica set or no access
                    replica_set_data = {
                        'instance_name': instance.name,
                        'instance_id': instance.instanceId,
                        'replica_set_status': 'standalone_or_no_access',
                        'error': str(rs_error)
                    }
                
                client.close()
                return replica_set_data
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB replica set status for {instance.name}: {e}")
            raise Exception(f"Failed to get MongoDB replica set status: {str(e)}")

    def get_mongodb_connection_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get MongoDB connection analysis and statistics"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing connections for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                # Get server status for connection info
                server_status = db.command("serverStatus")
                
                # Get current operations to see active connections
                try:
                    current_ops = db.command("currentOp", True)
                except:
                    current_ops = {'inprog': []}
                
                connections_data = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'connection_stats': server_status.get('connections', {}),
                    'network_stats': server_status.get('network', {}),
                    'active_operations': len(current_ops.get('inprog', [])),
                    'operations_by_type': {},
                    'operations_by_client': {},
                    'long_running_operations': []
                }
                
                # Analyze current operations
                for op in current_ops.get('inprog', []):
                    op_type = op.get('op', 'unknown')
                    client_addr = op.get('client', 'unknown')
                    duration = op.get('secs_running', 0)
                    
                    # Count by operation type
                    connections_data['operations_by_type'][op_type] = connections_data['operations_by_type'].get(op_type, 0) + 1
                    
                    # Count by client
                    connections_data['operations_by_client'][client_addr] = connections_data['operations_by_client'].get(client_addr, 0) + 1
                    
                    # Track long-running operations (>30 seconds)
                    if duration > 30:
                        connections_data['long_running_operations'].append({
                            'operation': op_type,
                            'duration_seconds': duration,
                            'client': client_addr,
                            'description': op.get('desc', ''),
                            'namespace': op.get('ns', '')
                        })
                
                client.close()
                return connections_data
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB connections for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB connections: {str(e)}")

    def get_mongodb_operations_analysis(self, instance: ServiceInstance, operation_threshold_ms: int = 1000) -> Dict[str, Any]:
        """Get MongoDB operations analysis and current operations"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing operations for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                # Get current operations
                try:
                    current_ops = db.command("currentOp", True)
                except:
                    current_ops = {'inprog': []}
                
                # Get server status for operation counters
                server_status = db.command("serverStatus")
                
                operations_data = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'operation_threshold_ms': operation_threshold_ms,
                    'total_active_operations': len(current_ops.get('inprog', [])),
                    'operation_counters': server_status.get('opcounters', {}),
                    'operation_counters_repl': server_status.get('opcountersRepl', {}),
                    'current_operations': [],
                    'long_running_operations': [],
                    'operations_by_type': {},
                    'operations_by_database': {}
                }
                
                # Analyze current operations
                for op in current_ops.get('inprog', []):
                    op_info = {
                        'opid': op.get('opid'),
                        'operation': op.get('op'),
                        'namespace': op.get('ns'),
                        'duration_seconds': op.get('secs_running', 0),
                        'client': op.get('client'),
                        'description': op.get('desc'),
                        'command': op.get('command', {}),
                        'waiting_for_lock': op.get('waitingForLock', False),
                        'lock_stats': op.get('lockStats', {})
                    }
                    
                    operations_data['current_operations'].append(op_info)
                    
                    # Count by type
                    op_type = op.get('op', 'unknown')
                    operations_data['operations_by_type'][op_type] = operations_data['operations_by_type'].get(op_type, 0) + 1
                    
                    # Count by database
                    namespace = op.get('ns', '')
                    if '.' in namespace:
                        db_name = namespace.split('.')[0]
                        operations_data['operations_by_database'][db_name] = operations_data['operations_by_database'].get(db_name, 0) + 1
                    
                    # Track long-running operations
                    duration_ms = op.get('secs_running', 0) * 1000
                    if duration_ms >= operation_threshold_ms:
                        operations_data['long_running_operations'].append(op_info)
                
                client.close()
                return operations_data
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB operations for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB operations: {str(e)}")

    def get_mongodb_security_audit(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Perform MongoDB security audit and best practices check"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Performing security audit for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                security_audit = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'authentication': {},
                    'authorization': {},
                    'encryption': {},
                    'security_recommendations': [],
                    'compliance_checks': {}
                }
                
                # Check authentication mechanism
                try:
                    build_info = db.command("buildInfo")
                    security_audit['authentication']['mongodb_version'] = build_info.get('version')
                    
                    # Check if authentication is enabled
                    try:
                        users = db.command("usersInfo")
                        security_audit['authentication']['auth_enabled'] = True
                        security_audit['authentication']['total_users'] = len(users.get('users', []))
                    except:
                        security_audit['authentication']['auth_enabled'] = False
                        security_audit['security_recommendations'].append(
                            "Authentication is not enabled - consider enabling authentication"
                        )
                    
                    # Check SSL/TLS
                    server_status = db.command("serverStatus")
                    security_audit['encryption']['ssl_mode'] = server_status.get('transportSecurity', {}).get('mode', 'disabled')
                    
                    if security_audit['encryption']['ssl_mode'] == 'disabled':
                        security_audit['security_recommendations'].append(
                            "SSL/TLS encryption is not enabled - consider enabling for data in transit"
                        )
                    
                    # Check for default database names
                    db_names = client.list_database_names()
                    if 'test' in db_names:
                        security_audit['security_recommendations'].append(
                            "Default 'test' database exists - consider removing if not needed"
                        )
                    
                    # Basic compliance checks
                    security_audit['compliance_checks'] = {
                        'authentication_enabled': security_audit['authentication']['auth_enabled'],
                        'encryption_in_transit': security_audit['encryption']['ssl_mode'] != 'disabled',
                        'no_default_databases': 'test' not in db_names,
                        'mongodb_version_supported': True  # Would need to check against EOL versions
                    }
                    
                except Exception as audit_error:
                    security_audit['error'] = f"Security audit incomplete: {str(audit_error)}"
                
                client.close()
                return security_audit
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to perform MongoDB security audit for {instance.name}: {e}")
            raise Exception(f"Failed to perform MongoDB security audit: {str(e)}")

    def get_mongodb_backup_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze MongoDB backup status and strategies"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            database = instance.config.get('database', 'admin')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing backup status for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                db = client[database]
                
                backup_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'backup_recommendations': [],
                    'point_in_time_recovery': {},
                    'storage_analysis': {}
                }
                
                # Check if oplog exists (needed for point-in-time recovery)
                try:
                    oplog_stats = db.command("collStats", "oplog.rs")
                    backup_analysis['point_in_time_recovery'] = {
                        'oplog_available': True,
                        'oplog_size_mb': oplog_stats.get('size', 0) / (1024 * 1024),
                        'oplog_max_size_mb': oplog_stats.get('maxSize', 0) / (1024 * 1024),
                        'oplog_usage_percent': (oplog_stats.get('size', 0) / max(oplog_stats.get('maxSize', 1), 1)) * 100
                    }
                    
                    if backup_analysis['point_in_time_recovery']['oplog_usage_percent'] > 80:
                        backup_analysis['backup_recommendations'].append(
                            "Oplog usage is high - consider increasing oplog size for better point-in-time recovery"
                        )
                        
                except:
                    backup_analysis['point_in_time_recovery'] = {
                        'oplog_available': False
                    }
                    backup_analysis['backup_recommendations'].append(
                        "Oplog not available - point-in-time recovery may not be possible"
                    )
                
                # Get storage information
                try:
                    db_stats = db.command("dbStats")
                    backup_analysis['storage_analysis'] = {
                        'data_size_mb': db_stats.get('dataSize', 0) / (1024 * 1024),
                        'storage_size_mb': db_stats.get('storageSize', 0) / (1024 * 1024),
                        'index_size_mb': db_stats.get('indexSize', 0) / (1024 * 1024),
                        'total_collections': db_stats.get('collections', 0)
                    }
                except:
                    pass
                
                # Add general backup recommendations
                backup_analysis['backup_recommendations'].extend([
                    "Implement regular automated backups",
                    "Test backup restoration procedures regularly",
                    "Store backups in geographically distributed locations",
                    "Monitor backup success and failure rates",
                    "Document backup and recovery procedures"
                ])
                
                client.close()
                return backup_analysis
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB backup status for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB backup status: {str(e)}")

    def get_mongodb_capacity_planning(self, instance: ServiceInstance, projection_days: int = 30) -> Dict[str, Any]:
        """Analyze MongoDB capacity and provide growth projections"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            connection_string = instance.config.get('connectionString')
            
            if not connection_string:
                raise Exception("MongoDB connection string not found in instance configuration")
            
            logger.info(f"🔍 Analyzing capacity planning for MongoDB instance: {instance.name}")
            
            try:
                from pymongo import MongoClient
                from datetime import datetime, timedelta
                
                client = MongoClient(connection_string, serverSelectionTimeoutMS=30000)
                
                capacity_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'projection_days': projection_days,
                    'current_usage': {},
                    'database_breakdown': [],
                    'growth_projections': {},
                    'capacity_recommendations': []
                }
                
                # Get current storage usage
                total_data_size = 0
                total_storage_size = 0
                total_index_size = 0
                
                db_names = client.list_database_names()
                
                for db_name in db_names:
                    if db_name in ['admin', 'local', 'config']:
                        continue
                    
                    try:
                        db = client[db_name]
                        db_stats = db.command("dbStats")
                        
                        db_info = {
                            'database': db_name,
                            'data_size_mb': db_stats.get('dataSize', 0) / (1024 * 1024),
                            'storage_size_mb': db_stats.get('storageSize', 0) / (1024 * 1024),
                            'index_size_mb': db_stats.get('indexSize', 0) / (1024 * 1024),
                            'collections': db_stats.get('collections', 0),
                            'objects': db_stats.get('objects', 0)
                        }
                        
                        capacity_analysis['database_breakdown'].append(db_info)
                        
                        total_data_size += db_info['data_size_mb']
                        total_storage_size += db_info['storage_size_mb']
                        total_index_size += db_info['index_size_mb']
                        
                    except Exception as e:
                        capacity_analysis['database_breakdown'].append({
                            'database': db_name,
                            'error': f"Unable to get stats: {str(e)}"
                        })
                
                capacity_analysis['current_usage'] = {
                    'total_data_size_mb': total_data_size,
                    'total_storage_size_mb': total_storage_size,
                    'total_index_size_mb': total_index_size,
                    'total_size_mb': total_data_size + total_index_size,
                    'storage_efficiency_percent': (total_data_size / max(total_storage_size, 1)) * 100
                }
                
                # Simple growth projection (would be more sophisticated with historical data)
                # Assume 10% monthly growth as baseline
                monthly_growth_rate = 0.10
                daily_growth_rate = monthly_growth_rate / 30
                
                projected_size = total_data_size * (1 + (daily_growth_rate * projection_days))
                
                capacity_analysis['growth_projections'] = {
                    'current_size_mb': total_data_size,
                    'projected_size_mb': projected_size,
                    'growth_mb': projected_size - total_data_size,
                    'growth_percent': ((projected_size - total_data_size) / max(total_data_size, 1)) * 100,
                    'projection_date': (datetime.now() + timedelta(days=projection_days)).isoformat()
                }
                
                # Add capacity recommendations
                if capacity_analysis['current_usage']['storage_efficiency_percent'] < 50:
                    capacity_analysis['capacity_recommendations'].append(
                        "Low storage efficiency detected - consider running compact operations"
                    )
                
                if projected_size > total_data_size * 2:
                    capacity_analysis['capacity_recommendations'].append(
                        f"High growth projected - plan for {projected_size:.1f}MB capacity in {projection_days} days"
                    )
                
                capacity_analysis['capacity_recommendations'].extend([
                    "Monitor storage usage trends regularly",
                    "Plan for at least 20% buffer above projected usage",
                    "Consider archiving old data if growth is unsustainable",
                    "Review index usage and optimize if necessary"
                ])
                
                client.close()
                return capacity_analysis
                
            except ImportError:
                raise Exception("pymongo library not available. Please install: pip install pymongo")
            
        except Exception as e:
            logger.error(f"Failed to analyze MongoDB capacity planning for {instance.name}: {e}")
            raise Exception(f"Failed to analyze MongoDB capacity planning: {str(e)}")

    # Redis client methods
    def get_redis_health(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Redis instance health and server information"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Connecting to Redis instance: {instance.name} at {host}:{port}")
            
            try:
                import redis
                
                # Create Redis client
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30,
                    socket_connect_timeout=30
                )
                
                # Test connection and get server info
                info = client.info()
                ping_result = client.ping()
                
                # Get key statistics
                dbsize = client.dbsize()
                
                health_data = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'connection_status': 'healthy' if ping_result else 'unhealthy',
                    'server_info': {
                        'redis_version': info.get('redis_version'),
                        'redis_mode': info.get('redis_mode', 'standalone'),
                        'arch_bits': info.get('arch_bits'),
                        'uptime_in_seconds': info.get('uptime_in_seconds'),
                        'uptime_in_days': info.get('uptime_in_days'),
                        'tcp_port': info.get('tcp_port'),
                        'process_id': info.get('process_id')
                    },
                    'memory_info': {
                        'used_memory': info.get('used_memory'),
                        'used_memory_human': info.get('used_memory_human'),
                        'used_memory_rss': info.get('used_memory_rss'),
                        'used_memory_peak': info.get('used_memory_peak'),
                        'used_memory_peak_human': info.get('used_memory_peak_human'),
                        'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio')
                    },
                    'stats': {
                        'total_connections_received': info.get('total_connections_received'),
                        'total_commands_processed': info.get('total_commands_processed'),
                        'connected_clients': info.get('connected_clients'),
                        'blocked_clients': info.get('blocked_clients'),
                        'expired_keys': info.get('expired_keys'),
                        'evicted_keys': info.get('evicted_keys'),
                        'keyspace_hits': info.get('keyspace_hits'),
                        'keyspace_misses': info.get('keyspace_misses')
                    },
                    'database_info': {
                        'total_keys': dbsize,
                        'databases': {}
                    }
                }
                
                # Get database-specific key counts
                for key, value in info.items():
                    if key.startswith('db'):
                        health_data['database_info']['databases'][key] = value
                
                client.close()
                return health_data
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            except redis.ConnectionError:
                raise Exception("Failed to connect to Redis server")
            except redis.AuthenticationError:
                raise Exception("Redis authentication failed - check password")
            except redis.TimeoutError:
                raise Exception("Redis connection timeout")
            
        except Exception as e:
            logger.error(f"Failed to get Redis health for {instance.name}: {e}")
            raise Exception(f"Failed to get Redis health: {str(e)}")

    def get_redis_performance_metrics(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Redis performance metrics and statistics"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Getting performance metrics for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get comprehensive server info
                info = client.info()
                
                # Calculate hit ratio
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                total_requests = hits + misses
                hit_ratio = (hits / total_requests * 100) if total_requests > 0 else 0
                
                # Calculate operations per second (approximation)
                uptime = info.get('uptime_in_seconds', 1)
                total_commands = info.get('total_commands_processed', 0)
                ops_per_second = total_commands / uptime if uptime > 0 else 0
                
                performance_metrics = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'performance_summary': {
                        'hit_ratio_percent': round(hit_ratio, 2),
                        'operations_per_second': round(ops_per_second, 2),
                        'memory_efficiency_percent': round((1 - info.get('mem_fragmentation_ratio', 1)) * 100, 2),
                        'connected_clients': info.get('connected_clients', 0)
                    },
                    'command_stats': {
                        'total_commands_processed': info.get('total_commands_processed', 0),
                        'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0)
                    },
                    'memory_metrics': {
                        'used_memory': info.get('used_memory', 0),
                        'used_memory_rss': info.get('used_memory_rss', 0),
                        'used_memory_peak': info.get('used_memory_peak', 0),
                        'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                        'maxmemory': info.get('maxmemory', 0),
                        'maxmemory_policy': info.get('maxmemory_policy', 'noeviction')
                    },
                    'connection_metrics': {
                        'connected_clients': info.get('connected_clients', 0),
                        'client_recent_max_input_buffer': info.get('client_recent_max_input_buffer', 0),
                        'client_recent_max_output_buffer': info.get('client_recent_max_output_buffer', 0),
                        'blocked_clients': info.get('blocked_clients', 0),
                        'total_connections_received': info.get('total_connections_received', 0),
                        'rejected_connections': info.get('rejected_connections', 0)
                    },
                    'persistence_metrics': {
                        'rdb_changes_since_last_save': info.get('rdb_changes_since_last_save', 0),
                        'rdb_last_save_time': info.get('rdb_last_save_time', 0),
                        'aof_enabled': info.get('aof_enabled', 0),
                        'aof_rewrite_in_progress': info.get('aof_rewrite_in_progress', 0),
                        'aof_pending_rewrite': info.get('aof_pending_rewrite', 0)
                    },
                    'network_metrics': {
                        'total_net_input_bytes': info.get('total_net_input_bytes', 0),
                        'total_net_output_bytes': info.get('total_net_output_bytes', 0),
                        'instantaneous_input_kbps': info.get('instantaneous_input_kbps', 0),
                        'instantaneous_output_kbps': info.get('instantaneous_output_kbps', 0)
                    }
                }
                
                client.close()
                return performance_metrics
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to get Redis performance metrics for {instance.name}: {e}")
            raise Exception(f"Failed to get Redis performance metrics: {str(e)}")

    def get_redis_memory_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze Redis memory usage and fragmentation"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing memory usage for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                info = client.info('memory')
                
                # Calculate memory utilization
                used_memory = info.get('used_memory', 0)
                maxmemory = info.get('maxmemory', 0)
                memory_utilization = (used_memory / maxmemory * 100) if maxmemory > 0 else 0
                
                # Get memory breakdown by data structure if available
                memory_usage = {}
                try:
                    memory_usage = client.memory_usage('*') if hasattr(client, 'memory_usage') else {}
                except:
                    pass
                
                memory_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'memory_overview': {
                        'used_memory_bytes': used_memory,
                        'used_memory_human': info.get('used_memory_human', '0B'),
                        'used_memory_rss_bytes': info.get('used_memory_rss', 0),
                        'used_memory_peak_bytes': info.get('used_memory_peak', 0),
                        'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                        'maxmemory_bytes': maxmemory,
                        'memory_utilization_percent': round(memory_utilization, 2)
                    },
                    'fragmentation_analysis': {
                        'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                        'mem_fragmentation_bytes': info.get('mem_fragmentation_bytes', 0),
                        'allocator_frag_ratio': info.get('allocator_frag_ratio', 0),
                        'allocator_frag_bytes': info.get('allocator_frag_bytes', 0),
                        'allocator_rss_ratio': info.get('allocator_rss_ratio', 0),
                        'allocator_rss_bytes': info.get('allocator_rss_bytes', 0)
                    },
                    'memory_policies': {
                        'maxmemory_policy': info.get('maxmemory_policy', 'noeviction'),
                        'evicted_keys': client.info().get('evicted_keys', 0),
                        'expired_keys': client.info().get('expired_keys', 0)
                    },
                    'optimization_recommendations': []
                }
                
                # Add optimization recommendations
                fragmentation_ratio = info.get('mem_fragmentation_ratio', 0)
                if fragmentation_ratio > 1.5:
                    memory_analysis['optimization_recommendations'].append(
                        f"High memory fragmentation detected ({fragmentation_ratio:.2f}). Consider running MEMORY PURGE or restarting Redis during low traffic."
                    )
                
                if memory_utilization > 80:
                    memory_analysis['optimization_recommendations'].append(
                        f"High memory utilization ({memory_utilization:.1f}%). Consider increasing maxmemory or implementing key expiration policies."
                    )
                
                if info.get('maxmemory_policy') == 'noeviction' and maxmemory > 0:
                    memory_analysis['optimization_recommendations'].append(
                        "No eviction policy set. Consider setting an appropriate eviction policy (e.g., allkeys-lru) to prevent out-of-memory errors."
                    )
                
                client.close()
                return memory_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis memory for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis memory: {str(e)}")

    def get_redis_key_analysis(self, instance: ServiceInstance, database_id: int = 0, pattern: Optional[str] = None, sample_size: int = 1000) -> Dict[str, Any]:
        """Analyze Redis keys and patterns"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing keys for Redis instance: {instance.name}, DB: {database_id}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    db=database_id,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get basic key statistics
                dbsize = client.dbsize()
                
                # Sample keys for analysis
                if pattern:
                    sample_keys = list(client.scan_iter(match=pattern, count=min(sample_size, 100)))
                else:
                    sample_keys = list(client.scan_iter(count=min(sample_size, 100)))
                
                # Limit sample size to prevent performance issues
                sample_keys = sample_keys[:sample_size]
                
                # Analyze key patterns and types
                key_types = {}
                key_patterns = {}
                key_sizes = []
                large_keys = []
                ttl_analysis = {'with_ttl': 0, 'without_ttl': 0}
                
                for key in sample_keys:
                    try:
                        # Get key type
                        key_type = client.type(key)
                        key_types[key_type] = key_types.get(key_type, 0) + 1
                        
                        # Analyze key patterns
                        if ':' in key:
                            pattern_prefix = key.split(':')[0]
                            key_patterns[pattern_prefix] = key_patterns.get(pattern_prefix, 0) + 1
                        
                        # Get key size (memory usage)
                        try:
                            if hasattr(client, 'memory_usage'):
                                key_size = client.memory_usage(key)
                                key_sizes.append(key_size)
                                
                                # Track large keys (>1MB)
                                if key_size > 1024 * 1024:
                                    large_keys.append({
                                        'key': key,
                                        'type': key_type,
                                        'size_bytes': key_size,
                                        'size_human': f"{key_size / (1024*1024):.2f}MB"
                                    })
                        except:
                            pass
                        
                        # Check TTL
                        ttl = client.ttl(key)
                        if ttl > 0:
                            ttl_analysis['with_ttl'] += 1
                        else:
                            ttl_analysis['without_ttl'] += 1
                            
                    except Exception as key_error:
                        logger.warning(f"Error analyzing key {key}: {key_error}")
                        continue
                
                # Calculate statistics
                avg_key_size = sum(key_sizes) / len(key_sizes) if key_sizes else 0
                total_sampled_memory = sum(key_sizes) if key_sizes else 0
                
                key_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'database_id': database_id,
                    'pattern': pattern or 'all',
                    'key_statistics': {
                        'total_keys_in_db': dbsize,
                        'sampled_keys': len(sample_keys),
                        'sample_size_requested': sample_size
                    },
                    'key_type_distribution': key_types,
                    'key_pattern_analysis': dict(sorted(key_patterns.items(), key=lambda x: x[1], reverse=True)[:20]),
                    'memory_analysis': {
                        'average_key_size_bytes': round(avg_key_size, 2),
                        'total_sampled_memory_bytes': total_sampled_memory,
                        'large_keys_count': len(large_keys),
                        'large_keys': large_keys[:10]  # Top 10 largest keys
                    },
                    'ttl_analysis': ttl_analysis,
                    'recommendations': []
                }
                
                # Add recommendations
                if ttl_analysis['without_ttl'] > ttl_analysis['with_ttl']:
                    key_analysis['recommendations'].append(
                        "Many keys without TTL detected. Consider setting appropriate expiration times to manage memory usage."
                    )
                
                if len(large_keys) > 0:
                    key_analysis['recommendations'].append(
                        f"Found {len(large_keys)} large keys (>1MB). Consider data structure optimization or data partitioning."
                    )
                
                most_common_type = max(key_types.items(), key=lambda x: x[1])[0] if key_types else None
                if most_common_type == 'string' and key_types.get('string', 0) > len(sample_keys) * 0.8:
                    key_analysis['recommendations'].append(
                        "High percentage of string keys. Consider using more efficient data structures like hashes for structured data."
                    )
                
                client.close()
                return key_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis keys for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis keys: {str(e)}")

    def get_redis_slow_log_analysis(self, instance: ServiceInstance, max_entries: int = 100) -> Dict[str, Any]:
        """Analyze Redis slow log for performance issues"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing slow log for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get slow log entries
                slow_log_entries = client.slowlog_get(max_entries)
                
                # Get slow log configuration
                slow_log_len = client.slowlog_len()
                config_info = client.config_get('slowlog-*')
                
                # Analyze slow log entries
                command_frequency = {}
                total_execution_time = 0
                slowest_commands = []
                
                for entry in slow_log_entries:
                    # Handle both tuple/list format (older Redis) and dict format (newer Redis)
                    if isinstance(entry, dict):
                        timestamp = entry.get('start_time', 0)
                        duration_microseconds = entry.get('duration', 0)
                        command_args = entry.get('command', [])
                        client_addr = entry.get('client_name', 'unknown')
                    else:
                        timestamp, duration_microseconds, command_args, client_addr = entry[:4]
                    
                    command = command_args[0] if command_args else 'UNKNOWN'
                    duration_ms = duration_microseconds / 1000
                    
                    # Count command frequency
                    command_frequency[command] = command_frequency.get(command, 0) + 1
                    total_execution_time += duration_ms
                    
                    # Track slowest commands
                    slowest_commands.append({
                        'timestamp': timestamp,
                        'duration_ms': round(duration_ms, 2),
                        'command': command,
                        'full_command': ' '.join(str(arg) for arg in command_args),
                        'client': client_addr
                    })
                
                # Sort by duration
                slowest_commands.sort(key=lambda x: x['duration_ms'], reverse=True)
                
                slow_log_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'slow_log_config': {
                        'slowlog_log_slower_than': config_info.get('slowlog-log-slower-than', 'unknown'),
                        'slowlog_max_len': config_info.get('slowlog-max-len', 'unknown'),
                        'current_entries': slow_log_len,
                        'analyzed_entries': len(slow_log_entries)
                    },
                    'performance_summary': {
                        'total_slow_commands': len(slow_log_entries),
                        'total_execution_time_ms': round(total_execution_time, 2),
                        'average_execution_time_ms': round(total_execution_time / len(slow_log_entries), 2) if slow_log_entries else 0,
                        'slowest_command_ms': slowest_commands[0]['duration_ms'] if slowest_commands else 0
                    },
                    'command_analysis': {
                        'command_frequency': dict(sorted(command_frequency.items(), key=lambda x: x[1], reverse=True)),
                        'slowest_commands': slowest_commands[:20]  # Top 20 slowest
                    },
                    'recommendations': []
                }
                
                # Add recommendations
                if len(slow_log_entries) > 50:
                    slow_log_analysis['recommendations'].append(
                        f"High number of slow commands detected ({len(slow_log_entries)}). Investigate query optimization opportunities."
                    )
                
                # Analyze most frequent slow commands
                if command_frequency:
                    most_frequent = max(command_frequency.items(), key=lambda x: x[1])
                    if most_frequent[1] > len(slow_log_entries) * 0.3:
                        slow_log_analysis['recommendations'].append(
                            f"Command '{most_frequent[0]}' appears frequently in slow log ({most_frequent[1]} times). Consider optimization."
                        )
                
                # Check for blocking commands
                blocking_commands = ['KEYS', 'FLUSHALL', 'FLUSHDB', 'SORT']
                found_blocking = [cmd for cmd in command_frequency.keys() if cmd in blocking_commands]
                if found_blocking:
                    slow_log_analysis['recommendations'].append(
                        f"Blocking commands detected: {', '.join(found_blocking)}. Consider alternatives or run during maintenance windows."
                    )
                
                client.close()
                return slow_log_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis slow log for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis slow log: {str(e)}")

    def get_redis_connection_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze Redis connections and client statistics"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing connections for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get connection info from server stats
                info = client.info()
                
                # Get client list
                try:
                    client_list = client.client_list()
                except:
                    client_list = []
                
                # Analyze client connections
                client_by_type = {}
                client_by_addr = {}
                idle_clients = 0
                long_running_clients = 0
                
                for client_info in client_list:
                    client_type = client_info.get('name', 'unknown')
                    client_addr = client_info.get('addr', 'unknown')
                    idle_time = client_info.get('idle', 0)
                    
                    client_by_type[client_type] = client_by_type.get(client_type, 0) + 1
                    client_by_addr[client_addr] = client_by_addr.get(client_addr, 0) + 1
                    
                    if idle_time > 300:  # 5 minutes
                        idle_clients += 1
                    if idle_time > 3600:  # 1 hour
                        long_running_clients += 1
                
                connection_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'connection_overview': {
                        'connected_clients': info.get('connected_clients', 0),
                        'client_recent_max_input_buffer': info.get('client_recent_max_input_buffer', 0),
                        'client_recent_max_output_buffer': info.get('client_recent_max_output_buffer', 0),
                        'blocked_clients': info.get('blocked_clients', 0),
                        'total_connections_received': info.get('total_connections_received', 0),
                        'rejected_connections': info.get('rejected_connections', 0)
                    },
                    'client_analysis': {
                        'total_active_clients': len(client_list),
                        'clients_by_type': client_by_type,
                        'unique_client_addresses': len(client_by_addr),
                        'idle_clients_5min_plus': idle_clients,
                        'long_running_clients_1hr_plus': long_running_clients
                    },
                    'connection_patterns': {
                        'top_client_addresses': dict(sorted(client_by_addr.items(), key=lambda x: x[1], reverse=True)[:10])
                    },
                    'recommendations': []
                }
                
                # Add recommendations
                if info.get('rejected_connections', 0) > 0:
                    connection_analysis['recommendations'].append(
                        f"Rejected connections detected ({info.get('rejected_connections')}). Consider increasing maxclients or optimizing connection usage."
                    )
                
                if idle_clients > len(client_list) * 0.5:
                    connection_analysis['recommendations'].append(
                        f"High number of idle clients ({idle_clients}/{len(client_list)}). Consider implementing connection pooling or reducing connection timeouts."
                    )
                
                if info.get('connected_clients', 0) > 1000:
                    connection_analysis['recommendations'].append(
                        "High number of connected clients. Monitor for connection leaks and consider connection limits."
                    )
                
                client.close()
                return connection_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis connections for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis connections: {str(e)}")

    def get_redis_replication_status(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Get Redis replication status and master-slave health"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Checking replication status for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get replication info
                replication_info = client.info('replication')
                
                replication_status = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'replication_role': replication_info.get('role', 'unknown'),
                    'master_info': {},
                    'slave_info': {},
                    'replication_health': 'healthy'
                }
                
                if replication_info.get('role') == 'master':
                    # Master node analysis
                    connected_slaves = replication_info.get('connected_slaves', 0)
                    slaves = []
                    
                    for i in range(connected_slaves):
                        slave_key = f'slave{i}'
                        if slave_key in replication_info:
                            slave_data = replication_info[slave_key]
                            # Parse slave info (format: ip=X,port=Y,state=online,offset=Z,lag=N)
                            slave_info = {}
                            for item in slave_data.split(','):
                                if '=' in item:
                                    key, value = item.split('=', 1)
                                    slave_info[key] = value
                            slaves.append(slave_info)
                    
                    replication_status['master_info'] = {
                        'connected_slaves': connected_slaves,
                        'slaves': slaves,
                        'master_replid': replication_info.get('master_replid'),
                        'master_replid2': replication_info.get('master_replid2'),
                        'master_repl_offset': replication_info.get('master_repl_offset'),
                        'second_repl_offset': replication_info.get('second_repl_offset')
                    }
                    
                    # Check for replication lag
                    max_lag = 0
                    for slave in slaves:
                        lag = int(slave.get('lag', 0))
                        if lag > max_lag:
                            max_lag = lag
                    
                    if max_lag > 10:  # 10 seconds lag
                        replication_status['replication_health'] = 'degraded'
                    
                elif replication_info.get('role') == 'slave':
                    # Slave node analysis
                    replication_status['slave_info'] = {
                        'master_host': replication_info.get('master_host'),
                        'master_port': replication_info.get('master_port'),
                        'master_link_status': replication_info.get('master_link_status'),
                        'master_last_io_seconds_ago': replication_info.get('master_last_io_seconds_ago'),
                        'master_sync_in_progress': replication_info.get('master_sync_in_progress'),
                        'slave_repl_offset': replication_info.get('slave_repl_offset'),
                        'slave_priority': replication_info.get('slave_priority'),
                        'slave_read_only': replication_info.get('slave_read_only')
                    }
                    
                    # Check slave health
                    if replication_info.get('master_link_status') != 'up':
                        replication_status['replication_health'] = 'unhealthy'
                    elif replication_info.get('master_last_io_seconds_ago', 0) > 30:
                        replication_status['replication_health'] = 'degraded'
                
                else:
                    # Standalone instance
                    replication_status['standalone_info'] = {
                        'message': 'This is a standalone Redis instance (not part of replication)'
                    }
                
                client.close()
                return replication_status
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to check Redis replication status for {instance.name}: {e}")
            raise Exception(f"Failed to check Redis replication status: {str(e)}")

    def get_redis_persistence_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze Redis persistence configuration and backup status"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing persistence for Redis instance: {instance.name}")
            
            try:
                import redis
                import time
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get persistence-related info
                persistence_info = client.info('persistence')
                config_info = client.config_get('*save*')
                aof_config = client.config_get('*aof*')
                
                # Calculate time since last save
                last_save_time = persistence_info.get('rdb_last_save_time', 0)
                current_time = int(time.time())
                time_since_last_save = current_time - last_save_time
                
                persistence_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'rdb_configuration': {
                        'save_points': config_info.get('save', 'disabled'),
                        'rdb_changes_since_last_save': persistence_info.get('rdb_changes_since_last_save', 0),
                        'rdb_bgsave_in_progress': persistence_info.get('rdb_bgsave_in_progress', 0),
                        'rdb_last_save_time': last_save_time,
                        'time_since_last_save_seconds': time_since_last_save,
                        'rdb_last_bgsave_status': persistence_info.get('rdb_last_bgsave_status', 'unknown'),
                        'rdb_last_bgsave_time_sec': persistence_info.get('rdb_last_bgsave_time_sec', 0)
                    },
                    'aof_configuration': {
                        'aof_enabled': aof_config.get('appendonly', 'no') == 'yes',
                        'aof_rewrite_in_progress': persistence_info.get('aof_rewrite_in_progress', 0),
                        'aof_rewrite_scheduled': persistence_info.get('aof_rewrite_scheduled', 0),
                        'aof_last_rewrite_time_sec': persistence_info.get('aof_last_rewrite_time_sec', 0),
                        'aof_current_rewrite_time_sec': persistence_info.get('aof_current_rewrite_time_sec', 0),
                        'aof_last_bgrewrite_status': persistence_info.get('aof_last_bgrewrite_status', 'unknown'),
                        'aof_last_write_status': persistence_info.get('aof_last_write_status', 'unknown')
                    },
                    'data_safety_analysis': {
                        'unsaved_changes': persistence_info.get('rdb_changes_since_last_save', 0),
                        'persistence_enabled': config_info.get('save', 'disabled') != 'disabled' or aof_config.get('appendonly', 'no') == 'yes'
                    },
                    'recommendations': []
                }
                
                # Add recommendations
                if config_info.get('save', 'disabled') == 'disabled' and aof_config.get('appendonly', 'no') == 'no':
                    persistence_analysis['recommendations'].append(
                        "No persistence configured! Data will be lost on restart. Enable RDB snapshots or AOF logging."
                    )
                
                if persistence_info.get('rdb_changes_since_last_save', 0) > 10000:
                    persistence_analysis['recommendations'].append(
                        f"High number of unsaved changes ({persistence_info.get('rdb_changes_since_last_save')}). Consider more frequent saves."
                    )
                
                if time_since_last_save > 3600 and persistence_info.get('rdb_changes_since_last_save', 0) > 0:
                    persistence_analysis['recommendations'].append(
                        f"Last save was {time_since_last_save // 60} minutes ago with unsaved changes. Check save configuration."
                    )
                
                if persistence_info.get('rdb_last_bgsave_status') == 'err':
                    persistence_analysis['recommendations'].append(
                        "Last background save failed. Check disk space and permissions."
                    )
                
                if aof_config.get('appendonly', 'no') == 'yes' and persistence_info.get('aof_last_write_status') == 'err':
                    persistence_analysis['recommendations'].append(
                        "AOF write errors detected. Check disk space and I/O performance."
                    )
                
                client.close()
                return persistence_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis persistence for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis persistence: {str(e)}")

    def get_redis_cluster_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze Redis Cluster status and node health"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing cluster status for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Check if cluster mode is enabled
                cluster_info = None
                cluster_nodes = None
                cluster_enabled = False
                
                try:
                    cluster_info = client.cluster_info()
                    cluster_nodes = client.cluster_nodes()
                    cluster_enabled = True
                except:
                    # Not a cluster or cluster commands not available
                    pass
                
                if cluster_enabled:
                    # Parse cluster nodes information
                    nodes = []
                    for node_line in cluster_nodes.split('\n'):
                        if node_line.strip():
                            parts = node_line.split()
                            if len(parts) >= 8:
                                node_info = {
                                    'id': parts[0],
                                    'address': parts[1],
                                    'flags': parts[2].split(','),
                                    'master_id': parts[3] if parts[3] != '-' else None,
                                    'ping_sent': parts[4],
                                    'pong_recv': parts[5],
                                    'config_epoch': parts[6],
                                    'link_state': parts[7],
                                    'slots': parts[8:] if len(parts) > 8 else []
                                }
                                nodes.append(node_info)
                    
                    # Analyze cluster health
                    cluster_state = cluster_info.get('cluster_state', 'unknown')
                    cluster_slots_assigned = cluster_info.get('cluster_slots_assigned', 0)
                    cluster_slots_ok = cluster_info.get('cluster_slots_ok', 0)
                    cluster_slots_pfail = cluster_info.get('cluster_slots_pfail', 0)
                    cluster_slots_fail = cluster_info.get('cluster_slots_fail', 0)
                    
                    # Count node types
                    masters = [n for n in nodes if 'master' in n.get('flags', [])]
                    slaves = [n for n in nodes if 'slave' in n.get('flags', [])]
                    
                    cluster_analysis = {
                        'instance_name': instance.name,
                        'instance_id': instance.instanceId,
                        'cluster_enabled': True,
                        'cluster_status': {
                            'state': cluster_state,
                            'slots_assigned': cluster_slots_assigned,
                            'slots_ok': cluster_slots_ok,
                            'slots_pfail': cluster_slots_pfail,
                            'slots_fail': cluster_slots_fail,
                            'total_nodes': len(nodes),
                            'master_nodes': len(masters),
                            'slave_nodes': len(slaves)
                        },
                        'node_details': nodes,
                        'health_summary': {
                            'healthy': cluster_state == 'ok' and cluster_slots_fail == 0,
                            'issues': []
                        },
                        'recommendations': []
                    }
                    
                    # Health checks
                    if cluster_state != 'ok':
                        cluster_analysis['health_summary']['healthy'] = False
                        cluster_analysis['health_summary']['issues'].append(f"Cluster state is {cluster_state}")
                    
                    if cluster_slots_fail > 0:
                        cluster_analysis['health_summary']['healthy'] = False
                        cluster_analysis['health_summary']['issues'].append(f"{cluster_slots_fail} slots in failed state")
                    
                    if cluster_slots_pfail > 0:
                        cluster_analysis['health_summary']['issues'].append(f"{cluster_slots_pfail} slots in probable failure state")
                    
                    # Check for nodes with link state issues
                    disconnected_nodes = [n for n in nodes if n.get('link_state') != 'connected']
                    if disconnected_nodes:
                        cluster_analysis['health_summary']['healthy'] = False
                        cluster_analysis['health_summary']['issues'].append(f"{len(disconnected_nodes)} nodes disconnected")
                    
                    # Recommendations
                    if not cluster_analysis['health_summary']['healthy']:
                        cluster_analysis['recommendations'].append("Cluster health issues detected. Investigate node connectivity and slot assignments.")
                    
                    if len(masters) < 3:
                        cluster_analysis['recommendations'].append("Less than 3 master nodes. Consider adding more masters for better fault tolerance.")
                    
                    if len(slaves) == 0:
                        cluster_analysis['recommendations'].append("No slave nodes detected. Add slave nodes for high availability.")
                
                else:
                    # Not a cluster
                    cluster_analysis = {
                        'instance_name': instance.name,
                        'instance_id': instance.instanceId,
                        'cluster_enabled': False,
                        'message': 'This Redis instance is not configured for cluster mode',
                        'recommendations': ['Consider Redis Cluster for horizontal scaling and high availability']
                    }
                
                client.close()
                return cluster_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis cluster for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis cluster: {str(e)}")

    def get_redis_security_audit(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Perform Redis security audit and configuration analysis"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Performing security audit for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get security-related configuration
                auth_config = client.config_get('*auth*')
                acl_config = client.config_get('*acl*')
                security_config = client.config_get('*protected*')
                bind_config = client.config_get('bind')
                
                # Check Redis version
                server_info = client.info('server')
                redis_version = server_info.get('redis_version', 'unknown')
                
                # Check for dangerous commands
                dangerous_commands = ['FLUSHALL', 'FLUSHDB', 'KEYS', 'DEBUG', 'CONFIG', 'SHUTDOWN', 'EVAL']
                command_info = {}
                
                try:
                    # Try to get command info (available in newer Redis versions)
                    for cmd in dangerous_commands:
                        try:
                            client.command_info(cmd)
                            command_info[cmd] = 'available'
                        except:
                            command_info[cmd] = 'unknown'
                except:
                    # Fallback for older Redis versions
                    for cmd in dangerous_commands:
                        command_info[cmd] = 'unknown'
                
                security_audit = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'redis_version': redis_version,
                    'authentication': {
                        'password_protected': bool(password),
                        'requirepass_set': bool(auth_config.get('requirepass')),
                        'auth_enabled': bool(password or auth_config.get('requirepass'))
                    },
                    'access_control': {
                        'protected_mode': security_config.get('protected-mode', 'unknown'),
                        'bind_addresses': bind_config.get('bind', 'unknown'),
                        'acl_enabled': 'aclfile' in acl_config or len([k for k in acl_config.keys() if 'acl' in k]) > 0
                    },
                    'dangerous_commands': command_info,
                    'security_recommendations': [],
                    'compliance_checks': {}
                }
                
                # Security recommendations
                if not security_audit['authentication']['auth_enabled']:
                    security_audit['security_recommendations'].append(
                        "No authentication configured. Set requirepass or use ACL for security."
                    )
                
                if security_config.get('protected-mode', 'yes') == 'no':
                    security_audit['security_recommendations'].append(
                        "Protected mode is disabled. Enable protected mode for better security."
                    )
                
                if bind_config.get('bind', '') in ['0.0.0.0', ''] or '0.0.0.0' in bind_config.get('bind', ''):
                    security_audit['security_recommendations'].append(
                        "Redis is bound to all interfaces (0.0.0.0). Consider binding to specific interfaces only."
                    )
                
                # Check for default port
                if port == 6379:
                    security_audit['security_recommendations'].append(
                        "Using default Redis port (6379). Consider using a non-standard port for security."
                    )
                
                # Version-specific recommendations
                try:
                    version_parts = redis_version.split('.')
                    major_version = int(version_parts[0])
                    minor_version = int(version_parts[1])
                    
                    if major_version < 6:
                        security_audit['security_recommendations'].append(
                            f"Redis version {redis_version} is outdated. Consider upgrading for security improvements and ACL support."
                        )
                    elif major_version == 6 and not security_audit['access_control']['acl_enabled']:
                        security_audit['security_recommendations'].append(
                            "Redis 6+ supports ACLs for fine-grained access control. Consider implementing ACL instead of simple passwords."
                        )
                except:
                    pass
                
                # Compliance checks
                security_audit['compliance_checks'] = {
                    'authentication_enabled': security_audit['authentication']['auth_enabled'],
                    'protected_mode_enabled': security_config.get('protected-mode', 'yes') == 'yes',
                    'not_bound_to_all_interfaces': '0.0.0.0' not in bind_config.get('bind', ''),
                    'recent_redis_version': redis_version >= '6.0.0',
                    'acl_configured': security_audit['access_control']['acl_enabled']
                }
                
                client.close()
                return security_audit
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to perform Redis security audit for {instance.name}: {e}")
            raise Exception(f"Failed to perform Redis security audit: {str(e)}")

    def get_redis_capacity_planning(self, instance: ServiceInstance, projection_days: int = 30) -> Dict[str, Any]:
        """Analyze Redis capacity and provide growth projections"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing capacity planning for Redis instance: {instance.name}")
            
            try:
                import redis
                from datetime import datetime, timedelta
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get current memory and key statistics
                info = client.info()
                
                current_memory = info.get('used_memory', 0)
                max_memory = info.get('maxmemory', 0)
                total_keys = client.dbsize()
                
                # Get key count for all databases
                db_key_counts = {}
                for key, value in info.items():
                    if key.startswith('db'):
                        # Parse db0:keys=X,expires=Y,avg_ttl=Z format
                        db_stats = {}
                        for item in value.split(','):
                            if '=' in item:
                                stat_key, stat_value = item.split('=', 1)
                                db_stats[stat_key] = int(stat_value)
                        db_key_counts[key] = db_stats.get('keys', 0)
                
                # Simple growth projection based on current usage
                # In production, this would use historical data
                daily_growth_rate = 0.02  # 2% daily growth assumption
                projected_memory = current_memory * (1 + (daily_growth_rate * projection_days))
                projected_keys = total_keys * (1 + (daily_growth_rate * projection_days))
                
                capacity_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'projection_days': projection_days,
                    'current_usage': {
                        'memory_bytes': current_memory,
                        'memory_human': info.get('used_memory_human', '0B'),
                        'max_memory_bytes': max_memory,
                        'memory_utilization_percent': (current_memory / max_memory * 100) if max_memory > 0 else 0,
                        'total_keys': total_keys,
                        'databases': db_key_counts
                    },
                    'growth_projections': {
                        'projected_memory_bytes': int(projected_memory),
                        'projected_memory_human': f"{projected_memory / (1024**2):.2f}MB",
                        'projected_keys': int(projected_keys),
                        'memory_growth_bytes': int(projected_memory - current_memory),
                        'key_growth_count': int(projected_keys - total_keys),
                        'projection_date': (datetime.now() + timedelta(days=projection_days)).isoformat()
                    },
                    'capacity_recommendations': [],
                    'performance_projections': {
                        'fragmentation_risk': 'low',
                        'eviction_risk': 'low'
                    }
                }
                
                # Calculate capacity recommendations
                current_utilization = (current_memory / max_memory * 100) if max_memory > 0 else 0
                projected_utilization = (projected_memory / max_memory * 100) if max_memory > 0 else 0
                
                if max_memory == 0:
                    capacity_analysis['capacity_recommendations'].append(
                        "No memory limit set (maxmemory=0). Consider setting a memory limit to prevent OOM issues."
                    )
                elif projected_utilization > 80:
                    capacity_analysis['capacity_recommendations'].append(
                        f"Projected memory usage will reach {projected_utilization:.1f}% in {projection_days} days. Plan for memory increase."
                    )
                    capacity_analysis['performance_projections']['eviction_risk'] = 'high'
                
                # Fragmentation analysis
                fragmentation_ratio = info.get('mem_fragmentation_ratio', 1.0)
                if fragmentation_ratio > 1.5:
                    capacity_analysis['capacity_recommendations'].append(
                        f"High memory fragmentation ({fragmentation_ratio:.2f}). Consider memory defragmentation strategies."
                    )
                    capacity_analysis['performance_projections']['fragmentation_risk'] = 'high'
                
                # Key growth analysis
                if projected_keys > total_keys * 2:
                    capacity_analysis['capacity_recommendations'].append(
                        f"High key growth projected ({projected_keys:,} keys). Consider implementing key expiration policies."
                    )
                
                # Performance recommendations
                ops_per_sec = info.get('instantaneous_ops_per_sec', 0)
                if ops_per_sec > 10000:
                    capacity_analysis['capacity_recommendations'].append(
                        f"High operation rate ({ops_per_sec} ops/sec). Monitor for performance bottlenecks as data grows."
                    )
                
                # General recommendations
                capacity_analysis['capacity_recommendations'].extend([
                    f"Monitor memory usage trends regularly",
                    f"Plan for at least 20% buffer above projected usage",
                    f"Implement key expiration policies for non-persistent data",
                    f"Consider Redis Cluster for horizontal scaling if needed"
                ])
                
                client.close()
                return capacity_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis capacity planning for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis capacity planning: {str(e)}")

    def get_redis_configuration_analysis(self, instance: ServiceInstance) -> Dict[str, Any]:
        """Analyze Redis configuration and optimization opportunities"""
        try:
            if not instance.config:
                raise Exception("Instance configuration not available")
            
            host = instance.config.get('host')
            password = instance.config.get('password')
            port = instance.config.get('port', 6379)
            
            if not host:
                raise Exception("Redis host not found in instance configuration")
            
            logger.info(f"🔍 Analyzing configuration for Redis instance: {instance.name}")
            
            try:
                import redis
                
                client = redis.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_timeout=30
                )
                
                # Get all configuration parameters
                all_config = client.config_get('*')
                
                # Categorize configuration
                memory_config = {k: v for k, v in all_config.items() if 'memory' in k or 'maxmemory' in k}
                persistence_config = {k: v for k, v in all_config.items() if any(x in k for x in ['save', 'aof', 'rdb'])}
                network_config = {k: v for k, v in all_config.items() if any(x in k for x in ['timeout', 'tcp', 'bind', 'port'])}
                security_config = {k: v for k, v in all_config.items() if any(x in k for x in ['auth', 'protected', 'acl'])}
                performance_config = {k: v for k, v in all_config.items() if any(x in k for x in ['slow', 'client', 'hz'])}
                
                # Get current server info for context
                server_info = client.info()
                
                config_analysis = {
                    'instance_name': instance.name,
                    'instance_id': instance.instanceId,
                    'configuration_categories': {
                        'memory_management': memory_config,
                        'persistence': persistence_config,
                        'network': network_config,
                        'security': security_config,
                        'performance': performance_config
                    },
                    'optimization_analysis': {
                        'memory_optimizations': [],
                        'performance_optimizations': [],
                        'reliability_optimizations': [],
                        'security_optimizations': []
                    },
                    'configuration_score': {
                        'memory': 0,
                        'performance': 0,
                        'reliability': 0,
                        'security': 0,
                        'overall': 0
                    }
                }
                
                # Analyze memory configuration
                maxmemory = int(memory_config.get('maxmemory', 0))
                maxmemory_policy = memory_config.get('maxmemory-policy', 'noeviction')
                used_memory = server_info.get('used_memory', 0)
                
                memory_score = 0
                if maxmemory > 0:
                    memory_score += 25
                    if maxmemory_policy != 'noeviction':
                        memory_score += 25
                    if (used_memory / maxmemory) < 0.8:
                        memory_score += 25
                    memory_score += 25  # Base score for having memory config
                else:
                    config_analysis['optimization_analysis']['memory_optimizations'].append(
                        "Set maxmemory to prevent OOM issues and enable memory management"
                    )
                
                if maxmemory_policy == 'noeviction' and maxmemory > 0:
                    config_analysis['optimization_analysis']['memory_optimizations'].append(
                        "Consider setting an eviction policy (e.g., allkeys-lru) instead of noeviction"
                    )
                
                # Analyze performance configuration
                performance_score = 0
                hz = int(performance_config.get('hz', 10))
                slowlog_slower_than = int(performance_config.get('slowlog-log-slower-than', 10000))
                
                if hz >= 10:
                    performance_score += 25
                if slowlog_slower_than <= 10000:  # 10ms
                    performance_score += 25
                performance_score += 50  # Base score
                
                if hz < 10:
                    config_analysis['optimization_analysis']['performance_optimizations'].append(
                        f"Increase hz from {hz} to 10+ for better background task frequency"
                    )
                
                if slowlog_slower_than > 10000:
                    config_analysis['optimization_analysis']['performance_optimizations'].append(
                        f"Lower slowlog-log-slower-than from {slowlog_slower_than} to 10000 (10ms) for better monitoring"
                    )
                
                # Analyze reliability configuration
                reliability_score = 0
                save_config = persistence_config.get('save', '')
                aof_enabled = persistence_config.get('appendonly', 'no') == 'yes'
                
                if save_config != '' or aof_enabled:
                    reliability_score += 50
                    if save_config != '' and aof_enabled:
                        reliability_score += 50
                else:
                    config_analysis['optimization_analysis']['reliability_optimizations'].append(
                        "Enable persistence (RDB snapshots or AOF) to prevent data loss on restart"
                    )
                
                # Analyze security configuration
                security_score = 0
                requirepass = security_config.get('requirepass', '')
                protected_mode = security_config.get('protected-mode', 'yes')
                
                if requirepass:
                    security_score += 40
                if protected_mode == 'yes':
                    security_score += 30
                security_score += 30  # Base score
                
                if not requirepass:
                    config_analysis['optimization_analysis']['security_optimizations'].append(
                        "Set requirepass for authentication"
                    )
                
                if protected_mode != 'yes':
                    config_analysis['optimization_analysis']['security_optimizations'].append(
                        "Enable protected-mode for better security"
                    )
                
                # Calculate overall scores
                config_analysis['configuration_score'] = {
                    'memory': memory_score,
                    'performance': performance_score,
                    'reliability': reliability_score,
                    'security': security_score,
                    'overall': (memory_score + performance_score + reliability_score + security_score) // 4
                }
                
                client.close()
                return config_analysis
                
            except ImportError:
                raise Exception("redis library not available. Please install: pip install redis")
            
        except Exception as e:
            logger.error(f"Failed to analyze Redis configuration for {instance.name}: {e}")
            raise Exception(f"Failed to analyze Redis configuration: {str(e)}")