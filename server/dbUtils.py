import sqlite3
import json
import os
from logConfig import logger
from envLoader import load_env
from cryptographyUtils import CryptoUtils

load_env()

class DbUtils:
    def __init__(self, dbPath, crypto_utils):
        self.dbPath = os.getenv("DATABASE_PATH")
        self.crypto_utils = crypto_utils  # Store CryptoUtils instance

        if not os.path.exists(dbPath):
            logger.info("dbInit - Initializing new database")
        else:
            logger.info("dbInit - Using existing database")

        self.connection = sqlite3.connect(dbPath, check_same_thread=False)
        self.cursor = self.connection.cursor()
        self._initializeTables()

    def _initializeTables(self):
        logger.info("Ensuring necessary database tables exist...")
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
            encrypted_publicKey = self.crypto_utils._encrypt_data(publicKey.encode())  # Encrypt
            encrypted_senderTag = self.crypto_utils._encrypt_data(senderTag.encode())  # Encrypt

            self.cursor.execute(
                "INSERT INTO users (username, publicKey, senderTag) VALUES (?, ?, ?)",
                (username, encrypted_publicKey, encrypted_senderTag),
            )
            self.connection.commit()
            logger.info("addUser successful!")
        except sqlite3.IntegrityError as e:
            logger.error(f"addUser error: {e}")
            return False
        return True

    def getUserByUsername(self, username):
        self.cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()
        if result:
            decrypted_publicKey = self.crypto_utils._decrypt_data(result[1])  # Decrypt
            decrypted_senderTag = self.crypto_utils._decrypt_data(result[2])  # Decrypt
            logger.info("getUserByUsername - success")
            return (result[0], decrypted_publicKey, decrypted_senderTag)
        return None

    def getUserBySenderTag(self, senderTag):
        self.cursor.execute("SELECT * FROM users WHERE senderTag = ?", (senderTag,))
        result = self.cursor.fetchone()
        if result:
            decrypted_publicKey = self.crypto_utils._decrypt_data(result[1])  # Decrypt
            decrypted_senderTag = self.crypto_utils._decrypt_data(result[2])  # Decrypt
            logger.info("getUserBySenderTag - success!")
            return (result[0], decrypted_publicKey, decrypted_senderTag)  # Return decrypted data
        return None

    def updateUserField(self, username, field, value):
        allowed_fields = ["publicKey", "senderTag"]  # Only allow updates to these fields
        if field not in allowed_fields:
            logger.error(f"updateUserField - Invalid field update attempt: {field}")
            return False

        try:
            self.cursor.execute(f"UPDATE users SET {field} = ? WHERE username = ?", (value, username))
            self.connection.commit()
            logger.info("updaterUserField - success!")
        except sqlite3.Error as e:
            logger.error(f"updateUserField - Error updating user: {e}")
            return False
        return True

    # def addGroup(self, groupId, initialUsers):
    #     try:
    #         encrypted_userList = self.crypto_utils._encrypt_data(json.dumps(initialUsers).encode())  # Encrypt
    #         self.cursor.execute(
    #             "INSERT INTO groups (groupID, userList) VALUES (?, ?)",
    #             (groupId, encrypted_userList),
    #         )
    #         self.connection.commit()
    #         logger.info(f"Group {groupId} added successfully.")
    #     except sqlite3.IntegrityError as e:
    #         logger.error(f"Error adding group {groupId}: {e}")
    #         return False
    #     return True

    # def getGroup(self, groupId):
    #     self.cursor.execute("SELECT * FROM groups WHERE groupID = ?", (groupId,))
    #     result = self.cursor.fetchone()
    #     if result:
    #         decrypted_userList = self.crypto_utils._decrypt_data(result[1])  # Decrypt
    #         return (result[0], json.loads(decrypted_userList))  # Return decrypted data
    #     return None

    def close(self):
        logger.info("Closing database connection.")
        self.connection.close()
