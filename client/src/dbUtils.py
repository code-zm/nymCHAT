import sqlite3
import json
import os
from datetime import datetime

class SQLiteManager:
    def __init__(self, username, storage_dir="storage"):
        """
        Initialize the database connection and create necessary tables.
        :param username: The username of the client.
        :param storage_dir: The base directory for storage.
        """
        user_dir = os.path.join(storage_dir, username)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        db_path = os.path.join(user_dir, f"{username}_client.db")
        self.conn = sqlite3.connect(db_path)
        self.create_global_tables()

    def create_global_tables(self):
        """
        Create global tables to track users.
        """
        with self.conn:
            # Global users table now stores only username and public_key
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL
                )
            """)

    def create_user_tables(self, username):
        """
        Create user-specific tables for contacts and messages.
        """
        with self.conn:
            # Contacts table for the specific user now stores username and public_key
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS contacts_{username} (
                    username TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL
                )
            """)
            # Messages table for the specific user remains unchanged
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS messages_{username} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    type TEXT CHECK(type IN ('to', 'from')) NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def register_user(self, username, public_key):
        """
        Register a new user and create their specific tables.
        """
        with self.conn:
            # Add user to the global users table (store the public key)
            self.conn.execute("""
                INSERT OR REPLACE INTO users (username, public_key)
                VALUES (?, ?)
            """, (username, public_key))
            # Create user-specific tables
            self.create_user_tables(username)

    def add_contact(self, active_user, contact_username, public_key):
        """
        Add or update a contact for the specified active user.
        """
        with self.conn:
            self.conn.execute(f"""
                INSERT OR REPLACE INTO contacts_{active_user} (username, public_key)
                VALUES (?, ?)
            """, (contact_username, public_key))

    def get_contact(self, active_user, contact_username):
        """
        Retrieve a contact's information for the specified active user.
        Returns (username, public_key) if found.
        """
        with self.conn:
            return self.conn.execute(f"""
                SELECT username, public_key
                FROM contacts_{active_user}
                WHERE username = ?
            """, (contact_username,)).fetchone()

    def get_all_contacts(self, active_user):
        """
        Retrieve all contacts for the specified active user.
        """
        with self.conn:
            return self.conn.execute(f"SELECT * FROM contacts_{active_user}").fetchall()

    def save_message(self, active_user, contact_username, msg_type, message):
        """
        Save a message for the specified active user.
        """
        with self.conn:
            self.conn.execute(f"""
                INSERT INTO messages_{active_user} (username, type, message)
                VALUES (?, ?, ?)
            """, (contact_username, msg_type, message))

    def get_messages_by_contact(self, active_user, contact_username):
        """
        Retrieve all messages exchanged with a specific contact for the active user.
        """
        with self.conn:
            return self.conn.execute(f"""
                SELECT type, message, timestamp
                FROM messages_{active_user}
                WHERE username = ?
                ORDER BY timestamp ASC
            """, (contact_username,)).fetchall()

    def get_all_messages(self, active_user):
        """
        Retrieve all messages for the specified active user.
        """
        with self.conn:
            return self.conn.execute(f"""
                SELECT username, type, message, timestamp
                FROM messages_{active_user}
                ORDER BY username, timestamp ASC
            """).fetchall()

    def delete_contact(self, active_user, contact_username):
        """
        Delete a contact for the specified active user.
        """
        with self.conn:
            self.conn.execute(f"""
                DELETE FROM contacts_{active_user} WHERE username = ?
            """, (contact_username,))

    def delete_all_messages(self, active_user):
        """
        Delete all messages for the specified active user.
        """
        with self.conn:
            self.conn.execute(f"DELETE FROM messages_{active_user}")

    def get_all_users(self):
        """
        Retrieve all registered users.
        """
        with self.conn:
            return self.conn.execute("SELECT * FROM users").fetchall()

    def close(self):
        """
        Close the database connection.
        """
        self.conn.close()
