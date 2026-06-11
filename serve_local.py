from werkzeug.serving import make_server

from app import app


if __name__ == "__main__":
    server = make_server("127.0.0.1", 5000, app)
    server.serve_forever()
