import os
import logging
from typing import Optional, Any, Union
from contextlib import contextmanager
from enum import Enum

try:
    import braintrust
    from braintrust import Span, SpanTypeAttribute

    BRAINTRUST_AVAILABLE = True
except ImportError:
    BRAINTRUST_AVAILABLE = False
    # Type aliases for when braintrust is not available
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from braintrust import Span, SpanTypeAttribute
    else:
        Span = Any
        SpanTypeAttribute = Any


class SpanType(Enum):
    """Standard span types for tracing categorization."""

    LLM = "llm"
    TOOL = "tool"
    TASK = "task"
    SCORE = "score"


class DummySpan:
    """A no-op span implementation for when tracing is disabled."""

    def start_span(self, name: str, span_type: Optional[SpanType] = None, **kwargs):
        return DummySpan()

    def log(self, *args, **kwargs):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class DummyTracer:
    """A no-op tracer implementation for when tracing is disabled."""

    @contextmanager
    def start_trace(self, prompt: str):
        """Context manager for starting a trace."""
        yield DummySpan()

    def get_trace_url(self):
        return None

    def wrap_llm(self, llm_module):
        """No-op LLM wrapping for dummy tracer."""
        return llm_module


class BraintrustTracer:
    """Braintrust implementation of tracing."""

    def __init__(self, project: str = "HolmesGPT-CLI"):
        if not BRAINTRUST_AVAILABLE:
            raise ImportError("braintrust package is required for BraintrustTracer")

        self.project = project

    def start_experiment(
        self, experiment_name: Optional[str] = None, metadata: Optional[dict] = None
    ):
        """Create and start a new Braintrust experiment.

        Args:
            experiment_name: Name for the experiment, auto-generated if None
            metadata: Metadata to attach to experiment

        Returns:
            Braintrust experiment object
        """
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return None

        return braintrust.init(
            project=self.project,
            experiment=experiment_name,
            metadata=metadata or {},
            open=False,
        )

    def start_trace(
        self, name: str, span_type: Optional[SpanType] = None
    ) -> Union[Span, DummySpan]:
        """Start a trace span in current Braintrust context.

        Args:
            name: Span name
            span_type: Type of span for categorization

        Returns:
            Span that can be used as context manager
        """
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return DummySpan()

        # Add span type to kwargs if provided
        kwargs = {}
        if span_type:
            kwargs["type"] = getattr(SpanTypeAttribute, span_type.name)

        # Use current Braintrust context (experiment or parent span)
        current_span = braintrust.current_span()
        if current_span and not str(type(current_span)).endswith("_NoopSpan'>"):
            return current_span.start_span(name=name, **kwargs)

        # Fallback to current experiment
        current_experiment = braintrust.current_experiment()
        if current_experiment:
            return current_experiment.start_span(name=name, **kwargs)

        return DummySpan()

    def start_span(
        self, name: str, span_type: Optional[SpanType] = None, **kwargs
    ) -> Union[Span, DummySpan]:
        """Start a child span."""
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return DummySpan()

        if span_type:
            kwargs["type"] = getattr(SpanTypeAttribute, span_type.name)

        # Use current span if available
        current_span = braintrust.current_span()
        if current_span and not str(type(current_span)).endswith("_NoopSpan'>"):
            return current_span.start_span(name=name, **kwargs)

        # Fallback to current experiment
        current_experiment = braintrust.current_experiment()
        if current_experiment:
            return current_experiment.start_span(name=name, **kwargs)

        return DummySpan()

    def get_trace_url(self) -> Optional[str]:
        """Get URL to view the trace in Braintrust."""
        if not os.environ.get("BRAINTRUST_API_KEY"):
            return None

        # Get current experiment from Braintrust context
        current_experiment = braintrust.current_experiment()
        if current_experiment:
            experiment_name = getattr(current_experiment, "name", None)

            # Get current span for detailed URL construction
            current_span = braintrust.current_span()

            # Use experiment name for URL construction
            if experiment_name:
                if current_span and not str(type(current_span)).endswith("_NoopSpan'>"):
                    span_id = getattr(current_span, "span_id", None)
                    id_attr = getattr(current_span, "id", None)
                    if span_id and id_attr:
                        return f"https://www.braintrust.dev/app/robustadev/p/{self.project}/experiments/{experiment_name}?c=&tg=false&r={id_attr}&s={span_id}"
                # Fallback to experiment name only
                return f"https://www.braintrust.dev/app/robustadev/p/{self.project}/experiments/{experiment_name}"

        return None

    def wrap_llm(self, llm_module):
        """Wrap LiteLLM using Braintrust's internal ChatCompletionWrapper for proper tracing."""
        if not BRAINTRUST_AVAILABLE:
            return llm_module

        try:
            from braintrust.oai import ChatCompletionWrapper

            # Create a wrapper that ensures LLM calls are child spans of our investigation span
            class WrappedLiteLLM:
                def __init__(self, original_module, tracer):
                    self._original_module = original_module
                    self._tracer = tracer
                    # Create the ChatCompletionWrapper for the original completion function
                    self._chat_wrapper = ChatCompletionWrapper(
                        create_fn=original_module.completion,
                        acreate_fn=None,  # LiteLLM async not structured the same way
                    )

                def completion(self, **kwargs):
                    # For existing context (evals), the ChatCompletionWrapper should automatically
                    # detect the current Braintrust span and create child spans
                    # For new context (holmes ask), we use our start_trace context manager
                    return self._chat_wrapper.create(**kwargs)

                def __getattr__(self, name):
                    # Delegate all other attributes to the original module
                    return getattr(self._original_module, name)

            return WrappedLiteLLM(llm_module, self)

        except ImportError:
            logging.warning(
                "Could not import Braintrust ChatCompletionWrapper, falling back to no tracing"
            )
            return llm_module


class TracingFactory:
    """Factory for creating tracer instances."""

    @staticmethod
    def create_tracer(trace_type: Optional[str], project: str):
        """Create a tracer instance based on the trace type.

        Args:
            trace_type: Type of tracing ('braintrust', etc.)
            project: Project name for tracing

        Returns:
            Tracer instance if tracing enabled, DummySpan if disabled
        """
        if not trace_type:
            return DummyTracer()

        if trace_type.lower() == "braintrust":
            if not BRAINTRUST_AVAILABLE:
                logging.warning(
                    "Braintrust tracing requested but braintrust package not available"
                )
                return DummyTracer()

            if not os.environ.get("BRAINTRUST_API_KEY"):
                logging.warning(
                    "Braintrust tracing requested but BRAINTRUST_API_KEY not set"
                )
                return DummyTracer()

            return BraintrustTracer(project=project)

        logging.warning(f"Unknown trace type: {trace_type}")
        return DummyTracer()
