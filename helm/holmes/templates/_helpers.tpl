{{/*
Return the service account name to use
*/}}
{{- define "holmes.serviceAccountName" -}}
{{- if .Values.createServiceAccount -}}
{{- if .Values.customServiceAccountName -}}
{{ .Values.customServiceAccountName }}
{{- else -}}
{{ .Release.Name }}-holmes-service-account
{{- end -}}
{{- else -}}
default
{{- end -}}
{{- end -}}
