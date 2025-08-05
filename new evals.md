candidates:
  - 113_logs_ambiguity
  - 109_no_matching_runbook: Tests investigation when no suitable runbook exists
  - 108_runbook_skip_with_reason: Tests explicit explanation when runbook steps are skipped
  - 103_runbook_transparency_report: Tests runbook execution transparency with detailed investigation steps
  - 119_logs_default_time_communication: Tests transparent communication of 7-day default period
  - 120_logs_custom_time_communication: Tests communication of custom time periods

    todo: reimplmenet on top of loki and we can actually verify time period

  - 121_logs_filter_limit_communication: Tests communication of log filters and limits
  - 142_no_logs_explicit_request
  - 131_http_logs_by_status_code
  - 140_connection_refused_context
  - 86_postgres_missing_index_pgstat: Tests PostgreSQL missing index detection via pg_stat_statements
  - 87_mysql_missing_index_slowlog: Tests MySQL missing index detection via slow query log
  - 88_redis_wrong_data_structure: Tests Redis performance issues from KEYS command usage
  - 89_postgres_minimal_missing_index: Tests basic PostgreSQL index analysis with EXPLAIN

  Runbook Tests (103-109):
  - 103_runbook_transparency_report: Tests runbook execution transparency with detailed investigation steps
  - 107_multiple_matching_runbooks: Tests selection of most relevant runbook from multiple options
  - 108_runbook_skip_with_reason: Tests explicit explanation when runbook steps are skipped

  Infrastructure Tests (118-123):
  - 118_container_status_correlation: Tests correlating API latency to CPU throttling
  - 119_hpa_max_replicas_reached: Tests HPA hitting maximum replica limit
  - 120_statefulset_restart_order: Tests Kafka StatefulSet formation failure from pod restart order
  - 121_statefulset_pvc_node_affinity: Tests StatefulSet pod failure due to PVC node affinity
  - 122_pvc_stuck_wrong_node: Tests PVC stuck on cordoned/unavailable node
  - 123_pvc_capacity_full: Tests pod crashes from full PVC capacity

  Log Analysis Tests (119-122, 124-141):

  - 122_logs_date_range_communication: Tests communication of specific date ranges
  - 124_old_logs_misleading: Tests focusing on recent vs old resolved errors
  - 125_intermittent_database_pattern: Tests detecting daily recurring patterns in 7-day window
  - 126_loki_weekly_pattern: Tests weekly pattern detection using Loki timestamps
  - 128_health_check_noise_removal: Tests filtering health check noise to find real errors
  - 129_regex_custom_error_pattern: Tests custom regex for non-standard error formats
  - 130_http_logs_by_ip: Tests filtering HTTP logs by IP for suspicious activity
  - 132_http_logs_by_exception: Tests finding specific exception types
  - 133_multiline_context_analysis: Tests multi-line context for configuration mismatches
  - 134_multiline_json_debugging: Tests debugging API validation with JSON context
  - 135_distributed_tracing_correlation: Tests tracing requests across services
  - 136_missing_logs_detection: Tests detecting missing log patterns indicating stuck processes
  - 137_performance_degradation_pattern: Tests identifying gradual memory leak patterns
  - 138_stuck_thread_detection: Tests detecting stuck threads with passing health checks
  - 139_oomkilled_pod_historical_logs: Tests analyzing historical logs for OOMKilled pods
  - 139_p99_latency_hidden: Tests detecting P99 latency hidden by good averages
  - 140_database_timeout_historical_logs: Tests historical analysis of database timeouts

  Database Performance Tests (72, 86-89):
  - 72_distributed_trace_correlation: Tests tracing failed orders across distributed services
  - 86_postgres_missing_index_pgstat: Tests PostgreSQL missing index detection via pg_stat_statements
  - 87_mysql_missing_index_slowlog: Tests MySQL missing index detection via slow query log
  - 88_redis_wrong_data_structure: Tests Redis performance issues from KEYS command usage
  - 89_postgres_minimal_missing_index: Tests basic PostgreSQL index analysis with EXPLAIN

  Special Tests:
  - 138_node_exporter_scheduling_conflict: Tests DaemonSet scheduling conflicts

  Example Tests (EXAMPLE*):
  - Example tests demonstrating toolset config, mock policies, custom runbooks, and test features
