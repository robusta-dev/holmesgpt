# TODO for Holmes Check Feature

## Dropped Features (Removed from implementation)

The following features were originally planned but have been dropped from the current implementation:

### Retry Logic
- **repeat**: Number of times to repeat a check before determining final status
- **failure_threshold**: Number of failures allowed before marking check as failed
- **repeat_delay**: Delay in seconds between retry attempts

These fields were removed to simplify the implementation. If retry logic is needed in the future, consider:
1. Implementing at the orchestration layer (e.g., systemd timers, k8s CronJobs)
2. Using exponential backoff strategies
3. Providing clearer semantics for partial failures

### Result Tracking
- **attempts**: Array tracking individual attempt results
- **rationales**: Array of explanations for each attempt

These were removed as they're not needed without the retry logic.

## Future Enhancements

- [ ] Scheduled checks (cron-style scheduling)
- [ ] Check groups for organizing related checks
- [ ] Additional destination types (Email, Webhooks, OpsGenie)
- [ ] Check dependencies (run check B only if check A passes)
- [ ] Metric collection and historical tracking
- [ ] Check result caching with TTL
