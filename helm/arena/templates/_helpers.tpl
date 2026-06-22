{{/*
Expand the name of the chart.
*/}}
{{- define "arena.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "arena.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "arena.labels" -}}
helm.sh/chart: {{ include "arena.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "arena.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "arena.selectorLabels" -}}
app.kubernetes.io/name: {{ include "arena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "arena.backend.selectorLabels" -}}
{{ include "arena.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "arena.database.selectorLabels" -}}
{{ include "arena.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Redis selector labels
*/}}
{{- define "arena.redis.selectorLabels" -}}
{{ include "arena.selectorLabels" . }}
app.kubernetes.io/component: redis
{{- end }}

{{/*
Docs selector labels
*/}}
{{- define "arena.docs.selectorLabels" -}}
{{ include "arena.selectorLabels" . }}
app.kubernetes.io/component: docs
{{- end }}
