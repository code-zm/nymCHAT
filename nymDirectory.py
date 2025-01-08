# NymDirectory: Remailer / Directory Service used by NymChat Clients.
# Copyright (C) 2025 code-zm
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


import asyncio
import json
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import websockets


class RemailerApp:
    """Remailer Server with GUI integration."""

    def __init__(self, root, websocketUrl="ws://127.0.0.1:1977"):
        self.root = root
        self.websocketUrl = websocketUrl
        self.websocket = None
        self.directory = {}

        # GUI setup
        self.root.title("Nym Server")

        # Directory display
        self.directoryLabel = tk.Label(root, text="Directory:")
        self.directoryLabel.pack(pady=5)

        self.directoryDisplay = ScrolledText(root, state='disabled', width=50, height=10)
        self.directoryDisplay.pack(pady=5)

        # Messages display
        self.messagesLabel = tk.Label(root, text="Messages:")
        self.messagesLabel.pack(pady=5)

        self.messagesDisplay = ScrolledText(root, state='disabled', width=50, height=10)
        self.messagesDisplay.pack(pady=5)

        # Asyncio loop
        self.loop = asyncio.get_event_loop()

        # Schedule the asyncio task to start
        self.root.after(100, self.startAsyncLoop)

    def updateDirectory(self):
        """Update the directory display."""
        self.directoryDisplay.config(state='normal')
        self.directoryDisplay.delete('1.0', tk.END)
        for pseudonym, senderTag in self.directory.items():
            self.directoryDisplay.insert(tk.END, f"{pseudonym} -> {senderTag}\n")
        self.directoryDisplay.config(state='disabled')

    def updateMessages(self, message):
        """Update the messages display."""
        self.messagesDisplay.config(state='normal')
        self.messagesDisplay.insert(tk.END, f"{message}\n")
        self.messagesDisplay.config(state='disabled')

    async def connectWebsocket(self):
        """Establish a WebSocket connection with the Nym client."""
        try:
            self.websocket = await websockets.connect(self.websocketUrl)
            await self.websocket.send(json.dumps({"type": "selfAddress"}))
            response = await self.websocket.recv()
            data = json.loads(response)
            selfAddress = data.get("address")
            print("Connected to WebSocket. Your Nym Address:", selfAddress)
            self.updateMessages(f"Connected to Nym Mixnet. Address: {selfAddress}")

            await self.receiveMessages()  # Start listening for incoming messages
        except Exception as e:
            print("Connection error:", e)
            self.updateMessages(f"Connection error: {e}")

    async def receiveMessages(self):
        """Listen for incoming messages."""
        try:
            while True:
                rawMessage = await self.websocket.recv()
                try:
                    data = json.loads(rawMessage)
                    print(f"Received message: {data}")
                    await self.processMessage(data)
                except json.JSONDecodeError as e:
                    print(f"Error decoding message: {e}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed.")
            self.updateMessages("WebSocket connection closed.")

    async def processMessage(self, data):
        """Process parsed JSON messages."""
        if data["type"] == "received":
            receivedMessage = data.get("message", "")
            senderTag = data.get("senderTag", None)

            try:
                parsedMessage = json.loads(receivedMessage)
                method = parsedMessage.get("method")
            except json.JSONDecodeError as e:
                print(f"Error parsing encapsulated message: {e}")
                self.updateMessages(f"Error parsing message: {e}")
                return

            if method == "register":
                pseudonym = parsedMessage.get("content", "")
                print(f"Register request: pseudonym='{pseudonym}', senderTag='{senderTag}'")
                self.directory[pseudonym] = senderTag
                self.updateDirectory()
                self.updateMessages(f"Registered pseudonym: {pseudonym}")
            elif method == "query":
                pseudonym = parsedMessage.get("pseudonym", "")
                content = parsedMessage.get("content", "")
                print(f"Query request: pseudonym='{pseudonym}', content='{content}', senderTag='{senderTag}'")
                await self.handleQuery(pseudonym, content)
            else:
                print(f"Unhandled method: {method}")
                self.updateMessages(f"Unhandled method: {method}")
        else:
            print(f"Unhandled message type: {data['type']}")
            self.updateMessages(f"Unhandled message type: {data['type']}")

    async def handleQuery(self, pseudonym, content):
        """Handle query messages."""
        if pseudonym in self.directory:
            senderTag = self.directory[pseudonym]
            print(f"Replying to query: pseudonym='{pseudonym}', content='{content}', senderTag='{senderTag}'")

            # Construct the reply message
            replyMessage = {
                "type": "reply",
                "message": content,
                "senderTag": senderTag
            }

            # Send the reply message
            try:
                await self.websocket.send(json.dumps(replyMessage))
                self.updateMessages(f"Replied to {pseudonym}: {content}")
                print(f"Sent reply: {replyMessage}")
            except Exception as e:
                print(f"Error sending reply: {e}")
                self.updateMessages(f"Error sending reply: {e}")
        else:
            print(f"Pseudonym '{pseudonym}' not found in directory.")
            self.updateMessages(f"Pseudonym '{pseudonym}' not found in directory.")

    def startAsyncLoop(self):
        """Start the asyncio loop."""
        self.loop.create_task(self.connectWebsocket())
        self.checkAsyncioLoop()

    def checkAsyncioLoop(self):
        """Run the asyncio loop periodically."""
        self.loop.stop()
        self.loop.run_forever()
        self.root.after(100, self.checkAsyncioLoop)


if __name__ == "__main__":
    root = tk.Tk()
    app = RemailerApp(root)
    root.mainloop()
