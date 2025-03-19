import http.server
import socketserver
import socket
import json
from datetime import datetime
from urllib.parse import parse_qs
from pymongo import MongoClient, errors
import threading
import signal
import mimetypes
import pathlib

running = True

try:
    client = MongoClient("mongodb://mongodb:27017/")

    db = client["messages_db"]
    messages_collection = db["messages"]

    client.admin.command("ping")
    print("Connected successfully to MongoDB!")
except errors.ConnectionFailure as e:
    print(f"Error connecting to MongoDB: {e}")
except errors.PyMongoError as e:
    print(f"An error occurred: {e}")


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def send_static(self):
        self.send_response(200)

        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open(f".{self.path}", "rb") as file:
            self.wfile.write(file.read())

    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        elif self.path == "/message":
            self.path = "/message.html"
        elif pathlib.Path().joinpath(self.path[1:]).exists():
            print(f"Sending static file: {self.path}")
            self.send_static()
        else:
            self.path = "/error.html"

        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == "/send_message":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            post_data = post_data.decode("utf-8")
            form_data = parse_qs(post_data)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", 5000))
            sock.send(
                json.dumps(
                    {
                        "username": form_data["username"][0],
                        "message": form_data["message"][0],
                    }
                ).encode()
            )
            sock.close()

            self.send_response(302)
            self.send_header("Location", "/message")
            self.end_headers()
        else:
            self.send_error(404)


def handle_signal(signum, frame):
    global running
    print("\nStopping servers...")
    running = False


def run_http_server():
    global running
    with socketserver.TCPServer(("", 3000), CustomHandler) as httpd:
        print("HTTP сервер запущено на порту 3000")
        while running:
            httpd.handle_request()


def run_socket_server():
    global running
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", 5000))
    server_socket.listen(1)
    print("Socket server started on port 5000")

    while running:
        try:
            server_socket.settimeout(1)
            client_socket, addr = server_socket.accept()
            data = client_socket.recv(1024).decode()
            message_data = json.loads(data)

            message_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            messages_collection.insert_one(message_data)
            print(f"Received message from {message_data['username']}")

            client_socket.close()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error in socket server: {e}")
            break

    server_socket.close()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    http_thread = threading.Thread(target=run_http_server)
    socket_thread = threading.Thread(target=run_socket_server)

    http_thread.start()
    socket_thread.start()

    http_thread.join()
    socket_thread.join()

    print("Servers stopped")
