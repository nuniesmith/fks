{{/*
Expand the name of the chart.
*/}}
{{- define "vision.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vision.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "vision.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vision.labels" -}}
helm.sh/chart: {{ include "vision.chart" . }}
{{ include "vision.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vision.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vision.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vision.serviceAccountName" -}}
{{- if .Values.rbac.serviceAccount.create }}
{{- default (include "vision.fullname" .) .Values.rbac.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.rbac.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Metrics Server - Full name
*/}}
{{- define "vision.metricsServer.fullname" -}}
{{- printf "%s-metrics" (include "vision.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Metrics Server - Labels
*/}}
{{- define "vision.metricsServer.labels" -}}
{{ include "vision.labels" . }}
app.kubernetes.io/component: metrics-server
{{- end }}

{{/*
Metrics Server - Selector Labels
*/}}
{{- define "vision.metricsServer.selectorLabels" -}}
{{ include "vision.selectorLabels" . }}
app.kubernetes.io/component: metrics-server
{{- end }}

{{/*
Live Pipeline - Full name
*/}}
{{- define "vision.livePipeline.fullname" -}}
{{- printf "%s-pipeline" (include "vision.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Live Pipeline - Labels
*/}}
{{- define "vision.livePipeline.labels" -}}
{{ include "vision.labels" . }}
app.kubernetes.io/component: live-pipeline
{{- end }}

{{/*
Live Pipeline - Selector Labels
*/}}
{{- define "vision.livePipeline.selectorLabels" -}}
{{ include "vision.selectorLabels" . }}
app.kubernetes.io/component: live-pipeline
{{- end }}

{{/*
Return the proper image name
*/}}
{{- define "vision.image" -}}
{{- $registryName := .registry -}}
{{- $repositoryName := .repository -}}
{{- $tag := .tag | toString -}}
{{- if .global }}
    {{- if .global.imageRegistry }}
        {{- $registryName = .global.imageRegistry -}}
    {{- end -}}
{{- end -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "vision.imagePullSecrets" -}}
{{- if .Values.global }}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for PodDisruptionBudget
*/}}
{{- define "vision.podDisruptionBudget.apiVersion" -}}
{{- if semverCompare ">=1.21-0" .Capabilities.KubeVersion.GitVersion -}}
{{- print "policy/v1" -}}
{{- else -}}
{{- print "policy/v1beta1" -}}
{{- end -}}
{{- end -}}

{{/*
Return the appropriate apiVersion for Ingress
*/}}
{{- define "vision.ingress.apiVersion" -}}
{{- if semverCompare ">=1.19-0" .Capabilities.KubeVersion.GitVersion -}}
{{- print "networking.k8s.io/v1" -}}
{{- else -}}
{{- print "networking.k8s.io/v1beta1" -}}
{{- end -}}
{{- end -}}

{{/*
Return the appropriate apiVersion for HorizontalPodAutoscaler
*/}}
{{- define "vision.hpa.apiVersion" -}}
{{- if semverCompare ">=1.23-0" .Capabilities.KubeVersion.GitVersion -}}
{{- print "autoscaling/v2" -}}
{{- else -}}
{{- print "autoscaling/v2beta2" -}}
{{- end -}}
{{- end -}}

{{/*
Compile all warnings into a single message
*/}}
{{- define "vision.validateValues" -}}
{{- $messages := list -}}
{{- if and .Values.metricsServer.enabled (not .Values.metricsServer.image.tag) -}}
{{- $messages = append $messages "ERROR: metricsServer.image.tag is required when metricsServer is enabled" -}}
{{- end -}}
{{- if and .Values.livePipeline.enabled (not .Values.livePipeline.image.tag) -}}
{{- $messages = append $messages "ERROR: livePipeline.image.tag is required when livePipeline is enabled" -}}
{{- end -}}
{{- if $messages -}}
{{- printf "\nVALUES VALIDATION:\n%s" (join "\n" $messages) | fail -}}
{{- end -}}
{{- end -}}
