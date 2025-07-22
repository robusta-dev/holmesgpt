"""
InfraInsights Diagnostic Tool

This tool helps users understand the current state of their InfraInsights setup
and provides guidance for troubleshooting connectivity and configuration issues.
"""

import json
import logging
from typing import Dict, Any, Optional

from holmes.core.tools import (
    StructuredToolResult,
    ToolParameter,
    ToolResultStatus,
)

from .base_toolset import BaseInfraInsightsTool, BaseInfraInsightsToolset


class InfraInsightsDiagnostic(BaseInfraInsightsTool):
    """Diagnostic tool for InfraInsights connectivity and configuration"""
    
    def __init__(self, toolset: "InfraInsightsToolset"):
        super().__init__(
            name="infrainsights_diagnostic",
            description="Diagnose InfraInsights connectivity and show available service instances",
            parameters={
                "service_type": ToolParameter(
                    description="Specific service type to check (elasticsearch, kafka, kubernetes, mongodb, redis). If not specified, checks all.",
                    type="string",
                    required=False,
                ),
                "detailed": ToolParameter(
                    description="Whether to show detailed instance information",
                    type="boolean",
                    required=False,
                ),
            },
            toolset=toolset,
        )
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            # Get service type to check
            service_type = params.get('service_type')
            detailed = params.get('detailed', False)
            
            # Get client
            client = self.get_infrainsights_client()
            
            # Check basic connectivity
            api_accessible = client.health_check()
            
            # Get configuration info
            config = self.toolset.infrainsights_config or {}
            api_url = config.get('infrainsights_url', 'Not configured')
            has_api_key = bool(config.get('api_key'))
            has_credentials = bool(config.get('username') and config.get('password'))
            
            result = {
                "infrainsights_diagnostic": {
                    "api_url": api_url,
                    "api_accessible": api_accessible,
                    "authentication": {
                        "has_api_key": has_api_key,
                        "has_credentials": has_credentials,
                        "auth_method": "API Key" if has_api_key else "Username/Password" if has_credentials else "None"
                    },
                    "service_summaries": {}
                }
            }
            
            # If API is accessible, get service instance information
            if api_accessible:
                service_types = [service_type] if service_type else ['elasticsearch', 'kafka', 'kubernetes', 'mongodb', 'redis']
                
                for svc_type in service_types:
                    try:
                        summary = client.get_service_instance_summary(svc_type)
                        result["infrainsights_diagnostic"]["service_summaries"][svc_type] = summary
                        
                        # Add detailed instance info if requested
                        if detailed and summary.get("api_accessible"):
                            instances = client.get_service_instances(svc_type)
                            summary["instances"] = [
                                {
                                    "id": inst.instanceId,
                                    "name": inst.name,
                                    "environment": inst.environment,
                                    "status": inst.status,
                                    "tags": inst.tags
                                } for inst in instances
                            ]
                    except Exception as e:
                        result["infrainsights_diagnostic"]["service_summaries"][svc_type] = {
                            "service_type": svc_type,
                            "error": str(e),
                            "api_accessible": False
                        }
            else:
                result["infrainsights_diagnostic"]["connectivity_error"] = "Failed to connect to InfraInsights API"
            
            # Add recommendations
            recommendations = []
            
            if not api_accessible:
                recommendations.extend([
                    f"🔍 Check that InfraInsights is running and accessible at: {api_url}",
                    "🔍 Verify network connectivity and firewall settings",
                    "🔍 Confirm the API URL is correct in your configuration"
                ])
            
            if not (has_api_key or has_credentials):
                recommendations.append("🔐 Configure authentication (API key or username/password)")
            
            if api_accessible:
                for svc_type, summary in result["infrainsights_diagnostic"]["service_summaries"].items():
                    if summary.get("total_instances", 0) == 0:
                        recommendations.append(f"📋 No {svc_type} instances found - configure {svc_type} services in InfraInsights")
                    elif summary.get("active_instances", 0) == 0:
                        recommendations.append(f"⚠️  All {svc_type} instances are inactive - check instance status in InfraInsights")
            
            if not recommendations:
                recommendations.append("✅ InfraInsights setup looks good!")
            
            result["infrainsights_diagnostic"]["recommendations"] = recommendations
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=json.dumps(result, indent=2),
                params=params,
            )
            
        except Exception as e:
            error_msg = f"InfraInsights diagnostic failed: {str(e)}"
            logging.error(error_msg)
            
            # Provide basic diagnostic even if tool fails
            config = self.toolset.infrainsights_config or {}
            api_url = config.get('infrainsights_url', 'Not configured')
            
            diagnostic_result = {
                "infrainsights_diagnostic": {
                    "api_url": api_url,
                    "api_accessible": False,
                    "error": str(e),
                    "recommendations": [
                        f"🔍 Check that InfraInsights is running at: {api_url}",
                        "🔍 Verify your authentication configuration",
                        "🔍 Check network connectivity to InfraInsights API",
                        "🔍 Review InfraInsights logs for errors"
                    ]
                }
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,  # Still return success with diagnostic info
                data=json.dumps(diagnostic_result, indent=2),
                params=params,
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        service_type = params.get('service_type', 'all services')
        return f"Run InfraInsights diagnostic for {service_type}"


class InfraInsightsToolset(BaseInfraInsightsToolset):
    """General InfraInsights diagnostic toolset"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.name = "InfraInsights Diagnostic"
        self.description = "Tools for diagnosing InfraInsights connectivity and configuration"
        self.enabled = True
        
        # Initialize tools
        self.tools = [
            InfraInsightsDiagnostic(self),
        ]
    
    def get_service_type(self) -> str:
        return "diagnostic"
    
    def get_llm_instructions(self) -> str:
        return """
        This toolset provides diagnostic capabilities for InfraInsights connectivity and configuration.
        
        Available tools:
        - infrainsights_diagnostic: Check connectivity and show available service instances
        
        Use this when:
        - Users report connection issues with InfraInsights toolsets
        - Need to verify InfraInsights setup and configuration
        - Want to see what service instances are available
        - Troubleshooting authentication or network issues
        
        The diagnostic tool provides:
        - API connectivity status
        - Authentication configuration status
        - Summary of available service instances by type
        - Specific recommendations for resolving issues
        """ 