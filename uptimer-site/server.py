import os
import http.server
import socketserver

PORT = int(os.environ.get("PORT", "8080"))

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence request logs

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print(f"[FMD BOT] Status page en puerto {PORT}")
with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    httpd.serve_forever()
