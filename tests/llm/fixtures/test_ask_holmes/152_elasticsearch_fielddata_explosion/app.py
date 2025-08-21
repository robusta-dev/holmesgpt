#!/usr/bin/env python3
import time
import json
import requests
import random
import string
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Set random seed for reproducible behavior
random.seed(152)

ES_URL = "http://elasticsearch:9200"
INDEX_NAME = "application_logs"


def generate_random_text(min_words=5, max_words=20):
    """Generate random text for log messages."""
    words = []
    word_pool = [
        "error",
        "warning",
        "info",
        "debug",
        "service",
        "request",
        "response",
        "user",
        "system",
        "database",
        "cache",
        "memory",
        "cpu",
        "disk",
        "network",
        "timeout",
        "retry",
        "success",
        "failure",
        "processing",
        "completed",
        "started",
        "stopped",
        "initialized",
        "configured",
        "deployed",
        "updated",
    ]

    num_words = random.randint(min_words, max_words)
    for _ in range(num_words):
        if random.random() < 0.7:
            words.append(random.choice(word_pool))
        else:
            # Add some random unique words to increase cardinality
            words.append(
                "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 8)))
            )

    return " ".join(words)


def setup_elasticsearch():
    """Initialize Elasticsearch with problematic mappings."""
    # Wait for Elasticsearch to be ready
    for i in range(30):
        try:
            resp = requests.get(f"{ES_URL}/_cluster/health")
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)

    # Create index with problematic mappings (text fields without keyword)
    index_settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index": {"refresh_interval": "1s"},
        },
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "level": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "service": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "hostname": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "message": {"type": "text"},  # This is fine as text
                "error_code": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "user_agent": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "request_path": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "response_status": {"type": "integer"},
                "duration_ms": {"type": "float"},
                "tags": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "trace_id": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "span_id": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "customer_id": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "region": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
                "environment": {
                    "type": "text",
                    "fielddata": True,
                },  # PROBLEMATIC: Should be keyword
            }
        },
    }

    # Delete index if exists
    requests.delete(f"{ES_URL}/{INDEX_NAME}")

    # Create index
    resp = requests.put(f"{ES_URL}/{INDEX_NAME}", json=index_settings)
    print(f"Index creation response: {resp.status_code}")

    # Generate diverse log data with high cardinality
    print("Generating log data with high cardinality...")
    logs = []
    base_time = datetime.utcnow() - timedelta(hours=24)

    # Generate 10k documents with high cardinality text fields (reduced for testing)
    for i in range(10000):
        log_entry = {
            "timestamp": (
                base_time + timedelta(seconds=random.randint(0, 86400))
            ).isoformat(),
            "level": random.choice(["ERROR", "WARN", "INFO", "DEBUG", "TRACE"]),
            "service": f"service-{random.randint(1, 100)}",
            "hostname": f"host-{random.randint(1, 50)}-{random.choice(['prod', 'staging', 'dev'])}",
            "message": generate_random_text(10, 30),
            "error_code": f"ERR_{random.randint(1000, 9999)}",
            "user_agent": f"Mozilla/5.0 ({random.choice(['Windows', 'Mac', 'Linux'])}) Chrome/{random.randint(90, 120)}.0.{random.randint(1000, 9999)}.{random.randint(10, 99)}",
            "request_path": f"/api/v{random.randint(1, 3)}/{random.choice(['users', 'products', 'orders', 'payments'])}/{random.randint(1, 10000)}/{random.choice(['details', 'list', 'update', 'delete'])}",
            "response_status": random.choice(
                [200, 201, 204, 400, 401, 403, 404, 500, 502, 503]
            ),
            "duration_ms": round(random.uniform(10, 5000), 2),
            "tags": " ".join(
                [f"tag_{random.randint(1, 1000)}" for _ in range(random.randint(1, 5))]
            ),
            "trace_id": f"trace-{''.join(random.choices(string.hexdigits, k=32))}",
            "span_id": f"span-{''.join(random.choices(string.hexdigits, k=16))}",
            "customer_id": f"cust_{random.randint(1, 5000)}",
            "region": random.choice(
                [
                    "us-east-1",
                    "us-west-2",
                    "eu-west-1",
                    "ap-southeast-1",
                    "ap-northeast-1",
                ]
            ),
            "environment": random.choice(
                ["production", "staging", "development", "testing"]
            ),
        }
        logs.append({"index": {"_index": INDEX_NAME}})
        logs.append(log_entry)

        # Bulk index every 1000 documents
        if len(logs) >= 2000:
            bulk_data = "\n".join(json.dumps(log) for log in logs) + "\n"
            resp = requests.post(
                f"{ES_URL}/_bulk",
                headers={"Content-Type": "application/x-ndjson"},
                data=bulk_data,
            )
            logs = []
            if i % 10000 == 0:
                print(f"Indexed {i} documents...")

    # Index remaining documents
    if logs:
        bulk_data = "\n".join(json.dumps(log) for log in logs) + "\n"
        requests.post(
            f"{ES_URL}/_bulk",
            headers={"Content-Type": "application/x-ndjson"},
            data=bulk_data,
        )

    print("Log data generation complete")

    # Force refresh
    requests.post(f"{ES_URL}/{INDEX_NAME}/_refresh")


class SearchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def trigger_fielddata_explosion():
    """Run queries that cause fielddata cache explosion."""
    iteration = 0

    while True:
        try:
            iteration += 1

            # Pattern 1: Terms aggregation on high-cardinality text field
            if random.random() < 0.4:
                # This is the main problem - aggregating on text fields
                query = {
                    "size": 0,
                    "aggs": {
                        "by_service": {
                            "terms": {
                                "field": "service",  # Text field - will load fielddata
                                "size": 100,
                            }
                        },
                        "by_hostname": {
                            "terms": {
                                "field": "hostname",  # Text field - will load fielddata
                                "size": 50,
                            }
                        },
                        "by_error_code": {
                            "terms": {
                                "field": "error_code",  # Text field - will load fielddata
                                "size": 200,
                            }
                        },
                    },
                }

                print(
                    f"Running terms aggregation on text fields (iteration {iteration})"
                )
                start_time = time.time()
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)
                elapsed = time.time() - start_time

                if resp.status_code == 200:
                    print(f"Aggregation completed in {elapsed:.2f}s")
                else:
                    print(f"Aggregation failed: {resp.status_code} - {resp.text[:200]}")

            # Pattern 2: Sorting on text fields
            if random.random() < 0.3:
                # Sorting on text fields also loads fielddata
                query = {
                    "size": 100,
                    "query": {"range": {"timestamp": {"gte": "now-1h"}}},
                    "sort": [
                        {"tags": "asc"},  # Text field - will load fielddata
                        {"trace_id": "desc"},  # Text field - will load fielddata
                    ],
                }

                print("Running sort on text fields")
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

                if resp.status_code != 200:
                    print(f"Sort query failed: {resp.status_code}")

            # Pattern 3: Multiple aggregations on different text fields
            if random.random() < 0.3:
                query = {
                    "size": 0,
                    "aggs": {
                        "by_user_agent": {
                            "terms": {
                                "field": "user_agent",  # High cardinality text field
                                "size": 500,
                            }
                        },
                        "by_request_path": {
                            "terms": {
                                "field": "request_path",  # High cardinality text field
                                "size": 500,
                            }
                        },
                        "by_customer": {
                            "terms": {
                                "field": "customer_id",  # Text field
                                "size": 1000,
                            }
                        },
                        "by_region": {
                            "terms": {
                                "field": "region",  # Text field
                                "size": 20,
                            }
                        },
                    },
                }

                print("Running multiple aggregations on high-cardinality text fields")
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

                if resp.status_code == 500 or "CircuitBreakingException" in resp.text:
                    print("CIRCUIT BREAKER TRIGGERED - Fielddata limit exceeded!")
                elif resp.status_code != 200:
                    print(f"Aggregation failed: {resp.status_code}")

            # Pattern 4: Cardinality aggregation on text field
            if random.random() < 0.2:
                query = {
                    "size": 0,
                    "aggs": {
                        "unique_traces": {
                            "cardinality": {
                                "field": "trace_id"  # Text field with very high cardinality
                            }
                        },
                        "unique_spans": {
                            "cardinality": {
                                "field": "span_id"  # Text field with very high cardinality
                            }
                        },
                    },
                }

                print("Running cardinality aggregation on text fields")
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

            # Check fielddata stats periodically
            if iteration % 5 == 0:
                stats_resp = requests.get(f"{ES_URL}/_stats/fielddata")
                if stats_resp.status_code == 200:
                    stats = stats_resp.json()
                    total = stats.get("_all", {}).get("total", {}).get("fielddata", {})
                    memory_bytes = total.get("memory_size_in_bytes", 0)
                    evictions = total.get("evictions", 0)

                    if memory_bytes > 0:
                        memory_mb = memory_bytes / (1024 * 1024)
                        print(
                            f"Fielddata memory: {memory_mb:.2f}MB, Evictions: {evictions}"
                        )

                        if memory_mb > 50:  # If fielddata is using more than 50MB
                            print("WARNING: High fielddata memory usage detected!")

            # Check for OOM errors
            health_resp = requests.get(f"{ES_URL}/_cluster/health")
            if health_resp.status_code == 200:
                health = health_resp.json()
                if health.get("status") == "red":
                    print("CLUSTER STATUS RED - Possible OOM!")

        except requests.exceptions.ConnectionError:
            print("Connection error - Elasticsearch might have crashed due to OOM!")
            time.sleep(5)
        except Exception as e:
            print(f"Query error: {e}")

        # Small delay between queries
        time.sleep(random.uniform(1, 3))


def monitor_memory_usage():
    """Monitor and log memory statistics."""
    while True:
        try:
            # Get node stats
            stats_resp = requests.get(f"{ES_URL}/_nodes/stats")
            if stats_resp.status_code == 200:
                stats = stats_resp.json()
                for node_id, node_stats in stats.get("nodes", {}).items():
                    heap_used = (
                        node_stats.get("jvm", {})
                        .get("mem", {})
                        .get("heap_used_percent", 0)
                    )
                    heap_used_bytes = (
                        node_stats.get("jvm", {})
                        .get("mem", {})
                        .get("heap_used_in_bytes", 0)
                    )
                    heap_max_bytes = (
                        node_stats.get("jvm", {})
                        .get("mem", {})
                        .get("heap_max_in_bytes", 0)
                    )
                    gc_count = (
                        node_stats.get("jvm", {})
                        .get("gc", {})
                        .get("collectors", {})
                        .get("old", {})
                        .get("collection_count", 0)
                    )

                    fielddata_memory = (
                        node_stats.get("indices", {})
                        .get("fielddata", {})
                        .get("memory_size_in_bytes", 0)
                    )
                    fielddata_evictions = (
                        node_stats.get("indices", {})
                        .get("fielddata", {})
                        .get("evictions", 0)
                    )

                    if heap_used > 75 or fielddata_memory > 10485760:  # 10MB
                        heap_mb = heap_used_bytes / (1024 * 1024)
                        heap_max_mb = heap_max_bytes / (1024 * 1024)
                        fielddata_mb = fielddata_memory / (1024 * 1024)

                        print(
                            f"MEMORY ALERT - Heap: {heap_used}% ({heap_mb:.1f}/{heap_max_mb:.1f}MB), "
                            f"Fielddata: {fielddata_mb:.1f}MB, Evictions: {fielddata_evictions}, "
                            f"Old GC: {gc_count}"
                        )

                    # Check circuit breakers
                    breakers = node_stats.get("breakers", {})
                    fielddata_breaker = breakers.get("fielddata", {})
                    if fielddata_breaker.get("tripped", 0) > 0:
                        print(
                            f"FIELDDATA CIRCUIT BREAKER TRIPPED: {fielddata_breaker.get('tripped')} times"
                        )

            # Get fielddata fields
            fielddata_resp = requests.get(f"{ES_URL}/_stats/fielddata?fields=*")
            if fielddata_resp.status_code == 200:
                fielddata_stats = fielddata_resp.json()
                indices = fielddata_stats.get("indices", {})
                if indices:
                    for index_name, index_stats in indices.items():
                        fields = (
                            index_stats.get("total", {})
                            .get("fielddata", {})
                            .get("fields", {})
                        )
                        if fields:
                            print(f"Fielddata loaded for fields in {index_name}:")
                            for field_name, field_stats in fields.items():
                                size_bytes = field_stats.get("memory_size_in_bytes", 0)
                                if size_bytes > 1048576:  # 1MB
                                    size_mb = size_bytes / (1024 * 1024)
                                    print(f"  - {field_name}: {size_mb:.2f}MB")

        except Exception as e:
            print(f"Monitoring error: {e}")

        time.sleep(5)


def main():
    # Initialize Elasticsearch with problematic mappings
    print("Setting up Elasticsearch with text field mappings...")
    setup_elasticsearch()

    # Start triggering fielddata explosion
    print("Starting fielddata explosion simulation...")
    explosion_thread = threading.Thread(target=trigger_fielddata_explosion, daemon=True)
    explosion_thread.start()

    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_memory_usage, daemon=True)
    monitor_thread.start()

    # Start HTTP server for health checks
    server = HTTPServer(("0.0.0.0", 8080), SearchHandler)
    print("Search service started on port 8080")

    server.serve_forever()


if __name__ == "__main__":
    main()
