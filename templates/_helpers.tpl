{{/*
Per-release flag values. Each defaults to a value derived from the release
name, unless explicitly overridden in values.yaml.
*/}}

{{- define "ctf.flag1" -}}
{{- if .Values.flags.flag1 -}}
{{ .Values.flags.flag1 }}
{{- else -}}
{{ printf "CTF{cmd_injection_%s}" (.Release.Name | sha256sum | trunc 8) }}
{{- end -}}
{{- end -}}

{{- define "ctf.flag2" -}}
{{- if .Values.flags.flag2 -}}
{{ .Values.flags.flag2 }}
{{- else -}}
{{ printf "CTF{overprivileged_sa_%s}" (.Release.Name | sha256sum | trunc 8) }}
{{- end -}}
{{- end -}}

{{- define "ctf.flag3" -}}
{{- if .Values.flags.flag3 -}}
{{ .Values.flags.flag3 }}
{{- else -}}
{{ printf "CTF{exec_pivot_%s}" (.Release.Name | sha256sum | trunc 8) }}
{{- end -}}
{{- end -}}

{{- define "ctf.flag4" -}}
{{- if .Values.flags.flag4 -}}
{{ .Values.flags.flag4 }}
{{- else -}}
{{ printf "CTF{cluster_admin_%s}" (.Release.Name | sha256sum | trunc 8) }}
{{- end -}}
{{- end -}}

{{- define "ctf.flag5" -}}
{{- if .Values.flags.flag5 -}}
{{ .Values.flags.flag5 }}
{{- else -}}
{{ printf "CTF{node_escape_%s}" (.Release.Name | sha256sum | trunc 8) }}
{{- end -}}
{{- end -}}
