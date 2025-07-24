import logging
from typing import Dict, List, Any

from holmes.core.tools import Toolset

logger = logging.getLogger(__name__)

# Import enhanced toolsets
from .enhanced_elasticsearch_toolset import EnhancedElasticsearchToolset
from .enhanced_mongodb_toolset import EnhancedMongoDBToolset
from .enhanced_redis_toolset import EnhancedRedisToolset
from .comprehensive_kafka_toolset import ComprehensiveKafkaToolset

# List of available toolsets - used by the loader
AVAILABLE_TOOLSETS = {
    'enhanced_elasticsearch': EnhancedElasticsearchToolset,
    'enhanced_mongodb': EnhancedMongoDBToolset,
    'enhanced_redis': EnhancedRedisToolset,
    'comprehensive_kafka': ComprehensiveKafkaToolset,
}

def get_infrainsights_toolsets(config: Dict[str, Any] = None) -> List[Toolset]:
    """
    Get all available InfraInsights toolsets
    """
    toolsets = []
    
    if config is None:
        config = {}
    
    # Enhanced Elasticsearch toolset
    if config.get('elasticsearch', {}).get('enabled', False):
        try:
            elasticsearch_toolset = EnhancedElasticsearchToolset()
            elasticsearch_toolset.configure(config.get('elasticsearch', {}))
            toolsets.append(elasticsearch_toolset)
            logger.info("✅ Enhanced Elasticsearch toolset loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Enhanced Elasticsearch toolset: {e}")
    
    # Enhanced MongoDB toolset
    if config.get('mongodb', {}).get('enabled', False):
        try:
            mongodb_toolset = EnhancedMongoDBToolset()
            mongodb_toolset.configure(config.get('mongodb', {}))
            toolsets.append(mongodb_toolset)
            logger.info("✅ Enhanced MongoDB toolset loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Enhanced MongoDB toolset: {e}")
    
    # Enhanced Redis toolset - support multiple config key variations
    redis_configs = [
        config.get('redis', {}),
        config.get('infrainsights_redis', {}),
        config.get('infrainsights_redis_enhanced', {})
    ]
    
    for redis_config in redis_configs:
        if redis_config.get('enabled', False):
            try:
                redis_toolset = EnhancedRedisToolset()
                redis_toolset.configure(redis_config)
                toolsets.append(redis_toolset)
                logger.info("✅ Enhanced Redis toolset loaded")
                break  # Only load one instance of Redis toolset
            except Exception as e:
                logger.error(f"❌ Failed to load Enhanced Redis toolset: {e}")
    
    # Comprehensive Kafka toolset - support multiple config key variations
    kafka_configs = [
        config.get('kafka', {}),
        config.get('infrainsights_kafka', {}),
        config.get('infrainsights_kafka_comprehensive', {})
    ]
    
    for kafka_config in kafka_configs:
        if kafka_config.get('enabled', False):
            try:
                kafka_toolset = ComprehensiveKafkaToolset()
                kafka_toolset.configure(kafka_config)
                toolsets.append(kafka_toolset)
                logger.info("✅ Comprehensive Kafka toolset loaded")
                break  # Only load one instance of Kafka toolset
            except Exception as e:
                logger.error(f"❌ Failed to load Comprehensive Kafka toolset: {e}")
    
    return toolsets 