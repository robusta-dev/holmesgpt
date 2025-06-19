When a user request checking issues on Atlas mongodb project use these steps. 

1, Use atlas_return_project_alerts and atlas_return_events_from_project first to find any known potential issues on the project.
2. for performance issues use atlas_return_project_slow_queries to see a list of slow queries YOU MUST check this for all processes of the project.
3, Always use atlas_return_logs_for_host_in_project to get the logs of the last hour to see for potential issues.


When asked about mongodb connection count or queue state ALWAYS use PrometheusToolset, execute_prometheus_range_query or execute_prometheus_instant_query tools and add a graph with these metrics:
1. mongodb_connections_current
2. mongodb_globalLock_currentQueue_readers
When asked about atlas mongodb opcounter ALWAYS use PrometheusToolset, execute_prometheus_range_query or execute_prometheus_instant_query tools and add a graph with these metrics:
1. rate(mongodb_opcounters_insert[5m])
2. rate(mongodb_opcounters_query[5m])
When asked about atlas mongodb replications or replication lag ALWAYS use PrometheusToolset, execute_prometheus_range_query or execute_prometheus_instant_query tools and add a graph with these metrics:
1. mongodb_metrics_repl_waiters_replication
2. rate(mongodb_metrics_repl_write_batches_totalMillis[5m])
3. rate(mongodb_metrics_repl_apply_ops[5m])
When asked asked about collscan queries, ALWAYS use atlas_return_project_slow_queries to fetch slow queries that trigger the collscan log line.
When asked about mongodb memory or cpu status ALWAYS use PrometheusToolset, execute_prometheus_range_query or execute_prometheus_instant_query tools and add a graph with these metrics:
1.rate(mongodb_mem_resident[1m])
2. (rate(mongodb_extra_info_user_time_us[1m]) / rate(mongodb_extra_info_system_time_us[1m]))
