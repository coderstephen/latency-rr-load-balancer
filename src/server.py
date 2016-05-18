import http
import logging
import socket
import threading
import time


"""
Primary class for the server.
"""
class Server:
    """
    Creates a new server instance.
    """
    def __init__(self, nodes, port, max_threads = 32):
        self.threads = []
        self.socket = None
        self.running = False

        self.nodes = nodes
        self.port = port
        self.max_threads = max_threads
        self.cache_dir = None
        self.most_recent_node = -1

    """
    Starts the server to begin listening for requests.
    """
    def listen(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.listen(100)

        logging.info("Listening on port %d", self.port)

        self.running = True
        while self.running:
            # Wait for incoming connections.
            try:
                connection, address = self.socket.accept()

                # Check if we reach our thread limit.
                while threading.active_count() >= self.max_threads:
                    time.sleep(0.1)

                # Spawn a handler thread.
                thread = RequestHandlerThread(self, connection, address, self.choose_node())
                self.threads.append(thread)
                thread.start()
            except KeyboardInterrupt:
                logging.debug("Shutting down due to keyboard interrupt")
                break

        # Clean up any remaining idle threads.
        logging.debug("Shutting down %d active threads", threading.active_count())
        for thread in self.threads:
            if thread.is_alive():
                thread.join()

        self.socket.close()

    """
    Selects an upstream node to back the next request.

    All of the actual load balancing happens here; this method uses the load balancing algorithm to select a node.

    Uses the Latency-Based Weighted Round Robin scheduling algorithm.
    """
    def choose_node(self):
        # Find the node with the largest effective weight.
        best_weight = 0
        best_node = None
        for node in self.nodes:
            effective_weight = node.weight * node.multiplier

            if effective_weight <= 0:
                best_node = node
                break

            if effective_weight >= best_weight:
                best_weight = effective_weight
                best_node = node

        # Increment multipliers.
        for node in self.nodes:
            node.multiplier *= 1.4

        best_node.multiplier = 1
        return best_node

    """
    Recomputes the weight of a given node based on the most recent latency value.
    """
    def recompute_weight(self, node, latency):
        node.weight = max(int(
            (node.weight / 2) + (1 / latency) + 1
        ), 1)
        print("Node {}:{} has weight {}".format(node.host, node.port, node.weight))

    """
    Stops the server.
    """
    def stop(self):
        self.running = False

"""
Thread class for responding to an incoming request.
"""
class RequestHandlerThread(threading.Thread):
    def __init__(self, server, connection, address, node):
        threading.Thread.__init__(self)
        self.server = server
        self.connection = connection
        self.address = address
        self.node = node

    def run(self):
        # Set a periodic timeout so we can chill out every once and a while.
        self.connection.settimeout(5.0)

        try:
            request = self.read_request()
            if not request:
                logging.warning("Error parsing request from %s", self.address)
                return

            logging.info("%s %s", request.method, request.url)

            # Set proxy headers.
            request.headers["Forwarded"] = "for={}; proto=http; by={}".format(self.address, request.headers["Host"])
            request.headers["X-Forwarded-For"] = self.address
            request.headers["X-Forwarded-Host"] = request.headers["Host"]
            request.headers["X-Forwarded-Proto"] = "http"
            request.headers["Via"] = "generic loadbalancer/1.0"

            # Send the request back to the upstream node.
            try:
                (response, latency) = self.node.handle(request)
            except:
                # Something went wrong upstream; we have to cancel the request.
                logging.error("Error fetching resource from node '%s'", self.node.host)
                response = http.Response(502)
                response.write_to(self.connection)
                return

            # Recompute the node's weight
            self.server.recompute_weight(self.node, latency)

            # Send the response back to the client in buffered form.
            response.headers["Connection"] = "close"
            response.headers.pop("Transfer-Encoding", None)
            response.write_to(self.connection)
        except ConnectionError:
            pass

        # Close the socket and discard this thread.
        self.connection.close()

    def read_request(self):
        try:
            return http.Request.read_from(self.connection)
        except socket.timeout:
            return None
