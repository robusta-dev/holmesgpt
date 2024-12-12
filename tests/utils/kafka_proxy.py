import socket
import threading
from typing import Dict, List

class KafkaProxy:
    def __init__(self, port_mappings: Dict[str, int]):
        """
        port_mappings: dict mapping domain names to target ports
        e.g., {
            "kafka-controller-0.kafka-controller-headless.default.svc.cluster.local": 31092,
            "kafka-controller-1.kafka-controller-headless.default.svc.cluster.local": 31093,
            "kafka-controller-2.kafka-controller-headless.default.svc.cluster.local": 31094,
        }
        """
        self.port_mappings = port_mappings
        self.running = False
        self.threads: List[threading.Thread] = []
        self.connections: List[socket.socket] = []

    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        try:
            # First message from Kafka client includes the host information
            # Peek at the data without removing it from the socket buffer
            initial_data = client_socket.recv(1024, socket.MSG_PEEK)

            # Find target port based on domain in the initial message
            target_port = None
            for domain, port in self.port_mappings.items():
                if domain.encode() in initial_data:
                    target_port = port
                    break

            if not target_port:
                print("No matching domain found in initial data")
                target_port = next(iter(self.port_mappings.values()))
                client_socket.close()
                return

            # Connect to target
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.connect(('localhost', target_port))

            def forward(source: socket.socket, destination: socket.socket):
                try:
                    while self.running:
                        data = source.recv(4096)
                        if not data:
                            break
                        destination.send(data)
                except:
                    pass
                finally:
                    source.close()
                    destination.close()

            t1 = threading.Thread(target=forward, args=(client_socket, target_socket))
            t2 = threading.Thread(target=forward, args=(target_socket, client_socket))
            t1.start()
            t2.start()
            self.threads.extend([t1, t2])
            self.connections.extend([client_socket, target_socket])

        except Exception as e:
            print(f"Error handling client: {e}")
            client_socket.close()

    def start(self):
        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 9092))
        server.listen(5)

        def accept_connections():
            while self.running:
                try:
                    client_socket, client_address = server.accept()
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address)
                    )
                    thread.start()
                    self.threads.append(thread)
                except:
                    break

        self.accept_thread = threading.Thread(target=accept_connections)
        self.accept_thread.start()
        self.threads.append(self.accept_thread)
        self.server = server

    def stop(self):
        self.running = False
        # Close all connections
        for conn in self.connections:
            try:
                conn.close()
            except Exception:
                pass
        # Close server socket
        try:
            self.server.close()
        except Exception:
            pass
        # Wait for all threads to complete
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1)
