import os
import logging
from typing import Optional, Any, Dict, List, Union
from abc import ABC, abstractmethod

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

    def start_investigation_span(self, *args, **kwargs):
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


class InvestigationSpanContext:
    """Context manager for investigation spans that ensures proper cleanup."""

    def __init__(self, tracer: "BraintrustTracer", prompt: str):
        self.tracer = tracer
        self.prompt = prompt
        self.span = None

    def __enter__(self):
        self.span = self.tracer.start_investigation_span(self.prompt)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            self.span.end()


class BaseTracer(ABC):
    """Abstract base class for tracing implementations."""

    @abstractmethod
    def start_investigation_span(self, prompt: str, **kwargs) -> Union[Span, DummySpan]:
        """Start a root span for an investigation."""
        pass

    @abstractmethod
    def start_span(self, name: str, **kwargs) -> Union[Span, DummySpan]:
        """Start a child span."""
        pass

    @abstractmethod
    def log_llm_call(
        self,
        span: Union[Span, DummySpan],
        messages: List[Dict],
        response: Any,
        tool_calls: Optional[List] = None,
    ):
        """Log an LLM call with its inputs and outputs."""
        pass

    @abstractmethod
    def get_trace_url(self) -> Optional[str]:
        """Get the URL to view the trace."""
        pass


class BraintrustTracer(BaseTracer):
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

    def start_investigation_span(self, prompt: str, **kwargs) -> Union[Span, DummySpan]:
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

    def log_llm_call(
        self,
        span: Union[Span, DummySpan],
        messages: List[Dict],
        response: Any,
        tool_calls: Optional[List] = None,
    ):
        """Log an LLM call."""
        if isinstance(span, DummySpan):
            return

        # Extract relevant information from response
        try:
            response_content = ""
            if hasattr(response, "choices") and response.choices:
                response_content = response.choices[0].message.content or ""
            elif isinstance(response, str):
                response_content = response

            metadata_dict = {
                "model": getattr(response, "model", None),
                "usage": getattr(response, "usage", None),
                "tool_calls_count": len(tool_calls) if tool_calls else 0,
            }

            if tool_calls:
                tool_calls_list = [
                    {
                        "name": getattr(tc, "function", {}).get("name", "unknown"),
                        "description": getattr(tc, "description", ""),
                    }
                    for tc in tool_calls
                ]
                metadata_dict["tool_calls"] = tool_calls_list

            log_data = {
                "input": messages,
                "output": response_content,
                "metadata": metadata_dict,
            }

            span.log(**log_data)
        except Exception as e:
            logging.warning(f"Failed to log LLM call to trace: {e}")

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

    def investigation_span(self, prompt: str):
        """Context manager for investigation spans."""
        return InvestigationSpanContext(self, prompt)


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
