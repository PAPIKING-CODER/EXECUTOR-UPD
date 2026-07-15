import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('', port), Handler)
    print(f"🔥 Servidor web corriendo en puerto {port}")
    server.serve_forever()
