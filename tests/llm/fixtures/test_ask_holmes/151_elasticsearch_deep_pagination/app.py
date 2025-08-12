#!/usr/bin/env python3
import time
import json
import requests
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import random

# Set random seed for reproducible behavior
random.seed(151)

ES_URL = "http://elasticsearch:9200"
INDEX_NAME = "analytics_data"


def setup_elasticsearch():
    """Initialize Elasticsearch with test data."""
    # Wait for Elasticsearch to be ready
    for i in range(30):
        try:
            resp = requests.get(f"{ES_URL}/_cluster/health")
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)

    # Create index with proper settings
    index_settings = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 0,
            "index": {"refresh_interval": "1s"},
        },
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "user_id": {"type": "keyword"},
                "event_type": {"type": "keyword"},
                "product_id": {"type": "keyword"},
                "category": {"type": "keyword"},
                "price": {"type": "float"},
                "quantity": {"type": "integer"},
                "session_id": {"type": "keyword"},
                "page_views": {"type": "integer"},
                "duration_seconds": {"type": "integer"},
                "browser": {"type": "keyword"},
                "country": {"type": "keyword"},
                "device_type": {"type": "keyword"},
                "referrer": {"type": "keyword"},
                "search_query": {"type": "text"},
                "click_through": {"type": "boolean"},
            }
        },
    }

    # Delete index if exists
    requests.delete(f"{ES_URL}/{INDEX_NAME}")

    # Create index
    resp = requests.put(f"{ES_URL}/{INDEX_NAME}", json=index_settings)
    print(f"Index creation response: {resp.status_code}")

    # Generate and index sample data
    print("Generating sample data...")
    events = []
    base_time = datetime.utcnow() - timedelta(days=30)

    # Generate 10k documents for realistic pagination scenarios (reduced for testing)
    for i in range(10000):
        event = {
            "timestamp": (
                base_time + timedelta(minutes=random.randint(0, 43200))
            ).isoformat(),
            "user_id": f"user_{random.randint(1, 10000)}",
            "event_type": random.choice(
                ["view", "click", "purchase", "search", "cart_add", "cart_remove"]
            ),
            "product_id": f"prod_{random.randint(1, 5000)}",
            "category": random.choice(
                ["electronics", "clothing", "books", "home", "sports", "toys"]
            ),
            "price": round(random.uniform(10, 1000), 2),
            "quantity": random.randint(1, 5),
            "session_id": f"session_{random.randint(1, 20000)}",
            "page_views": random.randint(1, 50),
            "duration_seconds": random.randint(10, 3600),
            "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
            "country": random.choice(["US", "UK", "DE", "FR", "JP", "CA", "AU"]),
            "device_type": random.choice(["desktop", "mobile", "tablet"]),
            "referrer": random.choice(
                ["google", "facebook", "direct", "email", "twitter"]
            ),
            "search_query": f"search term {random.randint(1, 1000)}",
            "click_through": random.choice([True, False]),
        }
        events.append({"index": {"_index": INDEX_NAME}})
        events.append(event)

        # Bulk index every 1000 documents
        if len(events) >= 2000:
            bulk_data = "\n".join(json.dumps(e) for e in events) + "\n"
            resp = requests.post(
                f"{ES_URL}/_bulk",
                headers={"Content-Type": "application/x-ndjson"},
                data=bulk_data,
            )
            events = []
            if i % 10000 == 0:
                print(f"Indexed {i} documents...")

    # Index remaining documents
    if events:
        bulk_data = "\n".join(json.dumps(e) for e in events) + "\n"
        requests.post(
            f"{ES_URL}/_bulk",
            headers={"Content-Type": "application/x-ndjson"},
            data=bulk_data,
        )

    print("Sample data generation complete")

    # Force refresh
    requests.post(f"{ES_URL}/{INDEX_NAME}/_refresh")


class AnalyticsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        elif self.path.startswith("/export"):
            # Simulate data export with deep pagination
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "export_running"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def simulate_deep_pagination_queries():
    """Continuously run deep pagination queries that cause high CPU."""
    page_size = 100
    current_offset = 0

    while True:
        try:
            # Simulate different types of problematic deep pagination patterns

            # Pattern 1: Sequential deep pagination for data export
            if random.random() < 0.3:
                # This is the problematic pattern - going deep into results
                offset = random.randint(5000, 9000)
                query = {
                    "from": offset,
                    "size": page_size,
                    "query": {"range": {"timestamp": {"gte": "now-30d", "lte": "now"}}},
                    "sort": [{"timestamp": "desc"}, {"_id": "desc"}],
                }

                print(
                    f"Running deep pagination query with from={offset}, size={page_size}"
                )
                start_time = time.time()
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)
                elapsed = time.time() - start_time

                if resp.status_code == 200:
                    result = resp.json()
                    hits = result.get("hits", {}).get("total", {}).get("value", 0)
                    took = result.get("took", 0)
                    print(
                        f"Query completed: from={offset}, took={took}ms, elapsed={elapsed:.2f}s, total_hits={hits}"
                    )
                else:
                    print(f"Query failed: {resp.status_code}")

            # Pattern 2: User browsing with large page numbers
            if random.random() < 0.4:
                # Simulate user clicking "next page" many times
                page_number = random.randint(100, 500)
                offset = page_number * page_size

                query = {
                    "from": offset,
                    "size": page_size,
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "term": {
                                        "category": random.choice(
                                            ["electronics", "clothing", "books"]
                                        )
                                    }
                                },
                                {"range": {"price": {"gte": 50, "lte": 500}}},
                            ]
                        }
                    },
                    "sort": [{"price": "asc"}],
                    "aggs": {
                        "price_stats": {"stats": {"field": "price"}},
                        "top_products": {"terms": {"field": "product_id", "size": 10}},
                    },
                }

                print(
                    f"Running pagination query for page {page_number} (from={offset})"
                )
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

                if resp.status_code == 200:
                    result = resp.json()
                    took = result.get("took", 0)
                    print(f"Page {page_number} query took {took}ms")

            # Pattern 3: Batch export with very deep pagination
            if random.random() < 0.2:
                # Simulate batch job trying to export all data
                current_offset += page_size
                if current_offset > 9000:
                    current_offset = 0

                query = {
                    "from": current_offset,
                    "size": page_size,
                    "query": {"match_all": {}},
                    "sort": [{"_id": "asc"}],
                }

                print(f"Batch export query: from={current_offset}")
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

                if resp.status_code == 200:
                    result = resp.json()
                    took = result.get("took", 0)
                    if took > 1000:
                        print(
                            f"SLOW QUERY DETECTED: from={current_offset}, took={took}ms"
                        )

            # Pattern 4: Complex aggregation with deep pagination
            if random.random() < 0.1:
                offset = random.randint(5000, 20000)
                query = {
                    "from": offset,
                    "size": 50,
                    "query": {
                        "bool": {
                            "must": [
                                {"range": {"timestamp": {"gte": "now-7d"}}},
                                {"terms": {"event_type": ["purchase", "cart_add"]}},
                            ]
                        }
                    },
                    "aggs": {
                        "by_category": {
                            "terms": {"field": "category", "size": 100},
                            "aggs": {
                                "revenue": {"sum": {"field": "price"}},
                                "avg_quantity": {"avg": {"field": "quantity"}},
                            },
                        },
                        "by_country": {"terms": {"field": "country", "size": 50}},
                    },
                    "sort": [{"price": "desc"}, {"timestamp": "desc"}],
                }

                print(f"Complex aggregation with from={offset}")
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)

            # Add some normal queries for contrast
            if random.random() < 0.3:
                # Normal query without deep pagination
                query = {
                    "from": 0,
                    "size": 20,
                    "query": {"term": {"user_id": f"user_{random.randint(1, 10000)}"}},
                }
                resp = requests.post(f"{ES_URL}/{INDEX_NAME}/_search", json=query)
                print("Normal query executed (from=0)")

        except Exception as e:
            print(f"Query error: {e}")

        # Small delay between queries
        time.sleep(random.uniform(0.5, 2))


def monitor_elasticsearch_stats():
    """Monitor and log Elasticsearch statistics."""
    while True:
        try:
            # Get node stats
            stats_resp = requests.get(f"{ES_URL}/_nodes/stats")
            if stats_resp.status_code == 200:
                stats = stats_resp.json()
                for node_id, node_stats in stats.get("nodes", {}).items():
                    cpu_percent = (
                        node_stats.get("os", {}).get("cpu", {}).get("percent", 0)
                    )
                    heap_used = (
                        node_stats.get("jvm", {})
                        .get("mem", {})
                        .get("heap_used_percent", 0)
                    )
                    search_queue = (
                        node_stats.get("thread_pool", {})
                        .get("search", {})
                        .get("queue", 0)
                    )
                    search_rejected = (
                        node_stats.get("thread_pool", {})
                        .get("search", {})
                        .get("rejected", 0)
                    )

                    if cpu_percent > 70 or heap_used > 80 or search_rejected > 0:
                        print(
                            f"ES Stats - CPU: {cpu_percent}%, Heap: {heap_used}%, Search Queue: {search_queue}, Rejected: {search_rejected}"
                        )

            # Get slow queries
            requests.get(
                f"{ES_URL}/{INDEX_NAME}/_search",
                json={"query": {"match_all": {}}, "profile": True, "size": 0},
            )

            # Get hot threads if CPU is high
            hot_threads_resp = requests.get(f"{ES_URL}/_nodes/hot_threads")
            if (
                hot_threads_resp.status_code == 200
                and "search" in hot_threads_resp.text.lower()
            ):
                print("Hot threads detected in search thread pool")

        except Exception as e:
            print(f"Stats monitoring error: {e}")

        time.sleep(10)


def main():
    # Initialize Elasticsearch with data
    print("Setting up Elasticsearch...")
    setup_elasticsearch()

    # Start the problematic deep pagination queries
    print("Starting deep pagination simulation...")
    pagination_thread = threading.Thread(
        target=simulate_deep_pagination_queries, daemon=True
    )
    pagination_thread.start()

    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_elasticsearch_stats, daemon=True)
    monitor_thread.start()

    # Start HTTP server for health checks
    server = HTTPServer(("0.0.0.0", 8080), AnalyticsHandler)
    print("Analytics API started on port 8080")

    server.serve_forever()


if __name__ == "__main__":
    main()
