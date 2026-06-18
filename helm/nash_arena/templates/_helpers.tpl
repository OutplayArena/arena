{{/*
Expand the name of the chart.
*/}}
{{- define "nasharena.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "nasharena.fullname" -}}
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
{{- define "nasharena.labels" -}}
helm.sh/chart: {{ include "nasharena.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "nasharena.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "nasharena.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nasharena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "nasharena.backend.selectorLabels" -}}
{{ include "nasharena.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "nasharena.database.selectorLabels" -}}
{{ include "nasharena.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Redis selector labels
*/}}
{{- define "nasharena.redis.selectorLabels" -}}
{{ include "nasharena.selectorLabels" . }}
app.kubernetes.io/component: redis
{{- end }}
