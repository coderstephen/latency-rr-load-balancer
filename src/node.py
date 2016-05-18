import http
import socket
import time


"""
Accesses and controls an upstream server node.
"""
class Node:
    def __init__(self, host, port = 80):
        self.host = host
        self.port = port
        self.connection = None
        self.weight = 0
        self.multiplier = 1

    """
    Sends a request to the node and returns the response.
    """
    def handle(self, request):
        if self.connection:
            connection = self.connection
        else:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.connect((self.host, self.port))
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Begin measuring latency
        latency = time.clock()

        upstream_request = http.Request("GET", request.url, request.headers.copy())
        upstream_request.headers["Connection"] = "close"
        upstream_request.headers["Host"] = self.host

        upstream_request.write_to(connection)
        response = http.Response.read_from(connection)

        # Capture the time to handle the request
        latency = time.clock() - latency

        # Handle persistent HTTP with the node.
        if response.keep_alive():
            self.connection = connection
        else:
            connection.close()

        return (response, latency)
