{{/*
Expand the name of the chart.
*/}}
{{- define "outplaylabs-arena.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "outplaylabs-arena.fullname" -}}
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
{{- define "outplaylabs-arena.labels" -}}
helm.sh/chart: {{ include "outplaylabs-arena.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "outplaylabs-arena.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "outplaylabs-arena.selectorLabels" -}}
app.kubernetes.io/name: {{ include "outplaylabs-arena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "outplaylabs-arena.backend.selectorLabels" -}}
{{ include "outplaylabs-arena.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "outplaylabs-arena.database.selectorLabels" -}}
{{ include "outplaylabs-arena.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Redis selector labels
*/}}
{{- define "outplaylabs-arena.redis.selectorLabels" -}}
{{ include "outplaylabs-arena.selectorLabels" . }}
app.kubernetes.io/component: redis
{{- end }}

{{/*
Docs selector labels
*/}}
{{- define "outplaylabs-arena.docs.selectorLabels" -}}
{{ include "outplaylabs-arena.selectorLabels" . }}
app.kubernetes.io/component: docs
{{- end }}
