"""
Base class for HTTP messages.
"""
class Message:
    """
    Creates a new HTTP message.
    """
    def __init__(self, headers = {}, body = b""):
        self.headers = headers
        self.body = body
        self.version = "1.1"

    def __str__(self):
        message = ""
        for header, value in self.headers.items():
            message += "{}: {}\r\n".format(header, value)
        return message

    def keep_alive(self):
        return "Connection" in self.headers and self.headers["Connection"].lower() == "keep-alive"

    def chunked_encoding(self):
        return "Transfer-Encoding" in self.headers and self.headers["Transfer-Encoding"].lower() == "chunked"

    """
    Writes the HTTP message object to a a socket.
    """
    def write_to(self, socket):
        # If not using chunked encoding, set the response length.
        if not self.chunked_encoding():
            self.headers["Content-Length"] = str(len(self.body))

        string = self.__str__()
        socket.sendall(string.encode() + b"\r\n")

        # Use the right encoding.
        if self.chunked_encoding():
            buffer = self.body
            while len(buffer) > 0:
                chunk_size = min(4096, len(buffer))
                socket.sendall((hex(chunk_size)[2:] + "\r\n").encode())
                socket.sendall(buffer[:chunk_size] + b"\r\n")
                buffer = buffer[chunk_size:]
            socket.sendall(b"0\r\n\r\n")
        else:
            socket.sendall(self.body)

    """
    Parses an HTTP message from a live socket.
    """
    def _parse(self, socket, buffer):
        # Read the header block first.
        read_until(socket, buffer, b"\r\n\r\n")
        start = buffer.find(b"\r\n")
        end = buffer.find(b"\r\n\r\n")
        headers = buffer[start + 2:end].decode().split("\r\n")

        for header in headers:
            separator = header.find(":")
            self.headers[header[:separator].strip().title()] = header[separator + 1:].strip()

        # More modern servers and clients use a chunked encoding for variable-length messages.
        if self.chunked_encoding():
            self.body = bytearray()
            chunk = buffer[end + 4:]

            # Read the body in chunks.
            while True:
                read_until(socket, chunk, b"\r\n")
                chunk_header = chunk[:chunk.find(b"\r\n")].decode().split(";")
                chunk_size = int(chunk_header[0], 16)
                chunk = chunk[chunk.find(b"\r\n") + 2:]
                read_length(socket, chunk, chunk_size + 2)
                self.body.extend(chunk[:chunk_size])

                # When we reach an empty chunk, there are no more chunks left to read.
                if chunk_size == 0:
                    break
                chunk = chunk[chunk_size + 2:]

        # We are told the message length explicitly, HTTP/1.0 style.
        elif "Content-Length" in self.headers:
            length = int(self.headers["Content-Length"])
            self.body = buffer[end + 4:]
            read_length(socket, self.body, length)

"""
Implementation of an HTTP request.
"""
class Request(Message):
    """
    Reads a request from a connected socket.
    """
    def read_from(socket):
        buffer = bytearray()
        read_until(socket, buffer, b"\r\n")

        request_line = buffer[:buffer.find(b"\r\n")].decode().split(" ")
        request = Request(request_line[0], request_line[1])

        request._parse(socket, buffer)
        return request

    def __init__(self, method, url, headers = {}, body = b""):
        self.method = method
        self.url = url
        Message.__init__(self, headers, body)

    def __str__(self):
        return "{} {} HTTP/{}\r\n{}".format(
            self.method,
            self.url,
            self.version,
            Message.__str__(self)
        )

"""
Implementation of an HTTP response.
"""
class Response(Message):
    """
    Reads a response from a connected socket.
    """
    def read_from(socket):
        buffer = bytearray()
        read_until(socket, buffer, b"\r\n")

        status_line = buffer[:buffer.find(b"\r\n")].decode().split(" ")
        response = Response(int(status_line[1]))

        response._parse(socket, buffer)
        return response

    def __init__(self, status, headers = {}, body = b""):
        self.status = status
        Message.__init__(self, headers, body)

    def __str__(self):
        return "HTTP/{} {}\r\n{}".format(
            self.version,
            self.status,
            Message.__str__(self)
        )

# Helper functions for socket reading.
def read_until(socket, buffer, bytes):
    while buffer.find(bytes) == -1:
        chunk = socket.recv(4096)
        if len(chunk) == 0:
            raise ConnectionError()

        buffer.extend(chunk)

def read_length(socket, buffer, length):
    while len(buffer) < length:
        chunk = socket.recv(min(4096, length - len(buffer)))
        if len(chunk) == 0:
            raise ConnectionError()

        buffer.extend(chunk)
