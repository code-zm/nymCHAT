# dbUtils.py
import sqlite3
import json
import os

class DbUtils:
    def __init__(self, dbPath="nym_server.db"):
        self.dbPath = dbPath

        if not os.path.exists(dbPath):
            print(f"[INFO] Initializing new database at {dbPath}.")
        else:
            print(f"[INFO] Using existing database at {dbPath}.")

        self.connection = sqlite3.connect(dbPath, check_same_thread=False)
        self.cursor = self.connection.cursor()
        self._initializeTables()

    def _initializeTables(self):
        print("[INFO] Ensuring necessary database tables exist...")
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            publicKey TEXT NOT NULL,
            senderTag TEXT NOT NULL
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            groupID TEXT PRIMARY KEY,
            userList TEXT NOT NULL
        )
        """)
        self.connection.commit()

    def addUser(self, username, publicKey, senderTag):
        try:
            self.cursor.execute(
                "INSERT INTO users (username, publicKey, senderTag) VALUES (?, ?, ?)",
                (username, publicKey, senderTag),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error adding user: {e}")
            return False
        return True

    def getUserByUsername(self, username):
        self.cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return self.cursor.fetchone()

    def getUserBySenderTag(self, senderTag):
        self.cursor.execute("SELECT * FROM users WHERE senderTag = ?", (senderTag,))
        return self.cursor.fetchone()

    def updateUserField(self, username, field, value):
        try:
            self.cursor.execute(f"UPDATE users SET {field} = ? WHERE username = ?", (value, username))
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating user: {e}")
            return False

    def addGroup(self, groupId, initialUsers):
        try:
            self.cursor.execute(
                "INSERT INTO groups (groupID, userList) VALUES (?, ?)",
                (groupId, json.dumps(initialUsers)),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error adding group: {e}")
            return False
        return True

    def getGroup(self, groupId):
        self.cursor.execute("SELECT * FROM groups WHERE groupID = ?", (groupId,))
        return self.cursor.fetchone()

    def close(self):
        print("[INFO] Closing database connection.")
        self.connection.close()

