import json
from typing import Any, Optional, Set, Union, Sequence

from pydantic import BaseModel

from holmes.plugins.toolsets.prometheus.model import PromSeries


class CompressedMetric(BaseModel):
    labels: set[tuple[str, Any]]
    values: list[list[Any]]


class Group(BaseModel):
    common_labels: set[tuple[str, Any]]
    metrics: Sequence[Union["Group", CompressedMetric]]


INDENT_SPACES = "  "


def format_labels(
    labels: set[tuple[str, Any]], section_name: str, line_prefix: str = ""
) -> list[str]:
    lines = []
    if labels:
        sorted_labels = sorted(
            labels, key=lambda t: t[0]
        )  # keep label list stable in the outpout by sorting them by key
        if len(sorted_labels) <= 10:
            labels_dict = {}
            for k, v in sorted_labels:
                labels_dict[k] = v
            lines.append(f"{line_prefix}{section_name} {json.dumps(labels_dict)}")
        else:
            lines.append(line_prefix + section_name)
            for k, v in sorted_labels:
                lines.append(f"{line_prefix}{INDENT_SPACES}- {str(k)}: {str(v)}")
    else:
        raise Exception("No label")
    return lines


def format_data(data: Union[Group, CompressedMetric], line_prefix: str = "") -> str:
    lines = []
    if isinstance(data, CompressedMetric):
        if data.labels:
            lines.extend(format_labels(labels=data.labels, section_name="labels:"))
        if data.values:
            lines.append("values:")
            for value in data.values:
                lines.append(f"{INDENT_SPACES}- {str(value[0])}: {str(value[1])}")
        else:
            lines.append("values: NO_VALUES")
        txt = "\n".join([line_prefix + line for line in lines])
        return txt

    elif data.metrics:
        if not data.common_labels:
            raise ValueError(
                f"Group has no labels: labels={data.common_labels} metrics={len(data.metrics)}"
            )
        group_labels = format_labels(
            labels=data.common_labels,
            section_name="common_labels:",
            line_prefix=line_prefix,
        )
        lines.extend(group_labels)
        lines.append(f"{line_prefix}metrics:")

        for metric in data.metrics:
            metric_lines = format_data(
                data=metric, line_prefix=line_prefix + (INDENT_SPACES * 2)
            )
            if metric_lines:
                metric_lines = f"{line_prefix}{INDENT_SPACES}- " + metric_lines.lstrip()
                lines.append(metric_lines)
        return "\n".join([line for line in lines])
    return ""


def format_zero_values_data(
    data: Union[Group, CompressedMetric], line_prefix: str = ""
) -> str:
    lines = []
    if isinstance(data, CompressedMetric):
        if data.labels:
            lines.extend(format_labels(labels=data.labels, section_name=""))
        txt = "\n".join([line_prefix + line for line in lines])
        return txt

    elif isinstance(data, Group):
        lines.extend(
            format_labels(
                labels=data.common_labels, section_name="", line_prefix=line_prefix
            )
        )

        compress_labels = True
        compressed_label_values: list = []
        compress_key: Optional[str] = None
        # close to the leaves the data may be a high number of metrics differentiated by a single label
        # Check if it's the case.
        for metric in data.metrics:
            if isinstance(metric, CompressedMetric) and len(metric.labels) == 1:
                key, value = next(iter(metric.labels))
                if not compress_key:
                    compress_key = key
                elif key != compress_key:
                    compress_labels = False
                    break
                compressed_label_values.append(value)
            else:
                compress_labels = False
                break
        if compress_labels and compress_key:
            lines.append(
                f"{line_prefix}{INDENT_SPACES}- {json.dumps({compress_key:compressed_label_values})}"
            )
        else:
            for metric in data.metrics:
                metric_lines = format_zero_values_data(
                    data=metric, line_prefix=line_prefix + (INDENT_SPACES * 2)
                )
                if metric_lines:
                    metric_lines = (
                        f"{line_prefix}{INDENT_SPACES}- " + metric_lines.lstrip()
                    )
                    lines.append(metric_lines)
        txt = "\n".join([line for line in lines])
        return txt


def format_zero_values_metrics(metrics: list[Union[Group, CompressedMetric]]) -> str:
    formatted_string = "# Metrics with the following hierarchised labels have all values set to ZERO:\n"
    for metric in metrics:
        formatted_string += (
            format_zero_values_data(metric, line_prefix=INDENT_SPACES) + "\n"
        )

    return formatted_string


def format_compressed_metrics(metrics: list[Union[Group, CompressedMetric]]) -> str:
    formatted_string = (
        "# The following metrics have been hierarchically grouped by labels:\n"
    )
    for metric in metrics:
        d = format_data(metric, line_prefix=INDENT_SPACES)
        formatted_string += d + "\n"

    return formatted_string


def simplify_prometheus_metric_object(
    raw_metric: PromSeries, labels_to_remove: set[tuple[str, Any]]
) -> CompressedMetric:
    labels: set[tuple[str, Any]] = set()
    if labels_to_remove:
        for label in raw_metric.metric.items():
            if label not in labels_to_remove:
                labels.add(label)
    else:
        labels = set(raw_metric.metric.items())
    return CompressedMetric(labels=labels, values=raw_metric.values)


def remove_labels(
    metric: CompressedMetric, labels_to_remove: set[tuple[str, Any]]
) -> None:
    labels: set[tuple[str, Any]] = set()
    for label in metric.labels:
        if label not in labels_to_remove:
            labels.add(label)
    metric.labels = labels


class PreFilteredMetrics(BaseModel):
    metrics_with_only_zero_values: list[CompressedMetric]
    other_metrics: list[CompressedMetric]


def pre_filter_metrics(metrics: list[CompressedMetric]) -> PreFilteredMetrics:
    """A prefilter before metrics are merged together.
    It helps for high cardinality when a lot of metrics have 0 as values.
    These metrics are grouped and then summarized as zero values
    """
    metrics_with_only_zero_values: list[CompressedMetric] = []
    other_metrics: list[CompressedMetric] = []
    for metric in metrics:
        metric_has_non_zero_value = False
        for value in metric.values:
            if value[1] != "0" and value[1] != 0:
                other_metrics.append(metric)
                metric_has_non_zero_value = True
                break
        if not metric_has_non_zero_value:
            metrics_with_only_zero_values.append(metric)

    return PreFilteredMetrics(
        metrics_with_only_zero_values=metrics_with_only_zero_values,
        other_metrics=other_metrics,
    )


def group_metrics(
    metrics_to_process: list[CompressedMetric],
    globally_common_labels: Optional[set[tuple[str, Any]]] = None,
) -> list[Union[Group, CompressedMetric]]:
    if not globally_common_labels:
        globally_common_labels = set()
    most_common_label, match_count = find_most_common_label(
        metrics=metrics_to_process, ignore_label_set=set()
    )
    if not globally_common_labels:
        while most_common_label and match_count == len(metrics_to_process):
            globally_common_labels.add(most_common_label)
            most_common_label, match_count = find_most_common_label(
                metrics=metrics_to_process, ignore_label_set=globally_common_labels
            )

    groups: list[Union[Group, CompressedMetric]] = []
    unmatched_metrics: list[CompressedMetric] = []
    # Constantly iterate over all metrics trying to extract the most common label
    # Once we find a common label that matches more than one metric, we try to find other common labels between these metrics
    # We group the metrics together once we don't find any more common metrics
    if not most_common_label or match_count <= 1:
        unmatched_metrics = metrics_to_process
    else:
        while most_common_label and match_count > 1:
            current_group_labels = set()
            current_group: list[CompressedMetric] = []
            current_group_labels.add(most_common_label)
            unmatched_metrics = []
            for metric_data in metrics_to_process:
                if most_common_label in metric_data.labels:
                    current_group.append(metric_data)
                else:
                    unmatched_metrics.append(metric_data)

            all_group_labels = current_group_labels.union(globally_common_labels)
            most_common_label, match_count = find_most_common_label(
                metrics=current_group, ignore_label_set=all_group_labels
            )

            # Keep aggregating all labels that are common with the current group.
            while match_count == len(current_group) and most_common_label is not None:
                current_group_labels.add(most_common_label)
                all_group_labels = current_group_labels.union(globally_common_labels)
                most_common_label, match_count = find_most_common_label(
                    metrics=current_group, ignore_label_set=all_group_labels
                )

            # We're done with our group as we found no more common labels.
            # 1. Remove the common labels from all metrics in this group
            # 2. Recurse to further group metrics within this group
            for metric_in_group in current_group:
                all_group_labels = current_group_labels.union(globally_common_labels)
                remove_labels(metric=metric_in_group, labels_to_remove=all_group_labels)

            groups.append(
                Group(common_labels=current_group_labels, metrics=current_group)
            )

            most_common_label, match_count = find_most_common_label(
                metrics=unmatched_metrics, ignore_label_set=globally_common_labels
            )
            metrics_to_process = unmatched_metrics

    for metric in unmatched_metrics:
        remove_labels(metric=metric, labels_to_remove=globally_common_labels)
        # prepend instead of append so that unique metrics are closer to common labels than grouped metrics
        # I 'guess' it may help the LLM in making sense of the hierarchy
        groups.insert(0, metric)

    if globally_common_labels and len(groups) > 1:
        parent_group = Group(common_labels=globally_common_labels, metrics=groups)
        return [parent_group]
    else:
        return groups


def compact_metrics(metrics_to_process: list[CompressedMetric]) -> str:
    summarized_text = ""
    filtered_metrics = pre_filter_metrics(metrics=metrics_to_process)
    if len(filtered_metrics.metrics_with_only_zero_values):
        zero_metrics = group_metrics(filtered_metrics.metrics_with_only_zero_values)
        summarized_text += format_zero_values_metrics(zero_metrics)

    if summarized_text and filtered_metrics.other_metrics:
        summarized_text += "\n"

    if filtered_metrics.other_metrics:
        metrics = group_metrics(metrics_to_process=filtered_metrics.other_metrics)
        summarized_text += format_compressed_metrics(metrics)

    return summarized_text


def find_most_common_label(
    metrics: list[CompressedMetric], ignore_label_set: Set[tuple[str, Any]]
) -> tuple[Optional[tuple[str, Any]], int]:
    """
    Find the most common label key/value across all metrics.

    Args:
        metrics: List of metrics
        ignore_label_set: labels to ignore (e.g. they are already known to be common across all metrics)

    Returns:
        The most common label and its occurence count across all metrics: ((key, value), count)
    """
    if len(metrics) <= 1:
        return None, 0

    # Count frequency of each (key, value) pair
    label_counts: dict[tuple[str, Any], int] = {}

    # First, collect all (key, value) pairs and their counts
    for metric_data in metrics:
        labels = metric_data.labels
        for key, value in labels:
            if (key, value) not in ignore_label_set:
                label_key = (key, value)
                label_counts[label_key] = label_counts.get(label_key, 0) + 1

    # Find the label that is the most frequent
    most_common_label: Optional[tuple[str, Any]] = None
    most_common_count_value = 0
    for (key, value), count in label_counts.items():
        if not most_common_label and count > 1:
            most_common_label = (key, value)
            most_common_count_value = count
        elif count > 1 and count > most_common_count_value:
            most_common_label = (key, value)
            most_common_count_value = count

    return most_common_label, most_common_count_value
