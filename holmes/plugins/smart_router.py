"""
Smart Router for HolmesGPT

Automatically parses user prompts to detect service types and instance hints,
then routes requests to appropriate toolsets with proper instance resolution.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RouteInfo:
    """Information extracted from prompt routing"""
    service_type: Optional[str] = None
    instance_hint: Optional[str] = None
    confidence: float = 0.0
    detected_keywords: List[str] = None
    extraction_method: str = ""

class SmartRouter:
    """
    Smart router that automatically resolves instances and routes to appropriate toolsets.
    """
    
    # Service type detection patterns
    SERVICE_PATTERNS = {
        'elasticsearch': {
            'keywords': [
                r'\belasticsearch\b', r'\bes\b', r'\bindex\b', r'\bindices\b', 
                r'\bcluster\s+health\b', r'\bsearch\b', r'\belastic\b',
                r'\bshards?\b', r'\bmapping\b', r'\bdocuments?\b'
            ],
            'priority': 1.0
        },
        'kafka': {
            'keywords': [
                r'\bkafka\b', r'\btopics?\b', r'\bconsumer\s+groups?\b', 
                r'\bproducers?\b', r'\bconsumers?\b', r'\bpartitions?\b',
                r'\boffsets?\b', r'\bmessages?\b', r'\bbrokers?\b'
            ],
            'priority': 1.0
        },
        'mongodb': {
            'keywords': [
                r'\bmongodb?\b', r'\bmongo\b', r'\bdatabases?\b', r'\bcollections?\b',
                r'\bdocuments?\b', r'\bbson\b', r'\bnosql\b', r'\bserver\s+status\b'
            ],
            'priority': 1.0
        },
        'redis': {
            'keywords': [
                r'\bredis\b', r'\bcache\b', r'\bmemory\s+usage\b', r'\bkeys?\b',
                r'\bstrings?\b', r'\bhashes?\b', r'\blists?\b', r'\bsets?\b',
                r'\bin-memory\b'
            ],
            'priority': 1.0
        },
        'kubernetes': {
            'keywords': [
                r'\bkubernetes\b', r'\bk8s\b', r'\bpods?\b', r'\bnodes?\b', 
                r'\bdeployments?\b', r'\bservices?\b', r'\bnamespaces?\b',
                r'\bcluster\b', r'\bcontainers?\b', r'\breplicasets?\b'
            ],
            'priority': 0.9  # Lower priority since it's more general
        },
        'kafkaconnect': {
            'keywords': [
                r'\bkafka\s+connect\b', r'\bconnectors?\b', r'\bconnect\s+cluster\b',
                r'\bsink\s+connector\b', r'\bsource\s+connector\b'
            ],
            'priority': 1.2  # Higher priority than kafka when connect is mentioned
        }
    }
    
    # Instance name extraction patterns (ordered by priority)
    INSTANCE_PATTERNS = [
        # Environment-based patterns (highest priority)
        {
            'pattern': r'(\w+(?:-\w+)*?)[-_]?(staging|stage|prod|production|dev|development|test|testing)',
            'priority': 1.0,
            'method': 'environment_based'
        },
        # Service-specific patterns
        {
            'pattern': r'(\w+(?:-\w+)*?)[-_]?(elasticsearch|kafka|mongodb|redis|k8s|kubernetes)',
            'priority': 0.9,
            'method': 'service_based'
        },
        # Direct instance references
        {
            'pattern': r'([\w-]+)(?:\s+(?:instance|cluster|environment))',
            'priority': 0.8,
            'method': 'direct_reference'
        },
        {
            'pattern': r'(?:instance|cluster)\s+([\w-]+)',
            'priority': 0.8,
            'method': 'direct_reference'
        },
        {
            'pattern': r'my\s+([\w-]+)\s+(?:instance|cluster)',
            'priority': 0.7,
            'method': 'possessive_reference'
        },
        # Multi-hyphen words (medium priority)
        {
            'pattern': r'(\w+(?:-\w+){2,})',
            'priority': 0.6,
            'method': 'multi_hyphen'
        },
        # Single hyphen words (lower priority)
        {
            'pattern': r'(\w+(?:-\w+){1})',
            'priority': 0.4,
            'method': 'single_hyphen'
        }
    ]
    
    # Common environment indicators
    ENVIRONMENT_INDICATORS = {
        'production': ['prod', 'production', 'prd'],
        'staging': ['staging', 'stage', 'stg'],
        'development': ['dev', 'development', 'develop'],
        'testing': ['test', 'testing', 'tst']
    }
    
    def __init__(self):
        """Initialize the Smart Router"""
        logger.info("🧠 Smart Router initialized")
    
    def extract_service_and_instance(self, prompt: str, context: Dict = None) -> RouteInfo:
        """
        Extract service type and instance hint from user prompt.
        
        Args:
            prompt: User's prompt/question
            context: Additional context (conversation history, user preferences, etc.)
            
        Returns:
            RouteInfo: Extracted routing information
        """
        logger.info(f"🔍 Analyzing prompt: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'")
        
        # Detect service type
        service_result = self._detect_service_type(prompt)
        
        # Extract instance hint
        instance_result = self._extract_instance_hint(prompt)
        
        # Combine results
        route_info = RouteInfo(
            service_type=service_result['service_type'],
            instance_hint=instance_result['instance_hint'],
            confidence=min(service_result['confidence'], instance_result['confidence']),
            detected_keywords=service_result['keywords'] + instance_result['keywords'],
            extraction_method=f"service:{service_result['method']}, instance:{instance_result['method']}"
        )
        
        logger.info(f"📊 Route analysis: service={route_info.service_type}, "
                   f"instance={route_info.instance_hint}, confidence={route_info.confidence:.2f}")
        
        return route_info
    
    def _detect_service_type(self, prompt: str) -> Dict:
        """Detect service type from prompt"""
        prompt_lower = prompt.lower()
        
        # Track matches for each service type
        service_scores = {}
        detected_keywords = []
        
        for service_type, config in self.SERVICE_PATTERNS.items():
            score = 0
            matched_keywords = []
            
            for pattern in config['keywords']:
                matches = re.findall(pattern, prompt_lower)
                if matches:
                    # Weight by priority and number of matches
                    match_score = len(matches) * config['priority']
                    score += match_score
                    matched_keywords.extend(matches)
            
            if score > 0:
                service_scores[service_type] = score
                detected_keywords.extend(matched_keywords)
        
        # Find the service with the highest score
        if service_scores:
            best_service = max(service_scores.items(), key=lambda x: x[1])
            confidence = min(1.0, best_service[1] / 2.0)  # Normalize confidence
            
            return {
                'service_type': best_service[0],
                'confidence': confidence,
                'keywords': detected_keywords,
                'method': 'keyword_matching'
            }
        else:
            return {
                'service_type': None,
                'confidence': 0.0,
                'keywords': [],
                'method': 'no_match'
            }
    
    def _extract_instance_hint(self, prompt: str) -> Dict:
        """Extract instance hint from prompt"""
        
        best_match = None
        best_score = 0
        best_method = "no_match"
        extracted_keywords = []
        
        # Try each pattern in priority order
        for pattern_config in self.INSTANCE_PATTERNS:
            pattern = pattern_config['pattern']
            priority = pattern_config['priority']
            method = pattern_config['method']
            
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                # Get the first capturing group (instance name)
                candidate = match.group(1) if match.groups() else match.group(0)
                
                # Calculate score based on pattern priority and candidate quality
                score = priority * self._score_instance_candidate(candidate)
                
                if score > best_score:
                    best_match = candidate
                    best_score = score
                    best_method = method
                    extracted_keywords = [candidate]
        
        # If no pattern match, look for specific instance-like words
        if not best_match:
            words = prompt.split()
            for word in words:
                if self._looks_like_instance_name(word):
                    best_match = word
                    best_score = 0.3  # Low confidence for generic word matching
                    best_method = "word_heuristic"
                    extracted_keywords = [word]
                    break
        
        confidence = min(1.0, best_score)
        
        return {
            'instance_hint': best_match,
            'confidence': confidence,
            'keywords': extracted_keywords,
            'method': best_method
        }
    
    def _score_instance_candidate(self, candidate: str) -> float:
        """Score an instance name candidate based on quality indicators"""
        if not candidate:
            return 0.0
        
        score = 0.5  # Base score
        
        # Length bonus (reasonable instance names are usually 3-50 chars)
        if 3 <= len(candidate) <= 50:
            score += 0.2
        
        # Hyphen bonus (many instance names have hyphens)
        if '-' in candidate:
            score += 0.3
        
        # Environment indicator bonus
        candidate_lower = candidate.lower()
        for env_type, indicators in self.ENVIRONMENT_INDICATORS.items():
            if any(indicator in candidate_lower for indicator in indicators):
                score += 0.4
                break
        
        # Avoid common words that are not instance names
        common_non_instances = {
            'my', 'the', 'this', 'that', 'cluster', 'instance', 'server',
            'service', 'application', 'app', 'system', 'health', 'status'
        }
        if candidate_lower in common_non_instances:
            score -= 0.5
        
        # Prefer longer, more specific names
        if len(candidate) > 10:
            score += 0.1
        
        return max(0.0, score)
    
    def _looks_like_instance_name(self, word: str) -> bool:
        """Check if a word looks like an instance name"""
        if len(word) < 3 or len(word) > 50:
            return False
        
        # Must contain letters
        if not re.search(r'[a-zA-Z]', word):
            return False
        
        # Prefer words with hyphens or numbers
        if '-' in word or re.search(r'\d', word):
            return True
        
        # Check for environment indicators
        word_lower = word.lower()
        for indicators in self.ENVIRONMENT_INDICATORS.values():
            if any(indicator in word_lower for indicator in indicators):
                return True
        
        return False
    
    def get_service_suggestions(self, prompt: str) -> List[str]:
        """Get suggestions for possible service types based on prompt"""
        prompt_lower = prompt.lower()
        suggestions = []
        
        for service_type, config in self.SERVICE_PATTERNS.items():
            for pattern in config['keywords']:
                if re.search(pattern, prompt_lower):
                    suggestions.append(service_type)
                    break
        
        return suggestions
    
    def validate_route_info(self, route_info: RouteInfo) -> Dict[str, Any]:
        """
        Validate and provide feedback on extracted route information.
        
        Returns:
            dict: Validation results with suggestions and confidence assessment
        """
        validation = {
            'is_valid': False,
            'confidence_level': 'none',
            'issues': [],
            'suggestions': []
        }
        
        # Check service type
        if not route_info.service_type:
            validation['issues'].append("No service type detected")
            validation['suggestions'].append("Try including service keywords like 'elasticsearch', 'kafka', 'mongodb', etc.")
        
        # Check instance hint
        if not route_info.instance_hint:
            validation['issues'].append("No instance name detected")
            validation['suggestions'].append("Try including instance name like 'production-cluster', 'staging-es', etc.")
        
        # Assess confidence level
        if route_info.confidence >= 0.8:
            validation['confidence_level'] = 'high'
            validation['is_valid'] = True
        elif route_info.confidence >= 0.5:
            validation['confidence_level'] = 'medium'
            validation['is_valid'] = True
        elif route_info.confidence >= 0.3:
            validation['confidence_level'] = 'low'
        else:
            validation['confidence_level'] = 'very_low'
        
        # If valid, no major issues
        if validation['is_valid'] and not validation['issues']:
            validation['suggestions'].append("Route information looks good!")
        
        return validation

# Global router instance
_smart_router = None

def get_smart_router() -> SmartRouter:
    """Get the global Smart Router instance"""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartRouter()
    return _smart_router

def parse_prompt_for_routing(prompt: str, context: Dict = None) -> RouteInfo:
    """
    Convenience function to parse a prompt and extract routing information.
    
    Usage:
        from holmes.plugins.smart_router import parse_prompt_for_routing
        
        route_info = parse_prompt_for_routing("Check health of my staging elasticsearch cluster")
        # Returns: RouteInfo(service_type='elasticsearch', instance_hint='staging', ...)
    
    Args:
        prompt: User's prompt
        context: Additional context
        
    Returns:
        RouteInfo: Extracted routing information
    """
    router = get_smart_router()
    return router.extract_service_and_instance(prompt, context) 