import unittest
import os
from dbUtils import SQLiteManager  # Assuming the class is in a file named sqlite_manager.py

class TestSQLiteManager(unittest.TestCase):
    def setUp(self):
        self.username = "testuser"
        self.storage_dir = "test_storage"
        self.db_manager = SQLiteManager(self.username, self.storage_dir)
        
        # Populate the database with test data
        self.db_manager.register_user(self.username, "public_key_testuser")
        self.db_manager.create_user_tables(self.username)
        self.db_manager.add_contact(self.username, "alice", "public_key_alice")
        self.db_manager.add_contact(self.username, "bob", "public_key_bob")
        self.db_manager.save_message(self.username, "alice", "to", "Hello Alice!")
        self.db_manager.save_message(self.username, "bob", "from", "Hello Bob!")

    def tearDown(self):
        self.db_manager.close()
        db_path = os.path.join(self.storage_dir, self.username, f"{self.username}_client.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(os.path.join(self.storage_dir, self.username))
        os.rmdir(self.storage_dir)

    def test_create_global_tables(self):
        tables = self.db_manager.get_all_users()
        self.assertIsInstance(tables, list)

    def test_register_user(self):
        self.db_manager.register_user("charlie", "public_key_123")
        user = self.db_manager.get_all_users()
        self.assertIn(("charlie", "public_key_123"), user)

    def test_create_user_tables(self):
        self.db_manager.create_user_tables("charlie")
        contacts = self.db_manager.get_all_contacts("charlie")
        messages = self.db_manager.get_all_messages("charlie")
        self.assertIsInstance(contacts, list)
        self.assertIsInstance(messages, list)

    def test_add_contact(self):
        self.db_manager.add_contact(self.username, "dave", "public_key_dave")
        contact = self.db_manager.get_contact(self.username, "dave")
        self.assertEqual(contact, ("dave", "public_key_dave"))

    def test_get_all_contacts(self):
        contacts = self.db_manager.get_all_contacts(self.username)
        self.assertGreater(len(contacts), 0)

    def test_save_message(self):
        self.db_manager.save_message(self.username, "dave", "to", "Hey Dave!")
        messages = self.db_manager.get_messages_by_contact(self.username, "dave")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][1], "Hey Dave!")

    def test_get_all_messages(self):
        messages = self.db_manager.get_all_messages(self.username)
        self.assertGreater(len(messages), 1)

    def test_delete_contact(self):
        self.db_manager.delete_contact(self.username, "alice")
        contact = self.db_manager.get_contact(self.username, "alice")
        self.assertIsNone(contact)

    def test_delete_all_messages(self):
        self.db_manager.delete_all_messages(self.username)
        messages = self.db_manager.get_all_messages(self.username)
        self.assertEqual(len(messages), 0)

    def test_get_all_users(self):
        users = self.db_manager.get_all_users()
        self.assertIn((self.username, "public_key_testuser"), users)

if __name__ == "__main__":
    unittest.main()
