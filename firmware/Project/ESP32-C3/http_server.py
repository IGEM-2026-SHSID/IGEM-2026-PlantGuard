import socket
import config

REASONS = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large", 500: "Internal Server Error"}

class HTTPServer:
    def __init__(self, app, host=config.HTTP_HOST, port=config.HTTP_PORT):
        self.app = app
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(2)
        self.sock.settimeout(config.SOCKET_POLL_TIMEOUT_S)

    def poll(self):
        try:
            client, _ = self.sock.accept()
        except OSError:
            return False
        try:
            client.settimeout(config.CLIENT_TIMEOUT_S)
            method, path, body = self._read_request(client)
            status, content_type, payload = self.app.route(method, path, body)
        except RequestError as exc:
            status, content_type, payload = self.app._error(exc.status, exc.code)
        except Exception:
            status, content_type, payload = self.app._error(500, "internal_error")
        try:
            reason = REASONS.get(status, "Error")
            head = "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (status, reason, content_type, len(payload))
            client.sendall(head.encode() + payload)
        finally:
            client.close()
        return True

    def _read_request(self, client):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client.recv(256)
            if not chunk: raise RequestError(400, "incomplete_headers")
            data += chunk
            if len(data) > config.MAX_HEADER_BYTES: raise RequestError(413, "headers_too_large")
        header, body = data.split(b"\r\n\r\n", 1)
        lines = header.decode("ascii").split("\r\n")
        parts = lines[0].split()
        if len(parts) != 3: raise RequestError(400, "invalid_request_line")
        method, target, _ = parts
        length = 0
        for line in lines[1:]:
            if ":" not in line: raise RequestError(400, "invalid_header")
            key, value = line.split(":", 1)
            if key.lower().strip() == "content-length":
                try: length = int(value.strip())
                except ValueError: raise RequestError(400, "invalid_content_length")
        if length < 0 or length > config.MAX_BODY_BYTES: raise RequestError(413, "body_too_large")
        while len(body) < length:
            chunk = client.recv(min(256, length - len(body)))
            if not chunk: raise RequestError(400, "incomplete_body")
            body += chunk
        return method, target.split("?", 1)[0], body[:length]

class RequestError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code

