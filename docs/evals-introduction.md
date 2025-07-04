# HolmesGPT Evaluations - Introduction


- [Docs on writing your own evals](./evals-writing.md).
- [Use Braintrust to view analyze results (optional)](./evals-reporting.md).

## Overview

HolmesGPT uses automated evaluations (evals) to ensure consistent performance across different LLM models and to catch regressions during development. These evaluations test the system's ability to correctly diagnose Kubernetes issues.

The eval system comprises two main test suites:

- **Ask Holmes**: Tests single-question interactions with HolmesGPT
- **Investigate**: Tests HolmesGPT's ability to investigate specific issues reported by AlertManager

Evals use fixtures that simulate real Kubernetes environments and tool outputs, allowing comprehensive testing without requiring live clusters.

While results are tracked and analyzed using Braintrust, Braintrust is not necessary to writing, running and debugging evals.

## Example

Below is an example of a report added to pull requests to catch regressions:

| Test suite | Test case | Status |
| --- | --- | --- |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [01_how_many_pods](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=940662ed-541e-4582-ae8f-11c5e59ead23) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [02_what_is_wrong_with_pod](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=7028baa8-a23d-4d1f-b1b0-7fcbfe6d43e0) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [02_what_is_wrong_with_pod_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=e4312642-d5be-498b-8995-0a5b72d3cc1d) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [03_what_is_the_command_to_port_forward](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=6dc4f866-1ba6-415a-a8a2-bd7469de63c4) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [04_related_k8s_events](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=383224df-a8da-4219-a758-38c5e03ff31b) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [05_image_version](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=b03ca78a-9d44-48d0-80bc-07745278831e) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [06_explain_issue](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=63786cc9-4a9e-46c2-ba0a-9c507f9b2cd0) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [07_high_latency](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=b605890d-7c55-4e04-b370-a55186c5f620) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [07_high_latency_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=38c706d2-77e4-44fd-bc17-e6d68dccfe7e) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [08_sock_shop_frontend](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=322dd286-fa4d-43fc-9ab5-931f6fe5e899) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [09_crashpod](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=b3e6de8d-c59b-4bec-a155-55fb4ad43e8a) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [10_image_pull_backoff](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=434bf53e-42d5-4983-b8b7-ede32ff1e69e) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [11_init_containers](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=b59c5506-c573-4221-9663-b48ec06fea05) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [12_job_crashing](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=a2ba0276-2b43-4e5c-8d0f-2a8a9bb229b1) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [12_job_crashing_CORALOGIX](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=8c731c44-b63b-4579-ac85-feaba35c2c3d) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [12_job_crashing_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=2fb3eb61-9343-4c11-92a2-c56524f6a0f4) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [13_pending_node_selector](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=42d6b38f-7cf0-4d39-aab6-468c3936966f) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [14_pending_resources](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=f72f775a-a7ef-43b6-86dc-9a25a7f7ab0b) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [15_failed_readiness_probe](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=6438dbeb-caec-48c1-88d7-4d2beba866e4) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [16_failed_no_toolset_found](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=f56de9b4-c80e-4e75-8f08-552f7d6c1006) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [17_oom_kill](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=4d0e0379-f522-4d54-8d5e-22a7a7f1ea4a) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [18_crash_looping_v2](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=686074ee-9065-488d-86d5-3d1401da1f4e) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [19_detect_missing_app_details](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=3789345c-d48c-4eb3-93af-02a387deeea2) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [20_long_log_file_search_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=53d69c05-12e5-42f6-90de-e80172a30cb3) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [21_job_fail_curl_no_svc_account](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=10163a7b-83b6-4dff-8bde-193bcbb180c3) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [22_high_latency_dbi_down](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=bcf0cb2e-3fa5-4466-9af2-7f34b83aa114) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [23_app_error_in_current_logs](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=989bbfe4-6196-4aca-8d84-a39c2030e6c6) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [23_app_error_in_current_logs_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=f62f4031-5bf4-4d25-a9c1-1918629cb177) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [24_misconfigured_pvc](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=bf186b9c-87aa-4219-a1a1-a165916df2d8) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [25_misconfigured_ingress_class](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=0b1aa110-cc02-49e1-870c-7cfec7e43701) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [26_multi_container_logs](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=2c846f97-ac39-4d82-aa00-8cfbd8884bec) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [27_permissions_error_no_helm_tools](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=7bef7159-9912-4aab-ad73-6ffa43a52ec6) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [28_permissions_error_helm_tools_enabled](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=5e19eb3e-b230-4183-a898-58b745c37aaf) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [29_events_from_alert_manager](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=098c0435-2dbc-46de-bad0-1877daef30d0) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [30_basic_promql_graph_cluster_memory](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=c671fed6-0c97-431a-a54c-76ff17218d05) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [31_basic_promql_graph_pod_memory](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=6acf29ce-0f11-4979-a696-54113620da2f) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [32_basic_promql_graph_pod_cpu](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=5eafab06-c474-4c40-82db-1beffaf445d3) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [33_http_latency_graph](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=75ad0227-9e09-49c1-86ad-21ad5ab9ef80) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [34_memory_graph](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=b8265337-6d13-43b3-9e21-3c7c2a6651e9) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [35_tempo](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=106082e8-88d3-45c9-ab17-b327f4487744) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [36_argocd_find_resource](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=fd0b39e7-c12e-4161-9140-5ac7cb7980a0) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [37_argocd_wrong_namespace](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=142289e5-efb4-4ec9-ba70-b2764b0d3d40) | :warning: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [38_rabbitmq_split_head](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=5b829cdc-196a-429f-bd4c-3a72f652365e) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [39_failed_toolset](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=ffd95a43-af6d-4bbc-80a6-72d8cfec44b8) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [40_disabled_toolset](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=1f22e939-34b1-4c48-8e7e-7989142d6606) | :white_check_mark: |
| [ask_holmes](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1) | [41_setup_argo](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/ask_holmes:github-15460174219.1581.1?r=e7ee49fa-2d35-4e97-ae23-85732e24f1f1) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [01_oom_kill](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=8f9ad9ba-41f9-473a-80f8-7dfced60dbf5) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [02_crashloop_backoff](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=125aea21-87c7-4cf1-a4f7-817d46297d05) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [03_cpu_throttling](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=76a8d2a8-dd33-47b8-8e89-8f3582bef254) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [04_image_pull_backoff](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=0c94ff6f-af73-49d1-9724-447aa1eaf94e) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [05_crashpod](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=9319a4bc-5913-4a69-b721-3f495302de2f) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [05_crashpod_LOKI](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=ef6657ee-5dbb-4cbc-a71a-66d0f8b28cb7) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [06_job_failure](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=7720e20f-1a45-4c94-9938-941675e82d0a) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [07_job_syntax_error](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=7512239d-5f74-4b5d-b4ee-e47fccd794be) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [08_memory_pressure](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=36be5e88-20ff-42ba-b8ab-a1e09c45d414) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [09_high_latency](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=dd3cd28b-131c-48d1-9381-3894c611879f) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [10_KubeDeploymentReplicasMismatch](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=2080ddca-f69c-47b2-a06c-736704d4dd43) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [11_KubePodCrashLooping](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=7f4cd0d5-0f53-42dc-81cc-1b35117931d3) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [12_KubePodNotReady](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=8c816950-7d9d-42d8-88dd-f73b54490267) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [13_Watchdog](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=22f1eb77-a47c-4c3b-89b4-3c2d06f701a0) | :white_check_mark: |
| [investigate](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1) | [14_tempo](https://www.braintrust.dev/app/robustadev/p/HolmesGPT/experiments/investigate:github-15460174219.1581.1?r=534eb7d7-de62-4dcb-ac9a-7358151cf91c) | :white_check_mark: |


**Legend**

- :white_check_mark: the test was successful
- :warning: the test failed but is known to be flakky or known to fail
- :x: the test failed and should be fixed before merging the PR

## Why Evaluations Matter

Evaluations serve several critical purposes:

1. **Quality Assurance**: Ensure HolmesGPT provides accurate diagnostics and recommendations
2. **Model Comparison**: Compare performance across different LLM models (GPT-4, Claude, Gemini, etc.)
3. **Regression Testing**: Catch performance degradations when updating code or dependencies
4. **Toolset Validation**: Verify that new toolsets and integrations work correctly
5. **Continuous Improvement**: Identify areas where HolmesGPT needs enhancement

## How to Run Evaluations

### Basic Usage

Install dependencies:
```bash
poetry install
```

Run all evaluations:
```bash
poetry run pytest ./tests/llm/test_*.py --no-cov --disable-warnings
```

By default the tests load and present mock files to the LLM whenever it asks for them. If a mock file is not present for a tool call, the tool call is passed through to the live tool itself. In a lot of cases this can cause the eval to fail unless the live environment (k8s cluster) matches what the LLM expects.

Run specific test suite:
```bash
poetry run pytest ./tests/llm/test_ask_holmes.py --no-cov --disable-warnings
poetry run pytest ./tests/llm/test_investigate.py --no-cov --disable-warnings
```

Run a specific test case:
```bash
poetry run pytest ./tests/llm/test_ask_holmes.py -k "01_how_many_pods" --no-cov --disable-warnings
```

> It is possible to investigate and debug why an eval fails by the output provided in the console. The output includes the correctness score, the reasoning for the score, information about what tools were called, the expected answer, as well as the LLM's answer.

### Environment Variables

Configure evaluations using these environment variables:

| Variable | Example | Description |
|----------|---------|-------------|
| `MODEL` | `MODEL=anthropic/claude-3.5` | Specify which LLM model to use |
| `CLASSIFIER_MODEL` | `CLASSIFIER_MODEL=gpt-4o` | The LLM model to use for scoring the answer (LLM as judge). Supported LLM providers are OpenAI and Azure OpenAI. Defaults to `MODEL` |
| `ITERATIONS` | `ITERATIONS=3` | Run each test multiple times for consistency checking |
| `RUN_LIVE` | `RUN_LIVE=true` | Execute `before-test` and `after-test` commands, ignore mock files |
| `BRAINTRUST_API_KEY` | `BRAINTRUST_API_KEY=sk-1dh1...swdO02` | API key for Braintrust integration |
| `UPLOAD_DATASET` | `UPLOAD_DATASET=true` | Sync dataset to Braintrust (safe, separated by branch) |
| `PUSH_EVALS_TO_BRAINTRUST` | `PUSH_EVALS_TO_BRAINTRUST=true` | Upload evaluation results to Braintrust |
| `EXPERIMENT_ID` | `EXPERIMENT_ID=my_baseline` | Custom experiment name for result tracking |

### Simple Example

Run a comprehensive evaluation:
```bash
export MODEL=gpt-4o

# Run with parallel execution for speed
poetry run pytest -n 10 ./tests/llm/test_*.py --no-cov --disable-warnings
```

### Live Testing

For tests that require actual Kubernetes resources:
```bash
export RUN_LIVE=true

poetry run pytest ./tests/llm/test_ask_holmes.py -k "specific_test" --no-cov --disable-warnings
```

Live testing requires a Kubernetes cluster and will execute `before-test` and `after-test` commands to set up/tear down resources. Not all tests support live testing. Some tests require manual setup.

## Model Comparison Workflow

1. **Create Baseline**: Run evaluations with a reference model
   ```bash
   EXPERIMENT_ID=baseline_gpt4o MODEL=gpt-4o poetry run pytest -n 10 ./tests/llm/test_* --no-cov --disable-warnings
   ```

2. **Test New Model**: Run evaluations with the model you want to compare
   ```bash
   EXPERIMENT_ID=test_claude35 MODEL=anthropic/claude-3.5 poetry run pytest -n 10 ./tests/llm/test_* --no-cov --disable-warnings
   ```

3. **Compare Results**: Use Braintrust dashboard to analyze performance differences

## Writing Evaluations

For detailed information on creating new evaluations, see the [Writing Evaluations Guide](evals-writing.md).

## Reporting and Analysis

Learn how to analyze evaluation results using Braintrust in the [Reporting Guide](evals-reporting.md).

## Troubleshooting

### Common Issues

1. **Missing BRAINTRUST_API_KEY**: Some tests are skipped without this key
2. **Live test failures**: Ensure Kubernetes cluster access and proper permissions
3. **Mock file mismatches**: Regenerate mocks with `generate_mocks: true`
4. **Timeout errors**: Increase test timeout or check network connectivity

### Debug Mode

Enable verbose output:
```bash
poetry run pytest -v -s ./tests/llm/test_ask_holmes.py -k "specific_test" --no-cov --disable-warnings
```

This shows detailed output including:
- Expected vs actual results
- Tool calls made by the LLM
- Evaluation scores and rationales
- Debugging information
