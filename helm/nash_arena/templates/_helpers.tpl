{{/*
Expand the name of the chart.
*/}}
{{- define "blotto.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "blotto.fullname" -}}
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
{{- define "blotto.labels" -}}
helm.sh/chart: {{ include "blotto.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "blotto.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "blotto.selectorLabels" -}}
app.kubernetes.io/name: {{ include "blotto.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "blotto.backend.selectorLabels" -}}
{{ include "blotto.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "blotto.database.selectorLabels" -}}
{{ include "blotto.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}
