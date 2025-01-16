import tkinter as tk
from tkinter import ttk
import sqlite3
import asyncio
import json
from websockets import connect
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

# SQLite setup
conn = sqlite3.connect("nym_server.db", check_same_thread=False)
cursor = conn.cursor()

# Initialize tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    publicKey TEXT NOT NULL,
    senderTag TEXT NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    groupID TEXT PRIMARY KEY,
    userList TEXT NOT NULL
)
""")
conn.commit()

def verify_signature(public_key_pem, signature, message):
    try:
        public_key = load_pem_public_key(public_key_pem.encode())
        public_key.verify(signature, message.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        print(f"Error verifying signature: {e}")
        return False

class NymServer:
    def __init__(self, websocket_url="ws://127.0.0.1:1977"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.self_address = None

    async def connect_websocket(self):
        try:
            self.websocket = await connect(self.websocket_url)
            print("Connected to WebSocket.")
            await self.websocket.send(json.dumps({"type": "selfAddress"}))
            response = await self.websocket.recv()
            data = json.loads(response)
            self.self_address = data.get("address")
            print("Server Address:", self.self_address)
            await self.receive_messages()
        except Exception as e:
            print(f"WebSocket connection error: {e}")
        finally:
            await self.cleanup_websocket()

    async def receive_messages(self):
        try:
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)
                print("Received message:", data)
                await self.process_received_message(data)
        except Exception as e:
            print(f"Error receiving messages: {e}")
        finally:
            print("WebSocket connection terminated.")

    async def process_received_message(self, message_data):
        if message_data.get("type") == "received":
            encapsulated_json = message_data.get("message")
            sender_tag = message_data.get("senderTag")
            try:
                encapsulated_data = json.loads(encapsulated_json)
                action = encapsulated_data.get("action")

                if action == "query":
                    await self.handle_query(encapsulated_data, sender_tag)
                elif action == "register":
                    await self.handle_register(encapsulated_data, sender_tag)
                elif action == "update":
                    await self.handle_update(encapsulated_data, sender_tag)
                elif action == "send":
                    await self.handle_send(encapsulated_data, sender_tag)
                elif action == "sendGroup":
                    await self.handle_send_group(encapsulated_data, sender_tag)
                elif action == "createGroup":
                    await self.handle_create_group(encapsulated_data, sender_tag)
                elif action == "inviteGroup":
                    await self.handle_send_invite(encapsulated_data, sender_tag)
                else:
                    print(f"Unknown encapsulated action: {action}")
            except json.JSONDecodeError:
                print("Error decoding encapsulated message")

    async def send_message(self, message):
        print("Sending message:", message)
        await self.websocket.send(json.dumps(message))

    async def send_confirmation(self, recipient_tag, status):
        confirm_message = {
            "type": "reply",  # Aligned to the client's expected message type
            "message": f"{status}",
            "senderTag": recipient_tag
        }
        await self.send_message(confirm_message)

    async def handle_register(self, message_data, sender_tag):
        username = message_data.get("username")
        public_key = message_data.get("publicKey")

        if not username or not public_key:
            # Handle invalid data
            await self.send_confirmation(sender_tag, "error: missing username or public key")
            return

        # Check if the username is already in use
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            await self.send_confirmation(sender_tag, "error: username already in use")
            return

        # Check if the senderTag is already in use
        cursor.execute("SELECT * FROM users WHERE senderTag = ?", (sender_tag,))
        if cursor.fetchone():
            await self.send_confirmation(sender_tag, "error: senderTag already in use")
            return

    # Add the new user to the database
    cursor.execute(
        "INSERT INTO users (username, publicKey, senderTag) VALUES (?, ?, ?)",
        (username, public_key, sender_tag),
    )
    conn.commit()
    print(f"User {username} successfully registered with SenderTag {sender_tag}.")
    await self.send_confirmation(sender_tag, "success")

    async def handle_query(self, message_data, sender_tag):
        username = message_data.get("target")
        cursor.execute("SELECT senderTag FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user:
            await self.send_confirmation(user[0], "confirm")
        else:
            await self.send_confirmation(sender_tag, "deny")

    async def handle_send(self, message_data, sender_tag):
        recipient = message_data.get("target")
        content = message_data.get("content")
        cursor.execute("SELECT senderTag FROM users WHERE username = ?", (recipient,))
        user = cursor.fetchone()

        if user:
            message = {
                "type": "reply",
                "message": content,
                "senderTag": user[0]
            }
            await self.send_message(message)

    async def handle_send_group(self, message_data, sender_tag):
        group_id = message_data.get("target")
        content = message_data.get("content")
        cursor.execute("SELECT userList FROM groups WHERE groupID = ?", (group_id,))
        group = cursor.fetchone()

        if group:
            user_list = json.loads(group[0])
            for username in user_list:
                cursor.execute("SELECT senderTag FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                if user:
                    message = {
                        "type": "message",
                        "recipient": user[0],
                        "message": content
                    }
                    await self.send_message(message)

    async def handle_update(self, message_data, sender_tag):
        field = message_data.get("field")
        value = message_data.get("value")
        signature = message_data.get("signature")
        username = message_data.get("target")

        cursor.execute("SELECT publicKey FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if not user:
            await self.send_confirmation(sender_tag, "deny")
            return

        public_key_pem = user[0]
        if not verify_signature(public_key_pem, bytes.fromhex(signature), json.dumps({field: value})):
            await self.send_confirmation(sender_tag, "deny")
            return

        cursor.execute(f"UPDATE users SET {field} = ? WHERE username = ?", (value, username))
        conn.commit()
        await self.send_confirmation(sender_tag, "confirm")

    async def handle_create_group(self, message_data, sender_tag):
        group_id = message_data.get("groupID")
        initial_user = sender_tag

        cursor.execute("INSERT INTO groups (groupID, userList) VALUES (?, ?)",
                       (group_id, json.dumps([initial_user])))
        conn.commit()
        await self.send_confirmation(sender_tag, "confirm")

    async def handle_send_invite(self, message_data, sender_tag):
        recipient = message_data.get("target")
        group_id = message_data.get("groupID")
        group_name = message_data.get("groupName")
        cursor.execute("SELECT senderTag FROM users WHERE username = ?", (recipient,))
        user = cursor.fetchone()

        if user:
            invite_message = {
                "type": "invite",
                "recipient": user[0],
                "message": {
                    "groupID": group_id,
                    "groupName": group_name
                }
            }
            await self.send_message(invite_message)

    async def cleanup_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            finally:
                self.websocket = None

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Server GUI")

        # Messages Frame
        self.messages_frame = ttk.LabelFrame(root, text="Received Messages")
        self.messages_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.messages_list = tk.Text(self.messages_frame, wrap="word", height=15)
        self.messages_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Database Fields Frame
        self.database_frame = ttk.LabelFrame(root, text="Database Fields")
        self.database_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.database_tabs = ttk.Notebook(self.database_frame)
        self.database_tabs.pack(fill="both", expand=True)

        # Users Tab
        self.users_tab = ttk.Frame(self.database_tabs)
        self.database_tabs.add(self.users_tab, text="Users")

        self.users_list = tk.Text(self.users_tab, wrap="word", height=10)
        self.users_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Groups Tab
        self.groups_tab = ttk.Frame(self.database_tabs)
        self.database_tabs.add(self.groups_tab, text="Groups")

        self.groups_list = tk.Text(self.groups_tab, wrap="word", height=10)
        self.groups_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Refresh Button
        self.refresh_button = ttk.Button(root, text="Refresh Database Fields", command=self.refresh_database)
        self.refresh_button.pack(pady=10)

        # Initialize asyncio loop integration
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.server_main())
        self.root.after(100, self.run_async_tasks)

    def log_message(self, message):
        self.messages_list.insert(tk.END, message + "\n")
        self.messages_list.see(tk.END)

    def refresh_database(self):
        self.users_list.delete(1.0, tk.END)
        self.groups_list.delete(1.0, tk.END)

        # Fetch users
        cursor.execute("SELECT username, publicKey FROM users")
        users = cursor.fetchall()
        for user in users:
            self.users_list.insert(tk.END, f"Username: {user[0]}, PublicKey: {user[1]}\n")

        # Fetch groups
        cursor.execute("SELECT groupID, userList FROM groups")
        groups = cursor.fetchall()
        for group in groups:
            self.groups_list.insert(tk.END, f"GroupID: {group[0]}, Users: {group[1]}\n")

    def run_async_tasks(self):
        try:
            self.loop.stop()
            self.loop.run_forever()
        except RuntimeError:
            pass
        self.root.after(100, self.run_async_tasks)

    async def server_main(self):
        server = NymServer()
        await server.connect_websocket()

if __name__ == "__main__":
    root = tk.Tk()
    gui = ServerGUI(root)
    root.mainloop()
