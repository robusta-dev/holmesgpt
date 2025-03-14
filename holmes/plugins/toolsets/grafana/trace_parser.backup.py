from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import base64

@dataclass
class Span:
    span_id: str
    parent_span_id: Optional[str]
    name: str
    service_name: str
    start_time: int
    end_time: int
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    children: List['Span'] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Calculate duration in milliseconds"""
        return (self.end_time - self.start_time) / 1_000_000  # Convert nanoseconds to milliseconds

def decode_id(encoded_id: str) -> str:
    """Decode base64 IDs to a hex string for easier reading"""
    return base64.b64decode(encoded_id).hex()

def build_span_hierarchy(trace_data: Dict) -> List[Span]:
    # Step 1: Extract all spans and create span objects
    all_spans = {}

    for batch in trace_data["batches"]:
        # Extract service name from resource attributes
        service_name = "unknown"
        for attr in batch["resource"]["attributes"]:
            if attr["key"] == "service.name":
                service_name = attr["value"]["stringValue"]
                break

        for scope_spans in batch["scopeSpans"]:
            for span_data in scope_spans["spans"]:
                span_id = decode_id(span_data["spanId"])

                # Get parent span ID if it exists
                parent_span_id = None
                if "parentSpanId" in span_data:
                    parent_span_id = decode_id(span_data["parentSpanId"])

                # Create a Span object
                span = Span(
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    name=span_data["name"],
                    service_name=service_name,
                    start_time=int(span_data["startTimeUnixNano"]),
                    end_time=int(span_data["endTimeUnixNano"]),
                    attributes={attr["key"]: list(attr["value"].values())[0]
                                for attr in span_data.get("attributes", [])},
                    events=span_data.get("events", [])
                )

                all_spans[span_id] = span

    # Step 2: Build the hierarchy by connecting parents and children
    root_spans = []

    for span in all_spans.values():
        if span.parent_span_id is None:
            # This is a root span
            root_spans.append(span)
        else:
            # Add this span as a child to its parent
            if span.parent_span_id in all_spans:
                all_spans[span.parent_span_id].children.append(span)

    return root_spans

def print_span_tree(span: Span, level: int = 0):
    """Print the span hierarchy in a tree format"""
    indent = "  " * level
    duration = span.duration_ms
    print(f"{indent}├─ {span.name} ({span.service_name}) - {duration:.2f}ms")

    # Print attributes
    if span.attributes:
        print(f"{indent}│  Attributes:")
        for key, value in span.attributes.items():
            print(f"{indent}│    {key}: {value}")

    # Print events
    if span.events:
        print(f"{indent}│  Events:")
        for event in span.events:
            event_name = event["name"]
            event_time = int(event["timeUnixNano"])
            relative_time = (event_time - span.start_time) / 1_000_000
            print(f"{indent}│    {event_name} (+{relative_time:.2f}ms)")

    # Print children
    for child in sorted(span.children, key=lambda s: s.start_time):
        print_span_tree(child, level + 1)

def process_trace(trace_data):
    root_spans = build_span_hierarchy(trace_data)

    # Print the trace tree
    print("Trace Hierarchy:")
    for root_span in sorted(root_spans, key=lambda s: s.start_time):
        print_span_tree(root_span)

    return root_spans
