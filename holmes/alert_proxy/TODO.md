# Alerts viewer TODO
- Show intermediate output and maybe tool calls in Alert Inspector pane
- When loading alerts, update UI as soon as we get alerts from one AM not only when fetching from all is done

# Alert Proxy TODO

## Features to Implement

### Caching Support
- Add `--cache-ttl` flag to webhook proxy server
- Implement alert deduplication cache to reduce LLM API calls
- Cache similar alerts based on fingerprint or label similarity
- Default TTL: 300 seconds (5 minutes)
- Track cache hit rate in stats

Example usage:
```bash
# Cache similar alerts for 10 minutes
holmes alertmanager-proxy serve --cache-ttl 600
```

### Additional Improvements
- Add prometheus metrics endpoint for monitoring
- Support for batch processing of alerts
- Rate limiting for LLM API calls
- Alert routing based on labels
