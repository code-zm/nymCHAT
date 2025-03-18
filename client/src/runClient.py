# runClient.py
import threading
import os
import asyncio
from nicegui import ui, app
from uuid import uuid4
from datetime import datetime

from dbUtils import SQLiteManager
from cryptographyUtils import CryptoUtils
from connectionUtils import MixnetConnectionClient
from messageHandler import MessageHandler
from logUtils import logger

###############################################################################
# GLOBAL / IN-MEMORY STATE
###############################################################################
DB_DIR = os.path.join(os.getcwd(), "storage")
usernames = []

chat_list = []        # [{"id": <username>, "name": <username>}]
active_chat = None    # currently active chat user ID
active_chat_user = None
messages = {}         # {username: [(sender_id, msg_text, timestamp), ...]}

chat_messages_container = None  # assigned in chat_page()

# Global variable for storing our nym address
global_nym_address = None

def set_active_chat(value):
    global active_chat
    active_chat = value

def get_active_chat():
    """Helper so we can pass this function to MessageHandler for checking which chat is active."""
    return active_chat

def set_active_chat_user(value):
    global active_chat_user
    active_chat_user = value

###############################################################################
# REFRESHABLE UI FOR CHAT
###############################################################################
@ui.refreshable
def render_chat_messages(current_user, target_chat, msg_dict):
    """
    Refresh the chat area to display messages properly, inside a structured column.
    """
    # Ensure chat_messages_container is defined
    if chat_messages_container is not None:
        chat_messages_container.clear()  # Clear old messages before re-rendering

    ui.label(f"Chat with {target_chat or ''}").classes('text-lg font-bold')

    if not target_chat or target_chat not in msg_dict or not msg_dict[target_chat]:
        ui.label('No messages yet.').classes('mx-auto my-4')
    else:
        with ui.column().classes('w-full max-w-6xl mx-auto items-stretch flex-grow gap-2'):
            for sender_id, text, stamp in msg_dict[target_chat]:
                is_sent = sender_id == current_user  # Check if the message is sent by the user

                # Handle multi-line messages
                text_content = text.split("\n") if "\n" in text else text

                ui.chat_message(
                    text=text_content,
                    stamp=stamp,
                    sent=is_sent
                ).classes('p-3 rounded-lg')

    ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')  # Auto-scroll to latest message

###############################################################################
# CREATE CORE OBJECTS
###############################################################################
crypto_utils = CryptoUtils()
connection_client = MixnetConnectionClient()
message_handler = MessageHandler(crypto_utils, connection_client)

###############################################################################
# UTILITY: SCAN FOR USERS, LOAD CHATS FROM DB, CONNECT TO MIXNET
###############################################################################
def scan_for_users():
    global usernames
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        logger.info("Created 'storage' directory for user data.")
        return

    dirs = [
        d for d in os.listdir(DB_DIR)
        if os.path.isdir(os.path.join(DB_DIR, d))
    ]
    usernames = dirs

def load_chats_from_db():
    """Load the chat_list and messages from DB for the current user."""
    global chat_list, messages
    chat_list.clear()
    messages.clear()

    active_username = message_handler.current_user["username"]
    if not message_handler.db_manager:
        logger.warning("DB manager not found; maybe not logged in yet.")
        return

    rows = message_handler.db_manager.conn.execute(
        f"SELECT DISTINCT username FROM messages_{active_username}"
    ).fetchall()

    # build chat_list
    for (contact_username,) in rows:
        chat_list.append({"id": contact_username, "name": contact_username})

    # load messages
    for info in chat_list:
        contact_username = info["id"]
        chat_msgs = message_handler.db_manager.get_messages_by_contact(
            active_username, contact_username
        )

        msg_list = []
        for (msg_type, msg_content, stamp) in chat_msgs:
            sender_id = active_username if msg_type == 'to' else contact_username
            msg_list.append((sender_id, msg_content, stamp))

        messages[contact_username] = msg_list

    logger.info("Chat list and messages loaded from DB.")

async def connect_mixnet():
    global global_nym_address
    logger.info("Initializing Mixnet client...")
    await connection_client.init()
    logger.info("Mixnet client initialized.")
    nym_address = await connection_client.get_nym_address()
    global_nym_address = nym_address
    # Update MessageHandler with our nym address
    message_handler.update_nym_address(nym_address)
    logger.info(f"My Nym Address: {nym_address}")
    main_loop = asyncio.get_running_loop()
    def message_callback(msg):
        logger.debug(f"Received raw message from server: {msg}")
        asyncio.run_coroutine_threadsafe(message_handler.handle_incoming_message(msg), main_loop)
    await connection_client.set_message_callback(message_callback)
    logger.info("Message callback set.")
    asyncio.create_task(connection_client.receive_messages())
    logger.info("Started message receiving loop.")
    ui.navigate.to("/welcome")  # Redirect to welcome page

###############################################################################
# OUTGOING MESSAGES
###############################################################################
async def send_message(text_input):
    if not active_chat or not text_input.value.strip():
        return

    msg_text = text_input.value.strip()
    text_input.value = ''
    current_user = message_handler.current_user["username"]

    # 1) Send direct message
    await message_handler.send_direct_message(active_chat_user, msg_text)

    # 2) Store in local memory
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if active_chat not in messages:
        messages[active_chat] = []
    messages[active_chat].append((current_user, msg_text, stamp))

    # 3) Re-render chat UI
    render_chat_messages.refresh(current_user, active_chat, messages)

async def send_handshake():
    """
    Native function to send a handshake (type 1 message) to the active chat user.
    """
    if not active_chat or not active_chat_user or not global_nym_address:
        return
    await message_handler.send_handshake(active_chat_user)

###############################################################################
# PAGE DEFINITIONS
###############################################################################
@ui.page('/')
def connect_page():
    with ui.column().classes('max-w-4xl mx-auto items-center flex flex-col justify-center h-screen'):
        ui.label("NymCHAT").classes("text-3xl font-bold mb-8")
        with ui.row().classes('justify-center w-full'):
            spin = ui.spinner(size='lg').props('hidden').classes("mb-4")
        
        async def do_connect():
            spin.props(remove='hidden')  # Show spinner
            await connect_mixnet()        # Connect to mixnet
            spin.props('hidden')          # Hide spinner
            ui.navigate.to("/welcome")    # Navigate to welcome page
        
        ui.button("Connect to Mixnet", color="green-6", on_click=do_connect, icon="wifi")

@ui.page('/welcome')
def welcome_page():
    with ui.column().classes('max-w-2xl mx-auto items-stretch flex-grow gap-1 flex justify-center items-center h-screen w-full'):
        ui.label("Welcome to NymCHAT").classes("text-3xl text-center font-bold mb-8")
        ui.button("Login", color="green-6", on_click=lambda: ui.navigate.to("/login"), icon="login").classes("mb-2")
        ui.button("Register", color="green-6", on_click=lambda: ui.navigate.to("/register"), icon="how_to_reg").classes("mb-2")

@ui.page('/login')
def login_page():
    with ui.column().classes('max-w-2xl mx-auto items-stretch flex-grow gap-1 flex justify-center items-center h-screen w-full'):
        ui.label("Login").classes("text-2xl text-center font-bold mb-4")
        
        scan_for_users()  # Load list of usernames

        if usernames:
            user_select = ui.select(usernames, label="Select a User").props("outlined").classes("mb-2")
            
            with ui.row().classes('justify-center w-full'):
                spin = ui.spinner(size='lg').props('hidden').classes("mb-4")

            async def do_login():
                if not user_select.value:
                    ui.notify("Please select a user.")
                    return
                spin.props(remove='hidden')  # Show spinner

                # Begin login process
                await message_handler.login_user(user_select.value)
                await message_handler.login_complete.wait()

                # Set up UI state and load chat data
                message_handler.set_ui_state(messages, chat_list, get_active_chat, render_chat_messages, chat_messages_container)
                load_chats_from_db()

                spin.props('hidden')  # Hide spinner

                if message_handler.login_successful:
                    ui.notify("Login successful! Welcome.")
                    ui.navigate.to("/app")
                else:
                    ui.notify("Login Failed: Did you delete your key file?")

            ui.button("Login", color="green-6", on_click=do_login, icon="login").classes("mb-2")
        else:
            ui.label("No users found. Please register first.")

        ui.button("Back", color="green-6", on_click=lambda: ui.navigate.to("/welcome"), icon="arrow_back_ios_new").classes("mb-2")

@ui.page('/register')
def register_page():
    with ui.column().classes('max-w-2xl mx-auto items-stretch flex-grow gap-1 flex justify-center items-center h-screen w-full'):
        ui.label("Register a New User").classes("text-2xl text-center font-bold mb-4")
        user_in = ui.input(label="Username").props("outlined").classes("mb-2")
        
        with ui.row().classes('justify-center w-full'):
            spin = ui.spinner(size='lg').props('hidden').classes("mb-4")
            
        async def do_register():
            username = user_in.value.strip()
            if not username:
                ui.notify("Username is required!")
                return

            spin.props(remove='hidden')
            await message_handler.register_user(username)
            await message_handler.registration_complete.wait()
            spin.props('hidden')

            if message_handler.registration_successful:
                ui.notify("Registration completed! Please login.")
                ui.navigate.to("/login")
            else:
                user_in.value = ""

        ui.button("Register", color="green-6", on_click=do_register, icon="how_to_reg").classes("mb-2")
        ui.button("Back", color="green-6", on_click=lambda: ui.navigate.to("/welcome"), icon="arrow_back_ios_new").classes("mb-2")

@ui.page('/app')
def chat_page():
    """
    Main chat page: toggleable chat list (sidebar), chat container, and message input.
    """
    user_id = message_handler.current_user["username"] or str(uuid4())

    global chat_messages_container  # Ensure accessibility

    chat_messages_container = ui.column().classes('flex-grow gap-2 overflow-auto')

    def show_new_message_notification(sender, message):
        with chat_messages_container:
            ui.notify(f"New message from {sender}: {message}")

    message_handler.new_message_callback = show_new_message_notification


    @ui.refreshable
    def chat_list_sidebar():
        with ui.column():
            ui.label('Chats').classes('text-xl font-bold')
            if not chat_list:
                ui.label('No chats yet').classes('text-gray-400')
            for info in chat_list:
                with ui.row().classes('p-2 hover:bg-gray-800 cursor-pointer') \
                        .on('click', lambda _, u=info: open_chat(u)):
                    ui.label(info["name"]).classes('font-bold text-white')
                    ui.label('Click to open chat').classes('text-gray-400 text-sm')

    def open_chat(u):
        set_active_chat(u["id"])
        set_active_chat_user(u["name"])
        chat_drawer.toggle()
        if chat_messages_container:
            render_chat_messages.refresh(user_id, active_chat, messages)

    with ui.left_drawer().classes('w-64 bg-zinc-700 text-white p-4') as chat_drawer:
        chat_list_sidebar()

    with ui.header().classes('w-full bg-zinc-800 text-white p-4 items-center justify-between'):
        with ui.row().classes('items-center gap-2'):
            ui.button(icon='menu', color="", on_click=lambda: chat_drawer.toggle())
            ui.label('NymCHAT').classes('text-xl font-bold')
            ui.button("Send Handshake", color="green-6", on_click=lambda: asyncio.create_task(send_handshake())).classes("ml-2")
        ui.button('Search', color="green-6", on_click=lambda: ui.navigate.to('/search'), icon="search") \
            .classes('bg-blue-500 text-white p-2 rounded') \
            .style('margin-left: auto; margin-right: auto;')
        with ui.element('q-fab').props('square icon=settings color=green-6 direction=left'):
            ui.element('q-fab-action').props('icon=logout color=green-6 label=LOGOUT') \
                .on('click', lambda: ui.navigate.to('/'))
            ui.element('q-fab-action').props('icon=power_settings_new color=green-6 label=SHUTDOWN') \
                .on('click', lambda: (app.shutdown(), ui.notify("Shutting down the app...")))

    message_handler.set_ui_state(messages, chat_list, get_active_chat, render_chat_messages, chat_messages_container, chat_list_sidebar)
    render_chat_messages(user_id, active_chat, messages)

    with ui.footer().classes('w-full bg-zinc-800 text-white p-4'):
        with ui.row().classes('w-full items-center'):
            text_in = ui.input(placeholder='Type a message...') \
                .props('rounded outlined input-class=mx-3') \
                .classes('flex-grow bg-zinc-700 text-white p-2 rounded-lg') \
                .on('keydown.enter', lambda: asyncio.create_task(send_message(text_in)))
            ui.button('Send', color="green-6", icon="send", on_click=lambda: asyncio.create_task(send_message(text_in))) \
                .classes('text-white p-2 rounded')

@ui.page('/search')
def search_page():
    with ui.header().classes('w-full bg-zinc-950 text-white p-4 justify-between'):
        ui.button('Back', color="green-6", icon="arrow_back_ios_new", on_click=lambda: ui.navigate.to('/app')).classes('text-white p-2 rounded')
    
    with ui.column().classes('w-full max-w-6xl mx-auto items-stretch flex-grow gap-1 w-full items-start p-4'):
        with ui.row().classes('gap-2 bg-zinc-800 p-4 rounded-lg shadow-lg w-full items-center justify-center'):
            search_in = ui.input(placeholder='Enter a username: *CASE SENSITIVE*') \
                .props('rounded outlined input-class=mx-3') \
                .classes('flex-grow bg-zinc-700 text-white p-2 rounded-lg') \
                .on('keydown.enter', lambda: asyncio.create_task(do_search()))
            ui.button('Search', color="green-6", icon="search", on_click=lambda: asyncio.create_task(do_search())).classes('text-white p-2 rounded')
        
        global profile_container
        profile_container = ui.column().classes('mt-4')
        
        async def do_search():
            username = search_in.value.strip()
            with profile_container:
                profile_container.clear()
                if not username:
                    ui.notify("Enter a username to search.")
                    return
                ui.notify(f"Searching for '{username}'...")
            result = await message_handler.query_user(username)
            with profile_container:
                if result is None:
                    ui.notify("Error or no response from server.")
                    return
                if isinstance(result, str):
                    ui.notify(result)
                elif isinstance(result, dict):
                    user_data = result
                    with ui.card().classes('p-4 bg-zinc-700 text-white rounded-lg shadow-lg w-80'):
                        ui.label(f"Username: {user_data.get('username') or 'N/A'}").classes('text-xl font-bold')
                        partial_key = (user_data.get('publicKey') or '')[:50]
                        ui.label(f"Public Key (partial): {partial_key}...")
                        def start_chat():
                            new_chat = {"id": user_data["username"], "name": user_data["username"]}
                            if new_chat not in chat_list:
                                chat_list.append(new_chat)
                            ui.navigate.to('/app')
                        ui.button('Start Chat', color='green-6', icon="chat", on_click=start_chat).classes('text-white p-2 mt-2 rounded')
                else:
                    ui.notify("Unexpected response format from server.")

###############################################################################
# APP STARTUP
###############################################################################
@app.on_startup
async def startup_sequence():
    # UI Setup
    message_handler.set_ui_state(
        messages,               # in-memory messages dict
        chat_list,              # in-memory chat_list
        get_active_chat,        # function to retrieve 'active_chat'
        render_chat_messages,   # our refreshable function
        chat_messages_container # container (if needed)
    )

def shutdown_client():
    # Create a new event loop in this thread and run the shutdown coroutine
    asyncio.run(connection_client.shutdown())

@app.on_shutdown
def on_shutdown():
    if connection_client.client is not None:
        logger.info("Shutting down Mixnet client...")
        t = threading.Thread(target=shutdown_client)
        t.start()
        t.join()  # Wait for shutdown to complete
        logger.info("Mixnet client shutdown complete.")
        
ui.run(dark=True, host='0.0.0.0', title="NymCHAT")
