"""
InfraInsights Client for HolmesGPT Toolsets

This client handles authentication, instance discovery, and credential management
for the InfraInsights multi-instance architecture.
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


class InfraInsightsConfig(BaseModel):
    """Configuration for InfraInsights connection"""
    base_url: str = Field(..., description="InfraInsights API base URL")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    timeout: int = Field(30, description="Request timeout in seconds")


class ServiceInstance(BaseModel):
    """Service instance information"""
    instanceId: str
    name: str
    serviceType: str
    environment: str
    status: str
    config: Dict[str, Any]
    ownerId: str
    tags: List[str] = []


class InfraInsightsClient:
    """Client for interacting with InfraInsights API"""
    
    def __init__(self, config: InfraInsightsConfig):
        self.config = config
        self.session = requests.Session()
        self.session.timeout = config.timeout
        
        # Set up authentication
        if config.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json'
            })
        elif config.username and config.password:
            # Basic auth
            self.session.auth = (config.username, config.password)
            self.session.headers.update({'Content-Type': 'application/json'})
        
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to InfraInsights API"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"InfraInsights API request failed: {e}")
            raise Exception(f"Failed to connect to InfraInsights API: {e}")
    
    def get_service_instances(self, service_type: Optional[str] = None, user_id: Optional[str] = None) -> List[ServiceInstance]:
        """Get service instances, optionally filtered by type and user access"""
        cache_key = f"instances:{service_type}:{user_id}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return cached_data
        
        # Build query parameters
        params = {}
        if service_type:
            params['serviceType'] = service_type
        if user_id:
            params['userId'] = user_id
        
        # Make API request
        data = self._make_request('GET', '/api/service-instances', params=params)
        
        # Parse response
        instances = []
        for instance_data in data.get('instances', []):
            try:
                instance = ServiceInstance(**instance_data)
                instances.append(instance)
            except Exception as e:
                logging.warning(f"Failed to parse service instance: {e}")
        
        # Cache result
        self._cache[cache_key] = (instances, datetime.now())
        
        return instances
    
    def get_instance_config(self, instance_id: str) -> Dict[str, Any]:
        """Get configuration for a specific service instance"""
        cache_key = f"config:{instance_id}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return cached_data
        
        # Make API request
        data = self._make_request('GET', f'/api/service-instances/{instance_id}')
        
        # Cache result
        self._cache[cache_key] = (data, datetime.now())
        
        return data
    
    def get_user_context(self, user_id: str, service_type: str) -> Optional[Dict[str, Any]]:
        """Get current user context for a service type"""
        try:
            data = self._make_request('GET', f'/api/context/{user_id}/{service_type}')
            return data.get('context')
        except Exception:
            return None
    
    def set_user_context(self, user_id: str, service_type: str, instance_id: str) -> Dict[str, Any]:
        """Set current user context for a service type"""
        data = self._make_request('POST', f'/api/context/{user_id}/{service_type}', 
                                json={'instanceId': instance_id})
        return data
    
    def identify_instance_from_prompt(self, prompt: str, service_type: str, user_id: Optional[str] = None) -> Optional[ServiceInstance]:
        """
        Identify which service instance the user is referring to in their prompt.
        This uses simple keyword matching and instance metadata.
        """
        instances = self.get_service_instances(service_type, user_id)
        
        if not instances:
            return None
        
        # If only one instance, return it
        if len(instances) == 1:
            return instances[0]
        
        # Score instances based on prompt keywords
        scored_instances = []
        prompt_lower = prompt.lower()
        
        for instance in instances:
            score = 0
            
            # Check instance name
            if instance.name.lower() in prompt_lower:
                score += 10
            
            # Check environment
            if instance.environment.lower() in prompt_lower:
                score += 5
            
            # Check tags
            for tag in instance.tags:
                if tag.lower() in prompt_lower:
                    score += 3
            
            # Check if instance is active
            if instance.status == 'active':
                score += 2
            
            scored_instances.append((instance, score))
        
        # Sort by score and return the highest
        scored_instances.sort(key=lambda x: x[1], reverse=True)
        
        if scored_instances and scored_instances[0][1] > 0:
            return scored_instances[0][0]
        
        # If no clear match, return the first active instance
        active_instances = [inst for inst in instances if inst.status == 'active']
        if active_instances:
            return active_instances[0]
        
        return instances[0]  # Return first instance as fallback
    
    def get_connection_config(self, instance_id: str) -> Dict[str, Any]:
        """Get connection configuration for a service instance"""
        instance_data = self.get_instance_config(instance_id)
        return instance_data.get('config', {})
    
    def clear_cache(self):
        """Clear the client cache"""
        self._cache.clear()
    
    def health_check(self) -> bool:
        """Check if InfraInsights API is accessible"""
        try:
            self._make_request('GET', '/api/health')
            return True
        except Exception:
            return False
    
    def get_service_instance_summary(self, service_type: str) -> Dict[str, Any]:
        """Get a summary of available instances for a service type"""
        try:
            instances = self.get_service_instances(service_type)
            
            summary = {
                "service_type": service_type,
                "total_instances": len(instances),
                "active_instances": len([i for i in instances if i.status == 'active']),
                "environments": list(set(i.environment for i in instances)),
                "instance_names": [i.name for i in instances],
                "api_accessible": True
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
                "error": str(e)
            } 