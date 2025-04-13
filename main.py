import discord
from discord.ext import commands
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext, Listbox, filedialog, Menu
import threading
import asyncio
import os
import json
import re

class FriendBot(commands.Bot):
    def __init__(self, token, log_text, server_list, dm_list, channel_list, user_list, *args, **kwargs):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), *args, **kwargs)
        self.token = token
        self.log_text = log_text
        self.server_list = server_list
        self.dm_list = dm_list
        self.channel_list = channel_list
        self.user_list = user_list
        self.running = False
        self.selected_server = None
        self.selected_dm = None
        self.selected_channel = None
        self.bot_data_folder = None
        self.friends_file = None
        self.messages_file = None
        self.friends = {}
        self.messages = {}

    async def on_ready(self):
        print(f"Logged in as {self.user.name} ({self.user.id})")
        self.log_message(f"Logged in as {self.user.name} ({self.user.id})")
        self.running = True
        self.populate_servers()
        self.bot_data_folder = f"BotData/{self.user.name}"
        if not os.path.exists(self.bot_data_folder):
            os.makedirs(self.bot_data_folder)
        self.friends_file = os.path.join(self.bot_data_folder, "friends.json")
        self.messages_file = os.path.join(self.bot_data_folder, "messages.json")
        self.load_data()
        self.populate_dms()

    async def close(self):
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_message("Bot is closing and disconnecting...")
        self.running = False
        self.save_data()
        await super().close()

    def run_bot(self):
        try:
            self.run(self.token)
        except discord.LoginFailure:
            print("Invalid token provided.")
            self.log_message("Invalid token provided.")
        except Exception as e:
            print(f"Error running bot: {e}")
            self.log_message(f"Error running bot: {e}")
        finally:
            if self.running:
                asyncio.run_coroutine_threadsafe(self.close(), self.loop)

    def log_message(self, message):
        if self.log_text:
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except Exception as e:
                print(f"Error in log_message: {e}")
        else:
            print(message)

    def populate_servers(self):
        if self.server_list:
            self.server_list.delete(0, tk.END)
            for guild in self.guilds:
                self.server_list.insert(tk.END, f"{guild.name} ({guild.id})")

    def populate_channels(self, server_id):
        if self.channel_list:
            self.channel_list.delete(0, tk.END)
            self.selected_server = self.get_guild(server_id)
            if self.selected_server:
                for channel in self.selected_server.text_channels:
                    self.channel_list.insert(tk.END, f"{channel.name} ({channel.id})")

    def populate_dms(self):
        if self.dm_list:
            self.dm_list.delete(0, tk.END)
            for user_id, friend_status in self.friends.items():
                if friend_status == "friends":
                    user = self.get_user(int(user_id))
                    if user:
                        self.dm_list.insert(tk.END, f"{user.name} ({user.id})")

    def populate_users(self, channel_id):
        if self.user_list:
            self.user_list.delete(0, tk.END)
            channel = self.get_channel(channel_id)
            if channel:
                for member in channel.members:
                    self.user_list.insert(tk.END, f"{member.name} ({member.id})")

    async def send_friend_request(self, user_id):
        try:
            user = await self.fetch_user(user_id)
            channel = await user.create_dm()
            await channel.send(f"Hello! I'm {self.user.name}, a bot, and I'd like to be your friend.  Please respond with 'yes' to accept.")
            self.log_message(f"Sent a friend request to user {user.name} ({user_id})")
        except discord.NotFound:
            self.log_message(f"User with ID {user_id} not found.")
        except discord.Forbidden:
            self.log_message(f"Could not open a DM with user {user_id}.")
        except Exception as e:
            self.log_message(f"Error sending friend request: {e}")

    async def send_message_to_channel(self, channel, content, file_paths=None):
        try:
            if not file_paths:
                file_paths = []

            if len(file_paths) > 10:
                self.log_message("Cannot attach more than 10 files.")
                return

            files = [discord.File(fp) for fp in file_paths]

            await channel.send(content=content[:2000], files=files)  # Truncate message
            self.log_message(f"Sent message to channel {channel.name}: {content[:2000]}")  # Truncated message
            self.save_message(channel.id, self.user.id, content)
        except Exception as e:
            self.log_message(f"Error sending message: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if isinstance(message.channel, discord.DMChannel) and message.content.lower() == "yes":
            self.friends[str(message.author.id)] = "friends"
            self.populate_dms()
            self.log_message(f"User {message.author.name} ({message.author.id}) accepted friend request.")

        self.save_message(message.channel.id, message.author.id, message.content)

    def load_data(self):
        try:
            with open(self.friends_file, "r") as f:
                self.friends = json.load(f)
        except FileNotFoundError:
            self.friends = {}
        try:
            with open(self.messages_file, "r") as f:
                self.messages = json.load(f)
        except FileNotFoundError:
            self.messages = {}

    def save_data(self):
        with open(self.friends_file, "w") as f:
            json.dump(self.friends, f)
        with open(self.messages_file, "w") as f:
            json.dump(self.messages, f)

    def save_message(self, channel_id, user_id, message_content):
        channel_id = str(channel_id)
        if channel_id not in self.messages:
            self.messages[channel_id] = []
        self.messages[channel_id].append({"user_id": user_id, "content": message_content})

class ChatWindow(tk.Toplevel):  # Separate class for Chat Window
    def __init__(self, parent, bot, channel_id, view_profile_callback, user_id=None):
        super().__init__(parent)
        self.title("Message UI")
        self.geometry("800x600")

        self.bot = bot
        self.channel_id = str(channel_id)
        self.user_id = user_id
        self.parent = parent
        self.view_profile_callback = view_profile_callback #Call the callback function instead of accessing the GUI

        self.messages_text = scrolledtext.ScrolledText(self, width=80, height=20)
        self.messages_text.pack(pady=5, padx=5, fill="both", expand=True)
        self.messages_text.config(state=tk.DISABLED)
        self.messages_text.bind("<Button-3>", self.on_message_right_click)

        self.chatbox_label = tk.Label(self, text="Chat:")
        self.chatbox_label.pack(pady=5, padx=5)

        self.chatbox_entry = tk.Entry(self, width=70)
        self.chatbox_entry.pack(pady=5, padx=5, fill="x")

        self.file_paths = []
        self.attached_files_label = tk.Label(self, text="Attached Files: None")
        self.attached_files_label.pack(pady=5, padx=5)

        self.attach_file_button = tk.Button(self, text="Attach File", command=self.attach_file)
        self.attach_file_button.pack(pady=5, padx=5)

        self.send_button = tk.Button(self, text="Send", command=self.send_message)
        self.send_button.pack(pady=5, padx=5)

        self.load_messages()
        self.after(3500, self.update_messages) #Call update messages loop

    def load_messages(self):
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.delete("1.0", tk.END)

        if self.channel_id in self.bot.messages:
            for msg in self.bot.messages[self.channel_id]:
                try:
                    user = self.bot.get_user(int(msg["user_id"]))
                    if user:
                        self.messages_text.insert(tk.END, f"{user.name}: {msg['content']}\n")
                    else:
                        self.messages_text.insert(tk.END, f"Unknown User ({msg['user_id']}): {msg['content']}\n")
                except Exception as e:
                    print(f"Error displaying message: {e}")

        self.messages_text.config(state=tk.DISABLED)

    def attach_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            if len(self.file_paths) < 10:
                self.file_paths.append(file_path)
                self.update_attached_files_label()
            else:
                messagebox.showinfo("Info", "Cannot attach more than 10 files.")

    def update_attached_files_label(self):
        if self.file_paths:
            self.attached_files_label.config(text=f"Attached Files: {', '.join([os.path.basename(fp) for fp in self.file_paths])}")
        else:
            self.attached_files_label.config(text="Attached Files: None")

    def send_message(self):
        message_content = self.chatbox_entry.get()
        if not message_content:
            return

        channel = self.bot.get_channel(int(self.channel_id))
        if channel is None:
            user = self.bot.get_user(self.user_id)
            if user:
                channel = user.dm_channel
                if channel is None:
                    asyncio.run_coroutine_threadsafe(user.create_dm(), self.bot.loop)
                    channel = user.dm_channel

        if channel:
            asyncio.run_coroutine_threadsafe(self.bot.send_message_to_channel(channel, message_content, self.file_paths), self.bot.loop)
            self.chatbox_entry.delete(0, tk.END)
            self.file_paths = []
            self.update_attached_files_label()
            self.load_messages() #Reload messages after sending
        else:
            messagebox.showinfo("Error", "Could not find the channel.")

    def update_messages(self):
        self.load_messages() #Reload messsages
        self.after(3500, self.update_messages) #Restart timeout for 3.5 seconds

    def on_message_right_click(self, event):
        try:
            index = self.messages_text.index("@%s,%s" % (event.x, event.y))
            line_start = int(float(index))
            message_line = self.messages_text.get(f"{line_start}.0", f"{line_start+1}.0")

            user_id_search = re.search(r'\((\d+)\):', message_line)

            if user_id_search:
                user_id = int(user_id_search.group(1))

                menu = Menu(self, tearoff=0)
                menu.add_command(label="View Profile", command=lambda: self.view_profile(user_id))
                menu.tk_popup(event.x_root, event.y_root, 0)
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def view_profile(self, user_id):
        if self.view_profile_callback: #Call the callback and view the profile
            self.view_profile_callback(user_id)

import re

class BotGUI:
    def __init__(self, loop):
        self.root = tk.Tk()
        self.root.title("Simple Bot Control")
        self.root.geometry("1200x700")

        self.loop = loop
        self.bot = None
        self.saved_tokens = self.load_saved_tokens()

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # Main Tab
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main")

        # UI Elements
        self.token_label = tk.Label(self.main_tab, text="Bot Token:")
        self.token_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.token_entry = tk.Entry(self.main_tab, width=50)
        self.token_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        self.token_dropdown_var = tk.StringVar(self.main_tab)
        self.token_dropdown_var.set("Select Bot")

        # Fix: Create OptionMenu *after* defining the variable and with a default value
        self.token_dropdown = tk.OptionMenu(self.main_tab, self.token_dropdown_var, "Select Bot", *list(self.saved_tokens.keys()), command=self.load_token)
        self.token_dropdown.grid(row=0, column=2, sticky="w", padx=5, pady=5)

        #Top Buttons
        self.add_by_id_button = tk.Button(self.main_tab, text="Add by ID", command=self.add_friend_by_id)
        self.add_by_id_button.grid(row=0, column=3, pady=5)

        self.server_list_label = tk.Label(self.main_tab, text="Servers:")
        self.server_list_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.server_list = Listbox(self.main_tab, width=30, height=20)
        self.server_list.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        self.server_list.bind("<<ListboxSelect>>", self.on_server_select)

        self.dm_list_label = tk.Label(self.main_tab, text="DMs/Friends:")
        self.dm_list_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.dm_list = Listbox(self.main_tab, width=30, height=20)
        self.dm_list.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")
        self.dm_list.bind("<Button-3>", self.on_dm_right_click)  # Right-click event
        self.dm_list.bind("<<ListboxSelect>>", self.on_dm_select)

        self.channel_list_label = tk.Label(self.main_tab, text="Channels:")
        self.channel_list_label.grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.channel_list = Listbox(self.main_tab, width=30, height=20)
        self.channel_list.grid(row=2, column=2, padx=5, pady=5, sticky="nsew")
        self.channel_list.bind("<Button-3>", self.on_channel_right_click)
        self.channel_list.bind("<<ListboxSelect>>", self.on_channel_select)

        self.user_list_label = tk.Label(self.main_tab, text="Users:")
        self.user_list_label.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        self.user_list = Listbox(self.main_tab, width=30, height=20)
        self.user_list.grid(row=2, column=3, padx=5, pady=5, sticky="nsew")
        self.user_list.bind("<Button-3>", self.on_user_right_click)

        self.log_label = tk.Label(self.main_tab, text="Log:")
        self.log_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.log_text = scrolledtext.ScrolledText(self.main_tab, width=100, height=10)
        self.log_text.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        self.log_text.config(state=tk.DISABLED)

        # Buttons
        self.start_button = tk.Button(self.main_tab, text="Start Bot", command=self.start_bot)
        self.start_button.grid(row=5, column=0, pady=10)
        self.stop_button = tk.Button(self.main_tab, text="Stop Bot", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.grid(row=5, column=1, pady=10)

        self.message_button = tk.Button(self.main_tab, text="Message", command=self.open_message_ui)
        self.message_button.grid(row=5, column=2, pady=10)

        # Configure row and column weights for resizing
        for i in range(6):
            self.main_tab.grid_rowconfigure(i, weight=0)
        self.main_tab.grid_rowconfigure(4, weight=1)
        self.main_tab.grid_columnconfigure(0, weight=1)
        self.main_tab.grid_columnconfigure(1, weight=1)
        self.main_tab.grid_columnconfigure(2, weight=1)
        self.main_tab.grid_columnconfigure(3, weight=1)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def start_bot(self):
        token = self.token_entry.get()
        if not token:
            messagebox.showerror("Error", "Please enter a bot token.")
            return

        if self.bot is not None:
            messagebox.showinfo("Info", "Bot is already running. Stop it first.")
            return

        self.save_token(self.token_dropdown_var.get(), token)

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

        self.bot = FriendBot(token, self.log_text, self.server_list, self.dm_list, self.channel_list, self.user_list)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        threading.Thread(target=self.bot.run_bot).start()

    def stop_bot(self):
        if self.bot is None:
            messagebox.showinfo("Info", "Bot is not running.")
            return

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        asyncio.run_coroutine_threadsafe(self.bot.close(), self.loop)

    def on_closing(self):
        if self.bot:
            asyncio.run_coroutine_threadsafe(self.bot.close(), self.loop)

        self.root.destroy()
        os._exit(0)

    def on_server_select(self, event):
        selection = self.server_list.curselection()
        if selection:
            server_info = self.server_list.get(selection[0])
            server_id = int(server_info.split("(")[1].split(")")[0])
            self.bot.populate_channels(server_id)

    def on_dm_select(self, event):
        pass

    def on_channel_select(self, event):
        try:
            channel_info = self.channel_list.get(self.channel_list.curselection()[0])
            channel_id = int(channel_info.split("(")[1].split(")")[0])
            self.bot.populate_users(channel_id)
        except IndexError:
            pass


    def on_dm_right_click(self, event):
        pass

    def on_channel_right_click(self, event):
        try:
            selection = self.channel_list.curselection()
            if selection:
                channel_info = self.channel_list.get(selection[0])
                channel_id = int(channel_info.split("(")[1].split(")")[0])

                menu = Menu(self.root, tearoff=0)
                menu.add_command(label="Message", command=lambda: self.open_message_ui(channel_id=channel_id))
                menu.add_command(label="Users", command=lambda: self.on_users_button(channel_id)) #Now calls on_users_button
                menu.tk_popup(event.x_root, event.y_root, 0)
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def on_user_right_click(self, event):
        try:
            selection = self.user_list.curselection()
            if selection:
                user_info = self.user_list.get(selection[0])
                user_id = int(user_info.split("(")[1].split(")")[0])

                menu = Menu(self.root, tearoff=0)
                menu.add_command(label="View Profile", command=lambda: self.view_profile(user_id))
                menu.tk_popup(event.x_root, event.y_root, 0)
        except Exception as e:
            print(f"Error showing context menu: {e}")


    def load_saved_tokens(self):
        try:
            with open("saved_tokens.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_token(self, bot_name, token):
        if not bot_name or bot_name == "Select Bot":
            bot_name = simpledialog.askstring("Bot Name", "Enter a name for this bot:")
            if not bot_name:
                return
        self.saved_tokens[bot_name] = token
        with open("saved_tokens.json", "w") as f:
            json.dump(self.saved_tokens, f)
        self.update_token_dropdown()

    def load_token(self, bot_name):
        if bot_name in self.saved_tokens:
            self.token_entry.delete(0, tk.END)
            self.token_entry.insert(0, self.saved_tokens[bot_name])

    def update_token_dropdown(self):
        menu = self.token_dropdown["menu"]
        menu.delete(0, "end")
        for bot_name in self.saved_tokens:
            menu.add_command(label=bot_name, command=lambda value=bot_name: self.load_token(value))

    def open_message_ui(self, channel_id=None):
       if channel_id is None:
           if self.bot.selected_server and self.bot.selected_channel:
               try:
                   channel_id = self.bot.channel_list.get(self.bot.channel_list.curselection()[0]).split("(")[1].split(")")[0]
               except IndexError:
                   self.log_message("No channel selected.")
                   return
           elif self.bot.selected_dm:
               user = self.bot.get_user(self.bot.selected_dm)
               if user and user.dm_channel:
                   channel_id = user.dm_channel.id
               else:
                   self.log_message("Could not find DM channel.")
                   return
       if channel_id:
           ChatWindow(self.root, self.bot, channel_id, self.view_profile)

    def log_message(self, message):
        if self.log_text:
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except Exception as e:
                print(f"Error in log_message: {e}")
        else:
            print(message)

    def on_users_button(self, channel_id):
        self.bot.populate_users(channel_id) #Call the bot to populate users
        #self.notebook.select(self.main_tab) #Shows main tab
        self.notebook.select(self.main_tab) #Select back to the main tab
        self.log_message("Users button is clicked")

    def view_profile(self, user_id): #Now doesn't have async
        asyncio.run_coroutine_threadsafe(self.get_and_show_profile(user_id), self.loop) #Calls to get the data

    async def get_and_show_profile(self, user_id): #We only use this to get and show the profile.
        try:
            user = await self.bot.fetch_user(user_id) #Gets the user and waits for the info
            if user:
                profile_info = f"Name: {user.name}\nID: {user.id}\nStatus: {user.status}\nCreated At: {user.created_at}\n" #We get the info for the status
                messagebox.showinfo("Profile", profile_info) #We make the message show up after.

        except discord.NotFound:
            self.log_message(f"User with ID {user_id} not found.")
        except Exception as e:
            self.log_message(f"Error getting user data: {e}")

    def add_friend_by_id(self): #Add friend by ID
        user_id = simpledialog.askstring("Add User", "Enter User ID:") #Ask for the ID
        if user_id:
          try:
            user_id = int(user_id)
            asyncio.run_coroutine_threadsafe(self.bot.send_friend_request(user_id), self.loop) #Call the bot to send the request
            self.log_message(f"Sending friend request to {user_id}")
          except ValueError:
            messagebox.showinfo("Error", "Not a valid user ID.")
          except Exception as e:
            self.log_message(f"Error sending friend request: {e}")


    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    gui = BotGUI(loop)
    gui.run()