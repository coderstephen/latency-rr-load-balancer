#!/usr/bin/python3
import logging
from node import Node
import server
import yaml

default_config = {
    "server": {
        "port": 8000
    },
    "nodes": []
}


def get_config():
    config = default_config.copy()

    with open("config.yaml", "r") as file:
        config.update(yaml.load(file))

    return config

def main():
    # Set the logging level.
    logging.getLogger().setLevel(logging.DEBUG)

    # Set up the log handler.
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logging.getLogger().addHandler(handler)

    # Load configuration.
    config = get_config()

    # Set up the configured upstream node servers.
    nodes = []
    for node in config["nodes"]:
        nodes.append(Node(node["host"], node["port"]))

    # Run the server.
    app = server.Server(nodes, config["server"]["port"], config["server"]["max_threads"])
    app.listen()

main()
