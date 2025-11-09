{{/*
Return the service account name to use
*/}}
{{- define "holmes.serviceAccountName" -}}
{{- if .Values.customServiceAccountName -}}
{{ .Values.customServiceAccountName }}
{{- else if .Values.createServiceAccount -}}
{{ .Release.Name }}-holmes-service-account
{{- else -}}
default
{{- end -}}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "holmes.selectorLabels" -}}
app: holmes
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Common labels for all resources
*/}}
{{- define "holmes.labels" -}}
{{- include "holmes.selectorLabels" . }}
app.kubernetes.io/name: holmes
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}
