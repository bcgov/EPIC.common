{{- define "submit-cron.labels" -}}
app: {{ .Values.name }}
app-group: submit-app
template: {{ .Values.name }}-deploy
{{- end -}}
