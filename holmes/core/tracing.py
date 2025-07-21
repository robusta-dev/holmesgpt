import os
import logging
from typing import Optional, Any, Union
from contextlib import contextmanager

try:
    import braintrust
    from braintrust import Span

    BRAINTRUST_AVAILABLE = True
except ImportError:
    BRAINTRUST_AVAILABLE = False
    # Type alias for when braintrust is not available
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from braintrust import Span
    else:
        Span = Any


class DummySpan:
    """A no-op span implementation for when tracing is disabled."""

    def start_span(self, *args, **kwargs):
        return self

    def log(self, *args, **kwargs):
        pass

    def end(self):
        pass

    def get_trace_url(self):
        return None

    def investigation_span(self, prompt: str):
        """Context manager for investigation spans."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class BraintrustTracer:
    """Braintrust implementation of tracing."""

    def __init__(self, project: str = "HolmesGPT-CLI", experiment=None):
        if not BRAINTRUST_AVAILABLE:
            raise ImportError("braintrust package is required for BraintrustTracer")

        self.project = project
        self.experiment = experiment
        self.root_span: Optional[Union[Span, DummySpan]] = None

        # If no experiment provided, we'll create one when needed
        if not experiment and os.environ.get("BRAINTRUST_API_KEY"):
            self._should_create_experiment = True
        else:
            self._should_create_experiment = False

    def _start_investigation_span(
        self, prompt: str, **kwargs
    ) -> Union[Span, DummySpan]:
        """Start a root investigation span."""
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return DummySpan()

        # Check if we're already in a Braintrust context (like tests)
        current_span = braintrust.current_span()

        # Check if current_span is a real span (not NoopSpan)
        is_real_span = current_span and not str(type(current_span)).endswith(
            "_NoopSpan'>"
        )

        if is_real_span:
            # We're in a test context - create child span
            self.root_span = current_span.start_span(name="holmes-ask", **kwargs)
            return self.root_span
        else:
            # CLI context - create experiment if needed and root span
            if not self.experiment and self._should_create_experiment:
                self.experiment = braintrust.init(
                    project=self.project, open=False, metadata={"prompt": prompt}
                )

            if self.experiment:
                # Create a new root span for each question (Option 1)
                self.root_span = self.experiment.start_span(name="holmes-ask", **kwargs)
                return self.root_span
            else:
                return DummySpan()

    def start_span(self, name: str, **kwargs) -> Union[Span, DummySpan]:
        """Start a child span."""
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return DummySpan()

        if self.root_span:
            return self.root_span.start_span(name=name, **kwargs)
        else:
            # Fallback to current span if available
            current_span = braintrust.current_span()
            if current_span:
                return current_span.start_span(name=name, **kwargs)

        return DummySpan()

    def get_trace_url(self) -> Optional[str]:
        """Get URL to view the trace in Braintrust."""
        if self.experiment:
            experiment_name = getattr(self.experiment, "name", None)
            experiment_id = getattr(self.experiment, "id", None)

            # Construct URL with proper format: experiments/{name}?c=&tg=false&r={span.id}&s={span_id}
            if experiment_name and self.root_span:
                span_id = getattr(self.root_span, "span_id", None)
                id_attr = getattr(self.root_span, "id", None)

                if span_id and id_attr:
                    return f"https://www.braintrust.dev/app/robustadev/p/{self.project}/experiments/{experiment_name}?c=&tg=false&r={id_attr}&s={span_id}"

            # Fallback to simple construction
            if experiment_id:
                return f"https://www.braintrust.dev/app/robustadev/p/{self.project}/experiments/{experiment_id}"

        return None

    @contextmanager
    def investigation_span(self, prompt: str):
        """Context manager for investigation spans."""
        span = self._start_investigation_span(prompt)
        try:
            yield span
        finally:
            span.end()


class TracingFactory:
    """Factory for creating tracer instances."""

    @staticmethod
    def create_tracer(trace_type: Optional[str], context: str = "cli"):
        """Create a tracer instance based on the trace type.

        Args:
            trace_type: Type of tracing ('braintrust', etc.)
            context: Context ('cli', 'test') - affects project naming

        Returns:
            Tracer instance if tracing enabled, DummySpan if disabled
        """
        if not trace_type:
            return DummySpan()

        if trace_type.lower() == "braintrust":
            if not BRAINTRUST_AVAILABLE:
                logging.warning(
                    "Braintrust tracing requested but braintrust package not available"
                )
                return DummySpan()

            if not os.environ.get("BRAINTRUST_API_KEY"):
                logging.warning(
                    "Braintrust tracing requested but BRAINTRUST_API_KEY not set"
                )
                return DummySpan()

            # Use different project names for different contexts
            project = "HolmesGPT-CLI" if context == "cli" else "HolmesGPT"
            return BraintrustTracer(project=project)

        logging.warning(f"Unknown trace type: {trace_type}")
        return DummySpan()


def log_llm_call(span, messages, full_response, tools=None, tool_choice=None):
    """Log an LLM call with its inputs and outputs to a span.

    Args:
        span: The span to log to (can be DummySpan)
        messages: Input messages to the LLM
        full_response: LLM response object
        tools: Available tools (for metadata)
        tool_choice: Tool choice setting (for metadata)
    """
    if isinstance(span, DummySpan):
        return

    # Extract response content safely
    response_content = ""
    try:
        if hasattr(full_response, "choices") and full_response.choices:
            choice = full_response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                response_content = choice.message.content or ""
    except (AttributeError, IndexError):
        response_content = ""

    # Build metadata
    metadata = {
        "model": getattr(full_response, "model", None),
        "usage": getattr(full_response, "usage", None),
    }

    if tools is not None:
        metadata["tools_available"] = len(tools)
    if tool_choice is not None:
        metadata["tool_choice"] = tool_choice

    # Log to span
    span.log(
        input=messages,
        output=response_content,
        metadata=metadata,
    )
