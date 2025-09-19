

import json
import logging
import shlex
from sys import exc_info
from typing import Any, List, Dict, Optional, Set, Union

from click import group
from numpy import isin
from pydantic import BaseModel
import yaml

class RawMetric(BaseModel):
    metric: dict[str, Any] # labels
    values: list[list[Any]] # typically list of tuples with timestamp as the first value and whatever value as the second


class CompressedMetric(BaseModel):
    labels: set[tuple[str, Any]]
    values: list[list[Any]]
    
class Group(BaseModel):
    common_labels: set[tuple[str, Any]]
    metrics: list[Union["Group", CompressedMetric]]

def format_labels(labels: set[tuple[str, Any]], section_name:str, line_prefix: str = '') -> list[str]:
    lines = []
    if labels:
        sorted_labels = sorted(labels, key=lambda t: t[0]) # keep label list stable in the outpout by sorting them by key
        if len(sorted_labels) <= 10:
            labels_dict = {}
            for (k, v) in sorted_labels:
                labels_dict[k] = v
            lines.append(f"{line_prefix}{section_name} {json.dumps(labels_dict)}")
        else:
            lines.append(line_prefix+section_name)
            for (k, v) in sorted_labels:
                lines.append(f"{line_prefix}{INDENT_SPACES}- {str(k)}: {str(v)}")
    else:
        raise Exception("No label")
    return lines

INDENT_SPACES = "  "

def format_data(data: Union[Group, CompressedMetric], line_prefix: str = '') -> str:

    lines = [] 
    if isinstance(data, CompressedMetric):
        if not data.labels:
            print(f"{line_prefix}{INDENT_SPACES}- CompressedMetric Data has no labels: labels={data.labels} values={data.values}")
            raise ValueError(f"CompressedMetric Data has no labels: labels={data.labels} values={data.values}")
        lines.extend(format_labels(labels=data.labels, section_name="labels:"))
        if data.values:
            lines.append("values:")
            for value in data.values:
                lines.append(f"{INDENT_SPACES}- {str(value[0])}: {str(value[1])}")
        else:
            lines.append("values: NO_VALUES")
        txt = "\n".join([line_prefix + line for line in lines])
        print(txt)
        return txt
    
    elif data.metrics:
        if not data.common_labels:
            print(f"{line_prefix}{INDENT_SPACES}- Group has no labels: labels={data.common_labels} metrics={len(data.metrics)}")
            raise ValueError(f"Group has no labels: labels={data.common_labels} metrics={len(data.metrics)}")
        group_labels = format_labels(labels=data.common_labels, section_name="common_labels:", line_prefix=line_prefix)
        print(group_labels)
        lines.extend(group_labels)
        lines.append(f"{line_prefix}metrics:")

        for metric in data.metrics:
            metric_lines = format_data(data=metric, line_prefix=line_prefix + (INDENT_SPACES*2))
            if metric_lines:
                metric_lines = f"{line_prefix}{INDENT_SPACES}- " + metric_lines.lstrip()
                lines.append(metric_lines)
        return "\n".join([line for line in lines])
    return ""

def format_zero_values_data(data: Union[Group, CompressedMetric], line_prefix: str = '') -> str:

    lines = [] 
    try:
        if isinstance(data, CompressedMetric):
            lines.extend(format_labels(labels=data.labels, section_name=""))
            txt = "\n".join([line_prefix + line for line in lines])
            # print(txt + "\n\n")
            return txt
        
        elif data.metrics:
            lines.extend(format_labels(labels=data.common_labels, section_name="", line_prefix=line_prefix))

            compress_labels = True
            compressed_label_values:list = []
            compress_key:Optional[str] = None
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
                lines.append(f"{line_prefix}{INDENT_SPACES}- {json.dumps({compress_key:compressed_label_values})}")
            else:

                for metric in data.metrics:
                    metric_lines = format_zero_values_data(data=metric, line_prefix=line_prefix + (INDENT_SPACES*2))
                    if metric_lines:
                        metric_lines = f"{line_prefix}{INDENT_SPACES}- " + metric_lines.lstrip()
                        lines.append(metric_lines)
            txt = "\n".join([line for line in lines])
            # print(txt + "\n\n")
            return txt
        else:
            raise Exception("Data has no metrics and is not a CompressedMetric")
    except Exception:
        logging.error(f"ERROR: {str(data)}", exc_info=True)
        raise
    
    return ""

def format_zero_values_metrics(metrics: list[Union[Group, CompressedMetric]]) -> str:
    formatted_string = "# Metrics with the following hierarchised labels have NO DATA:\n"
    for metric in metrics:
        formatted_string += format_zero_values_data(metric, line_prefix=INDENT_SPACES) + "\n"

    return formatted_string

def format_compressed_metrics(metrics: list[Union[Group, CompressedMetric]]) -> str:
    formatted_string = "# The following metrics have been hierarchically grouped by labels:\n"
    for metric in metrics:
        d = format_data(metric, line_prefix=INDENT_SPACES)
        formatted_string += d + "\n"

    return formatted_string

def raw_metric_to_compressed_metric(raw_metric:RawMetric, remove_labels: set[tuple[str, Any]]) -> CompressedMetric:
        labels:set[tuple[str, Any]] = set()
        if remove_labels:
            for label in raw_metric.metric.items():
                if label not in remove_labels:
                    labels.add(label)
        else:
            labels = set(raw_metric.metric.items())
        return CompressedMetric(
            labels=labels,
            values=raw_metric.values
        )
    
def remove_labels(metric: CompressedMetric, remove_labels: set[tuple[str, Any]]):
    labels:set[tuple[str, Any]] = set()
    for label in metric.labels:
        if label not in remove_labels:
            labels.add(label)
    metric.labels = labels


idx = 0

class PreFilteredMetrics(BaseModel):
    metrics_with_only_zero_values: list[CompressedMetric]
    other_metrics: list[CompressedMetric]

def pre_filter_metrics(metrics: list[CompressedMetric]) -> PreFilteredMetrics:
    """ A prefilter before metrics are merged together.
    It helps for high cardinality when a lot of metrics have 0 as values.
    These metrics are grouped and then summarized as zero values
    """
    metrics_with_only_zero_values:list[CompressedMetric] = []
    other_metrics:list[CompressedMetric] = []
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
        other_metrics=other_metrics
    )


def group_metrics(metrics_to_process: list[CompressedMetric], globally_common_labels:set[tuple[str, Any]] = set(), logging_prefix: str = '') -> list[Union[Group, CompressedMetric]]:
    global idx
    idx = idx + 1
    most_common_label, match_count = find_most_common_label(metrics=metrics_to_process, ignore_label_set = set())
    if not globally_common_labels:
        while most_common_label and match_count == len(metrics_to_process):
            globally_common_labels.add(most_common_label)
            most_common_label, match_count = find_most_common_label(metrics=metrics_to_process, ignore_label_set = globally_common_labels)

        print(f"{logging_prefix}** FOUND {len(globally_common_labels)} globally common labels")
    else:
        print(f"\n\n\n{logging_prefix}NESTED group_metrics {globally_common_labels} with #{len(metrics_to_process)} entities\n\n")
    groups:list[Union[Group, CompressedMetric]] = []
    unmatched_metrics:list[CompressedMetric] = []
    # Constantly iterate over all metrics trying to extract the most common label
    # Once we find a common label that matches more than one metric, we try to find other common labels between these metrics
    # We group the metrics together once we don't find any more common metrics
    if not most_common_label or match_count <= 1:
        unmatched_metrics = metrics_to_process
    else:
        while most_common_label and match_count > 1:
            print(f"{logging_prefix}** PROCESSING GROUP based on label {most_common_label} #{match_count}")
            current_group_labels = set()
            current_group:list[CompressedMetric] = []
            current_group_labels.add(most_common_label)
            unmatched_metrics = []
            for metric_data in metrics_to_process:
                if most_common_label in metric_data.labels:
                    current_group.append(metric_data)
                else:
                    unmatched_metrics.append(metric_data)

            print(f"{logging_prefix}** Found {len(current_group)} entities in group with common label={current_group_labels}")
            all_group_labels = current_group_labels.union(globally_common_labels)
            most_common_label, match_count = find_most_common_label(metrics=current_group, ignore_label_set = all_group_labels)

            # Keep aggregating all labels that are common with the current group.
            while match_count == len(current_group):
                current_group_labels.add(most_common_label)
                all_group_labels = current_group_labels.union(globally_common_labels)
                most_common_label, match_count = find_most_common_label(metrics=current_group, ignore_label_set = all_group_labels)

            print(f"{logging_prefix}** Of the {len(current_group)} entities in the current group, the following labels are common: {current_group_labels}")
            # We're done with our group as we found no more common labels.
            # 1. Remove the common labels from all metrics in this group
            # 2. Recurse to further group metrics within this group
            for metric_in_group in current_group:
                all_group_labels = current_group_labels.union(globally_common_labels)
                remove_labels(metric=metric_in_group, remove_labels=all_group_labels)

            # print(f"{logging_prefix}** Entities in the current group, labels have been filtered: {current_group}")

            # print(f"{logging_prefix}- current_group:\n{format_compressed_metrics(list(current_group))}\n\n")
            # if idx <= 2:
            # if len(current_group)== 1:
            #     print("** WARNING WARNING WARNING WARNING WARNING WARNING WARNING should not happen as we check match_count > 1 for the group")
            #     print(f"{logging_prefix}** Current group size is 1. Adding entity as-is to the output list")
            #     groups.append(current_group[0])
            # elif len(current_group) > 1:
            #     print(f"{logging_prefix}** Current group size is {len(current_group)}. Recursing...")
            #     sub_groups = group_metrics(metrics_to_process=current_group, globally_common_labels=set(), logging_prefix=logging_prefix + INDENT_SPACES + f'{idx}- ')
            #     groups.append(Group(common_labels=current_group_labels, metrics=sub_groups))
            # else:
            #     print("** WARNING WARNING WARNING WARNING WARNING WARNING WARNING should not happen as we check match_count > 1 for the group")
            #     print(f"{logging_prefix}** Current group is empty. Aie Aie Aie")
            groups.append(Group(common_labels=current_group_labels, metrics=current_group))
            # else:
            # print(f"{logging_prefix}- processed group:\n{format_compressed_metrics(list(sub_groups))}\n\n")
                # groups.append(Group(common_labels=current_group_labels, metrics=current_group))

            most_common_label, match_count = find_most_common_label(metrics=unmatched_metrics, ignore_label_set = globally_common_labels)
            metrics_to_process = unmatched_metrics


    # print(f"********************* GROUPS:\n{[g.model_dump() for g in groups]}\n")
    # print(f"********************* UMATCHED:\n{[m.model_dump() for m in unmatched_metrics]}\n")

    for metric in unmatched_metrics:
        remove_labels(metric=metric, remove_labels=globally_common_labels)
        # prepend instead of append so that unique metrics are closer to common labels than grouped metrics
        # I 'guess' it may help the LLM in making sense of the hierarchy
        groups.insert(0, metric)

    if globally_common_labels and len(groups) > 1:
        parent_group = Group(
            common_labels=globally_common_labels,
            metrics=groups
        )
        return [parent_group]
    else:
        return groups

def set_default(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError

def summarize_metrics(metrics_to_process: list[CompressedMetric]) -> str:

    summarized_text = ""
    print(f"metrics_to_process={len(metrics_to_process)}")
    filtered_metrics = pre_filter_metrics(metrics=metrics_to_process)
    print(f"filtered_metrics.metrics_with_only_zero_values={len(filtered_metrics.metrics_with_only_zero_values)}")
    print(f"filtered_metrics.other_metrics={len(filtered_metrics.other_metrics)}")
    if len(filtered_metrics.metrics_with_only_zero_values) >= len(filtered_metrics.other_metrics) * 0.1:
        # print(f"ZERO METRICS:{str(filtered_metrics.metrics_with_only_zero_values)}")
        zero_metrics = group_metrics(filtered_metrics.metrics_with_only_zero_values)
        # print(f"ZERO METRICS GROUPED:{str(zero_metrics)}")
        summarized_text += format_zero_values_metrics(zero_metrics)

    if summarized_text and filtered_metrics.other_metrics:
        summarized_text += "\n"

    if filtered_metrics.other_metrics:
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        metrics = group_metrics(metrics_to_process=filtered_metrics.other_metrics)
        print(json.dumps([metric.model_dump() for metric in metrics], indent=2, default=set_default))
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        print("*************************************************************************************************************")
        summarized_text += format_compressed_metrics(metrics)

    return summarized_text

        


def find_most_common_label(metrics: list[CompressedMetric], ignore_label_set: Set[tuple[str, Any]]) -> tuple[Optional[tuple[str, Any]], int]:
    # print(f"find_most_common_label, metrics#={len(metrics)}, ignore_label_set={ignore_label_set}")
    """
    Find label keys and values that are most common across all label sets.
    Returns labels that appear in ALL label sets with the same value.

    Args:
        label_sets: List of label dictionaries

    Returns:
        Dictionary of common labels (key -> most common value)
    """
    if len(metrics) <= 1:
        return None, 0

    # Count frequency of each (key, value) pair
    label_counts: dict[tuple[str, Any], int] = {}

    # First, collect all (key, value) pairs and their counts
    for metric_data in metrics:
        labels = metric_data.labels
        for (key, value) in labels:
            if (key, value) not in ignore_label_set:
                label_key = (key, value)
                label_counts[label_key] = label_counts.get(label_key, 0) + 1

    # Find labels that appear in ALL sets (100% frequency)
    most_common_label: Optional[tuple[str, Any]] = None
    most_common_count_value = 0
    for (key, value), count in label_counts.items():
        if not most_common_label and count > 1:
            most_common_label = (key, value)
            most_common_count_value = count
        elif count > 1 and count > most_common_count_value:
            most_common_label = (key, value)
            most_common_count_value = count

    # print(f"find_most_common_label -> most_common_label={most_common_label}, most_common_count_value={most_common_count_value}")
    return most_common_label, most_common_count_value
