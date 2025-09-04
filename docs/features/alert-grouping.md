# Alert Grouping (Experimental)

HolmesGPT can intelligently group alerts by their root cause, reducing noise and helping you focus on the actual problems rather than symptoms.

## How It Works

The alert grouping system uses a smart, adaptive approach:

1. **Root Cause Analysis**: Each alert is investigated to determine its root cause
2. **Intelligent Grouping**: Alerts with the same root cause are grouped together
3. **Rule Learning**: As patterns emerge, the system generates rules for faster matching
4. **Self-Verification**: New rules are verified for accuracy before being trusted

## Usage

To enable alert grouping when investigating AlertManager alerts:

```bash
holmes investigate alertmanager --group-alerts
```

This will:
- Fetch all firing alerts from AlertManager
- Analyze each alert to determine root cause
- Group related alerts together
- Show a summary of the groups

## Example Output

```
Grouping 15 alerts by root cause...
[1/15] Processing HighMemoryUsage...
  Running root cause analysis...
  → Grouped into: Memory exhaustion in payment service...
[2/15] Processing PodOOMKilled...
  → Grouped into: Memory exhaustion in payment service...
[3/15] Processing DatabaseConnectionTimeout...
  Running root cause analysis...
  → Grouped into: Database connection pool exhausted...

Alert Grouping Summary:
Total alerts: 15
Groups created: 3
Rules generated: 2

Groups:

Group group-a3f2d8e1:
  Root Cause: Memory exhaustion in payment service
  Category: application
  Alerts (7):
    - HighMemoryUsage
    - PodOOMKilled
    - ContainerRestart
    - ServiceUnavailable
    - HighLatency
    ... and 2 more
  ✓ Rule generated

Group group-b7c4e9a2:
  Root Cause: Database connection pool exhausted
  Category: database
  Alerts (5):
    - DatabaseConnectionTimeout
    - ConnectionPoolExhausted
    - SlowQueries
    - APITimeout
    - TransactionRollback

Group group-c1d5f3b8:
  Root Cause: Kubernetes node disk pressure
  Category: infrastructure
  Alerts (3):
    - NodeDiskPressure
    - PodEvicted
    - ImagePullBackOff
```

## How Rules Work

After grouping several alerts with the same root cause, the system may generate rules to speed up future grouping:

1. **Pattern Recognition**: When 3+ alerts share a root cause, the system looks for patterns
2. **Rule Generation**: If a clear pattern exists, a rule is created
3. **Verification Phase**: The first 5 uses of each rule are verified by the LLM
4. **Trust Building**: After successful verifications, the rule is applied automatically
5. **Self-Correction**: If a rule fails verification, it's automatically adjusted

## Benefits

- **Reduced Noise**: See the forest, not just the trees
- **Faster Resolution**: Focus on root causes, not symptoms
- **Learning System**: Gets smarter over time as it learns your infrastructure patterns
- **Explainable**: Every grouping decision can be traced back to evidence

## Configuration

The grouping behavior can be customized:

```python
# In your code
from holmes.core.alert_grouping import SmartAlertGrouper

grouper = SmartAlertGrouper(
    ai=ai,
    console=console,
    verify_first_n=5  # Number of times to verify a rule before trusting it
)
```

## Limitations

This is an experimental feature with some limitations:

- Initial processing may be slower as RCA is performed on each alert
- Rule generation requires at least 3 similar alerts
- Complex multi-cause incidents may not group perfectly
- Currently only available for AlertManager investigations

## Future Enhancements

Planned improvements include:

- Support for other alert sources (PagerDuty, OpsGenie, etc.)
- Incident correlation across time windows
- Custom rule definition via configuration
- Integration with incident management systems
- Historical pattern analysis
