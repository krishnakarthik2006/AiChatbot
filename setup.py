"""Initialize local application storage and train the intent model; no SQL server is used."""
import sys

from backend.database import init_db


def main():
    init_db()
    import train_chatbot
    train_chatbot.main()
    print("Local store initialized. ChromaDB is created when documents are indexed.")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
