# TODO for Holmes Check Feature

## Architecture Considerations

### CRD Design Pattern
Consider splitting into two CRDs following K8s Job/CronJob pattern:
- **HealthCheck CRD**: For one-time execution checks (like K8s Job)
- **ScheduledHealthCheck CRD**: For recurring checks with cron schedule (like K8s CronJob)

**Current approach (single HealthCheck CRD):**
- Simpler, fewer resources to manage
- Schedule field is optional - if missing, it's a one-time check
- Works well for current use case

**Two CRDs approach benefits:**
- More explicit - follows established K8s patterns
- Clear separation of concerns
- HealthCheck = one-time execution
- ScheduledHealthCheck = recurring execution with schedule
- Could share common spec fields through composition

For now, the single CRD with optional schedule works fine. If migrating to two CRDs later, it would provide cleaner separation but adds complexity.

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
