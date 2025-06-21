# Runbooks

Runbooks folder contains operational runbooks for the HolmesGPT project. Runbooks provide step-by-step instructions for common tasks, troubleshooting, and maintenance procedures related to the plugins in this directory.

## Purpose

- Standardize operational processes
- Enable quick onboarding for new team members
- Reduce downtime by providing clear troubleshooting steps

## Structure

### Structured Runbook

Structured runbooks are designed for specific issues when conditions like issue name, id or source match, the corresponding instructions will be returned for investigation.
For example, the investigation in [kube-prometheus-stack.yaml](kube-prometheus-stack.yaml) will be returned when the issue to be investigated match either KubeSchedulerDown or KubeControllerManagerDown.
This runbook is mainly used for `holmes investigate`

### Catalog

Catalog specified in [catalog.json](catalog.json) contains a collection of runbooks written in markdown.
During runtime, LLM will compare the runbook description with the user question and return the most matched runbook for investigation. It's possible no runbook is returned for no match.
