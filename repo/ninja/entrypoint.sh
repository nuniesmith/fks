#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

# Discover a candidate DLL if one not explicitly provided
if [[ -n "${FKS_NINJA_DLL:-}" ]]; then
  DLL="$FKS_NINJA_DLL"
else
  DLL=$(ls *.dll 2>/dev/null | grep -E '(FKS|Service|App)' | head -n1 || true)
fi
if [[ -z "${DLL:-}" ]]; then
  DLL="FKSService.dll"
fi
echo "[ninja] Starting dotnet $DLL" >&2

# Start a tiny background HTTP health server on $FKS_SERVICE_PORT (default 4900)
PORT="${FKS_SERVICE_PORT:-4900}"
python - <<'PY' &
import http.server, socketserver, os, threading, time
PORT = int(os.environ.get('FKS_SERVICE_PORT','4900'))
class H(http.server.BaseHTTPRequestHandler):
  def log_message(self, *a, **k):
    return
  def do_GET(self):
    if self.path == '/health':
      self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
      self.wfile.write(b'{"status":"healthy","service":"ninja","timestamp":'+str(time.time()).encode()+b'}')
    else:
      self.send_response(404); self.end_headers()
with socketserver.TCPServer(('', PORT), H) as httpd:
  threading.Thread(target=httpd.serve_forever, daemon=True).start()
  while True: time.sleep(3600)
PY

# Launch main process in foreground
exec dotnet "$DLL"
