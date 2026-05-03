"""
Kivy UI module for Universal Connectivity Python Peer

This module provides a modern mobile-friendly UI using Kivy and KivyMD.
It works with the headless service and uses queues for communication.
Design inspired by WhatsApp/Telegram for a familiar chat experience.
"""

import os
# Disable Kivy argument parsing to avoid conflicts with our app's arguments
os.environ['KIVY_NO_ARGS'] = '1'

import json
import logging
import time
import threading
from queue import Empty
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

from kivymd.app import MDApp
from kivymd.uix.list import OneLineAvatarIconListItem, IconLeftWidget, IconRightWidget
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDIconButton, MDFlatButton, MDRaisedButton
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.navigationdrawer import MDNavigationDrawer, MDNavigationDrawerMenu
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.filemanager import MDFileManager

logger = logging.getLogger("kivy_ui")

# File message prefix (must match headless.py)
FILE_MESSAGE_PREFIX = "[FILE]"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class MessageBubble(MDCard):
    """A message bubble similar to WhatsApp/Telegram."""
    
    def __init__(self, message: str, sender: str, is_self: bool = False, timestamp: str = "", **kwargs):
        super().__init__(**kwargs)
        
        # Set bubble properties
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(80)
        self.padding = dp(10)
        self.spacing = dp(5)
        
        # Set different colors for sent/received messages
        if is_self:
            self.md_bg_color = (0.85, 0.95, 0.85, 1)  # Light green for sent
            self.pos_hint = {'right': 0.98}
            self.size_hint_x = 0.75
        else:
            self.md_bg_color = (1, 1, 1, 1)  # White for received
            self.pos_hint = {'x': 0.02}
            self.size_hint_x = 0.75
        
        # Sender label (only for received messages)
        if not is_self:
            sender_label = MDLabel(
                text=sender,
                font_style='Caption',
                theme_text_color='Secondary',
                size_hint_y=None,
                height=dp(15)
            )
            self.add_widget(sender_label)
        
        # Message content
        message_label = MDLabel(
            text=message,
            size_hint_y=None,
            height=dp(40)
        )
        self.add_widget(message_label)
        
        # Timestamp
        time_label = MDLabel(
            text=timestamp,
            font_style='Caption',
            theme_text_color='Hint',
            size_hint_y=None,
            height=dp(15),
            halign='right'
        )
        self.add_widget(time_label)


class FileBubble(MDCard):
    """A file sharing bubble displayed in chat for shared/received files."""
    
    def __init__(self, filename: str, filesize: int, file_cid: str, sender: str,
                 is_self: bool = False, timestamp: str = "", on_download=None, **kwargs):
        super().__init__(**kwargs)
        
        self.file_cid = file_cid
        self.filename = filename
        self.filesize = filesize
        self.on_download_callback = on_download
        
        # Set bubble properties
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(120)
        self.padding = dp(10)
        self.spacing = dp(5)
        self.radius = [dp(10)]
        
        # Set different colors for sent/received
        if is_self:
            self.md_bg_color = (0.8, 0.93, 0.8, 1)  # Light green for sent
            self.pos_hint = {'right': 0.98}
            self.size_hint_x = 0.8
        else:
            self.md_bg_color = (1, 1, 1, 1)  # White for received
            self.pos_hint = {'x': 0.02}
            self.size_hint_x = 0.8
        
        # Sender label (only for received)
        if not is_self:
            sender_label = MDLabel(
                text=sender,
                font_style='Caption',
                theme_text_color='Secondary',
                size_hint_y=None,
                height=dp(15)
            )
            self.add_widget(sender_label)
        
        # File info row
        file_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(50),
            spacing=dp(10)
        )
        
        # File icon
        file_icon = MDIconButton(
            icon="file",
            theme_icon_color="Custom",
            icon_color=(0.2, 0.6, 0.2, 1),
            disabled=True
        )
        file_row.add_widget(file_icon)
        
        # File details
        file_details = BoxLayout(
            orientation='vertical',
            spacing=dp(2)
        )
        
        name_label = MDLabel(
            text=filename,
            font_style='Body2',
            bold=True,
            size_hint_y=None,
            height=dp(22)
        )
        file_details.add_widget(name_label)
        
        size_label = MDLabel(
            text=format_file_size(filesize),
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(18)
        )
        file_details.add_widget(size_label)
        
        file_row.add_widget(file_details)
        self.add_widget(file_row)
        
        # Download button (only for received files)
        if not is_self and on_download:
            self.download_btn = MDRaisedButton(
                text="Download",
                size_hint=(None, None),
                size=(dp(120), dp(36)),
                pos_hint={'center_x': 0.5},
                on_release=lambda x: self._on_download_pressed()
            )
            self.add_widget(self.download_btn)
        elif is_self:
            status_label = MDLabel(
                text="Shared",
                font_style='Caption',
                theme_text_color='Custom',
                text_color=(0.2, 0.7, 0.2, 1),
                halign='center',
                size_hint_y=None,
                height=dp(20)
            )
            self.add_widget(status_label)
        
        # Timestamp
        time_label = MDLabel(
            text=timestamp,
            font_style='Caption',
            theme_text_color='Hint',
            size_hint_y=None,
            height=dp(15),
            halign='right'
        )
        self.add_widget(time_label)
    
    def _on_download_pressed(self):
        """Handle download button press."""
        if self.on_download_callback:
            # Disable button to prevent double-click
            if hasattr(self, 'download_btn'):
                self.download_btn.text = "Downloading..."
                self.download_btn.disabled = True
            self.on_download_callback(self.file_cid, self.filename)
    
    def mark_downloaded(self, save_path: str = ""):
        """Update bubble to show download is complete."""
        if hasattr(self, 'download_btn'):
            self.download_btn.text = "Downloaded"
            self.download_btn.disabled = True
            self.download_btn.md_bg_color = (0.2, 0.7, 0.2, 1)


class ChatScreen(Screen):
    """Chat screen for a specific topic conversation."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        self.message_queue = headless_service.get_message_queue()
        self.system_queue = headless_service.get_system_queue()
        self.connection_info = headless_service.get_connection_info()
        self.current_topic = None  # The topic this chat screen is currently showing
        self.file_bubbles = {}  # Track file bubbles by CID for download status updates
        
        # File manager for picking files
        self.file_manager = MDFileManager(
            exit_manager=self._exit_file_manager,
            select_path=self._on_file_selected,
            preview=False,
        )
        self.file_manager_open = False
        
        # Main layout
        layout = BoxLayout(orientation='vertical')
        
        # Top app bar
        self.toolbar = MDTopAppBar(
            title="Select a Topic",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            right_action_items=[
                ["information", lambda x: self.show_info()]
            ],
            elevation=2
        )
        layout.add_widget(self.toolbar)
        
        # Messages container
        self.messages_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None
        )
        self.messages_layout.bind(minimum_height=self.messages_layout.setter('height'))
        
        # Scroll view for messages
        self.scroll = MDScrollView()
        self.scroll.add_widget(self.messages_layout)
        layout.add_widget(self.scroll)
        
        # Input area
        input_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            padding=dp(10),
            spacing=dp(5)
        )
        
        # File attachment button
        self.attach_btn = MDIconButton(
            icon="paperclip",
            on_release=self.open_file_picker,
            disabled=True
        )
        input_layout.add_widget(self.attach_btn)
        
        # Text input
        self.message_input = MDTextField(
            hint_text="Select a topic first...",
            multiline=False,
            size_hint_x=0.75,
            disabled=True
        )
        self.message_input.bind(on_text_validate=self.send_message)
        input_layout.add_widget(self.message_input)
        
        # Send button
        self.send_btn = MDIconButton(
            icon="send",
            on_release=self.send_message,
            disabled=True
        )
        input_layout.add_widget(self.send_btn)
        
        layout.add_widget(input_layout)
        
        self.add_widget(layout)
        
        # Start queue checking
        Clock.schedule_interval(self.check_queues, 0.1)
    
    def go_back(self):
        """Go back to topics list."""
        self.manager.current = 'topics'
    
    def set_topic(self, topic: str):
        """
        Set the topic for this chat screen and load its messages.
        
        Args:
            topic: The topic name to display
        """
        self.current_topic = topic
        self.toolbar.title = f"# {topic}"
        self.message_input.hint_text = f"Message in {topic}..."
        self.message_input.disabled = False
        self.send_btn.disabled = False
        self.attach_btn.disabled = False
        
        # Mark topic as read
        self.headless_service.mark_topic_as_read(topic)
        
        # Clear and reload messages
        self.messages_layout.clear_widgets()
        self.load_topic_messages()
    
    def load_topic_messages(self):
        """Load all messages for the current topic."""
        if not self.current_topic:
            return
        
        messages = self.headless_service.get_topic_messages(self.current_topic)
        our_peer_id = self.connection_info.get('peer_id', '')
        
        for msg_data in messages:
            sender_id = msg_data['sender_id']
            sender_nick = msg_data['sender_nick']
            timestamp = time.strftime("%H:%M", time.localtime(msg_data['timestamp']))
            is_self = (sender_id == our_peer_id or sender_id == "self")
            
            msg_type = msg_data.get('type', 'chat_message')
            
            if msg_type == 'file_message':
                # Render as file bubble
                file_cid = msg_data.get('file_cid', '')
                file_name = msg_data.get('file_name', 'unknown')
                file_size = msg_data.get('file_size', 0)
                
                self.add_file_bubble(
                    filename=file_name,
                    filesize=file_size,
                    file_cid=file_cid,
                    sender=sender_nick,
                    is_self=is_self,
                    timestamp=timestamp
                )
            else:
                message = msg_data['message']
                self.add_message_bubble(message, sender_nick, is_self=is_self, timestamp=timestamp)
    
    def send_message(self, *args):
        """Send a message to the current topic."""
        if not self.current_topic:
            return
        
        message = self.message_input.text.strip()
        
        if not message:
            return
        
        # Clear input
        self.message_input.text = ""
        
        # Handle commands
        if message.startswith("/"):
            self.handle_command(message)
            return
        
        # Send message through headless service
        try:
            self.headless_service.send_message_to_topic(self.current_topic, message)
            logger.info(f"Sending message to topic {self.current_topic}: {message}")
            
            # Display message immediately as sent
            timestamp = time.strftime("%H:%M")
            self.add_message_bubble(message, "You", is_self=True, timestamp=timestamp)
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.show_system_message(f"Error: {e}")
    
    def handle_command(self, command: str):
        """Handle special commands."""
        cmd = command.lower().strip()
        
        if cmd in ["/quit", "/exit"]:
            MDApp.get_running_app().stop()
        elif cmd == "/status":
            self.show_info()
        else:
            self.show_system_message(f"Unknown command: {command}")
    
    def check_queues(self, dt):
        """Check message queues for new messages for the current topic."""
        # Check message queue
        try:
            while True:
                try:
                    message_data = self.message_queue.sync_q.get_nowait()
                    msg_type = message_data.get('type', '')
                    
                    if msg_type == 'chat_message':
                        # Only show messages for the current topic
                        msg_topic = message_data.get('topic', 'default')
                        if msg_topic != self.current_topic:
                            continue
                        
                        sender_nick = message_data['sender_nick']
                        sender_id = message_data['sender_id']
                        msg = message_data['message']
                        
                        # Don't display our own messages again
                        our_peer_id = self.connection_info.get('peer_id', '')
                        if sender_id != our_peer_id and sender_id != "self":
                            timestamp = time.strftime("%H:%M")
                            self.add_message_bubble(msg, sender_nick, is_self=False, timestamp=timestamp)
                    
                    elif msg_type == 'file_message':
                        # Received a file sharing message from another peer
                        msg_topic = message_data.get('topic', 'default')
                        if msg_topic != self.current_topic:
                            continue
                        
                        sender_id = message_data.get('sender_id', '')
                        our_peer_id = self.connection_info.get('peer_id', '')
                        if sender_id != our_peer_id and sender_id != "self":
                            timestamp = time.strftime("%H:%M")
                            self.add_file_bubble(
                                filename=message_data.get('file_name', 'unknown'),
                                filesize=message_data.get('file_size', 0),
                                file_cid=message_data.get('file_cid', ''),
                                sender=message_data.get('sender_nick', 'Unknown'),
                                is_self=False,
                                timestamp=timestamp
                            )
                    
                    elif msg_type == 'file_shared':
                        # Our own file was successfully shared
                        msg_topic = message_data.get('topic', 'default')
                        if msg_topic != self.current_topic:
                            continue
                        
                        timestamp = time.strftime("%H:%M")
                        self.add_file_bubble(
                            filename=message_data.get('file_name', 'unknown'),
                            filesize=message_data.get('file_size', 0),
                            file_cid=message_data.get('file_cid', ''),
                            sender='You',
                            is_self=True,
                            timestamp=timestamp
                        )
                    
                    elif msg_type == 'file_downloaded':
                        # File download completed
                        file_cid = message_data.get('file_cid', '')
                        save_path = message_data.get('save_path', '')
                        file_name = message_data.get('file_name', 'unknown')
                        
                        # Update the file bubble if it exists
                        if file_cid in self.file_bubbles:
                            self.file_bubbles[file_cid].mark_downloaded(save_path)
                        
                        # Show download notification
                        self._show_download_notification(file_name, save_path)
                    
                    elif msg_type == 'file_download_failed':
                        # File download failed
                        file_cid = message_data.get('file_cid', '')
                        file_name = message_data.get('file_name', 'unknown')
                        error = message_data.get('error', 'Unknown error')
                        
                        # Re-enable download button
                        if file_cid in self.file_bubbles:
                            bubble = self.file_bubbles[file_cid]
                            if hasattr(bubble, 'download_btn'):
                                bubble.download_btn.text = "Retry"
                                bubble.download_btn.disabled = False
                        
                        self.show_system_message(f"Download failed: {file_name} - {error}")
                        
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error checking message queue: {e}")
        
        # Check system queue
        try:
            while True:
                try:
                    system_data = self.system_queue.sync_q.get_nowait()
                    if system_data.get('type') == 'system_message':
                        self.show_system_message(system_data['message'])
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error checking system queue: {e}")
    
    def add_message_bubble(self, message: str, sender: str, is_self: bool = False, timestamp: str = ""):
        """Add a message bubble to the chat."""
        bubble = MessageBubble(
            message=message,
            sender=sender,
            is_self=is_self,
            timestamp=timestamp
        )
        self.messages_layout.add_widget(bubble)
    
    def add_file_bubble(self, filename: str, filesize: int, file_cid: str,
                        sender: str, is_self: bool = False, timestamp: str = ""):
        """Add a file sharing bubble to the chat."""
        on_download = None if is_self else self._request_download
        
        bubble = FileBubble(
            filename=filename,
            filesize=filesize,
            file_cid=file_cid,
            sender=sender,
            is_self=is_self,
            timestamp=timestamp,
            on_download=on_download
        )
        self.messages_layout.add_widget(bubble)
        
        # Track file bubbles for download status updates
        if file_cid:
            self.file_bubbles[file_cid] = bubble
    
    def open_file_picker(self, *args):
        """Open the file picker to select a file to share."""
        if not self.current_topic:
            self.show_system_message("Select a topic first")
            return
        
        if self.file_manager_open:
            return
        
        # Open file manager at home directory
        home_dir = os.path.expanduser("~")
        self.file_manager.show(home_dir)
        self.file_manager_open = True
    
    def _exit_file_manager(self, *args):
        """Called when file manager is closed without selection."""
        self.file_manager.close()
        self.file_manager_open = False
    
    def _on_file_selected(self, path: str):
        """Called when a file is selected from the file picker."""
        self.file_manager.close()
        self.file_manager_open = False
        
        if not path or not os.path.isfile(path):
            self.show_system_message("Invalid file selected")
            return
        
        if not self.current_topic:
            self.show_system_message("Select a topic first")
            return
        
        filename = os.path.basename(path)
        filesize = os.path.getsize(path)
        
        # Show confirmation dialog
        self._confirm_file_share(path, filename, filesize)
    
    def _confirm_file_share(self, file_path: str, filename: str, filesize: int):
        """Show a confirmation dialog before sharing a file."""
        dialog = MDDialog(
            title="Share File?",
            text=f"File: {filename}\nSize: {format_file_size(filesize)}\nTopic: {self.current_topic}",
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: dialog.dismiss()
                ),
                MDFlatButton(
                    text="SHARE",
                    on_release=lambda x: (dialog.dismiss(), self._do_share_file(file_path))
                )
            ]
        )
        dialog.open()
    
    def _do_share_file(self, file_path: str):
        """Execute file sharing via headless service."""
        try:
            success = self.headless_service.share_file(file_path, self.current_topic)
            if success:
                self.show_system_message(f"Preparing file for sharing...")
            else:
                self.show_system_message("Failed to queue file share request")
        except Exception as e:
            logger.error(f"Error sharing file: {e}")
            self.show_system_message(f"Error: {str(e)}")
    
    def _request_download(self, file_cid: str, filename: str):
        """Request download of a file."""
        try:
            success = self.headless_service.download_file(file_cid, filename)
            if success:
                self.show_system_message(f"Downloading: {filename}...")
            else:
                self.show_system_message("Failed to queue download request")
                # Re-enable download button
                if file_cid in self.file_bubbles:
                    bubble = self.file_bubbles[file_cid]
                    if hasattr(bubble, 'download_btn'):
                        bubble.download_btn.text = "Download"
                        bubble.download_btn.disabled = False
        except Exception as e:
            logger.error(f"Error requesting download: {e}")
            self.show_system_message(f"Error: {str(e)}")
    
    def _show_download_notification(self, filename: str, save_path: str):
        """Show a brief notification that file has been downloaded."""
        try:
            Snackbar(
                text=f"Downloaded: {filename} -> {save_path}",
                duration=2,
            ).open()
        except Exception:
            # Fallback if Snackbar fails
            self.show_system_message(f"Downloaded: {filename} saved to {save_path}")
    
    def show_system_message(self, message: str):
        """Show a system message."""
        timestamp = time.strftime("%H:%M")
        
        # Create a centered system message
        system_card = MDCard(
            orientation='vertical',
            size_hint=(0.8, None),
            height=dp(40),
            pos_hint={'center_x': 0.5},
            md_bg_color=(0.95, 0.95, 0.95, 1),
            padding=dp(10)
        )
        
        label = MDLabel(
            text=f"[{timestamp}] {message}",
            font_style='Caption',
            theme_text_color='Secondary',
            halign='center'
        )
        system_card.add_widget(label)
        self.messages_layout.add_widget(system_card)
    
    def show_peers(self, *args):
        """Show connected peers dialog."""
        info = self.headless_service.get_connection_info()
        peers = info.get('connected_peers', set())
        
        if peers:
            peer_list = "\n".join([f"• {peer[:16]}..." for peer in sorted(peers)])
            content = f"Connected Peers ({len(peers)}):\n\n{peer_list}"
        else:
            content = "No peers connected yet."
        
        dialog = MDDialog(
            title="Connected Peers",
            text=content,
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
    
    def show_info(self, *args):
        """Show connection info dialog with clickable text to copy."""
        info = self.headless_service.get_connection_info()
        peer_id = info.get('peer_id', 'Unknown')
        multiaddr = info.get('multiaddr', 'Unknown')
        topics = self.headless_service.get_subscribed_topics()
        topics_list = ", ".join(sorted(topics)) if topics else "None"
        
        # Create content layout
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(320)
        )
        
        # Info text
        info_label = MDLabel(
            text=f"""Nickname: {info.get('nickname', 'Unknown')}
Connected Peers: {info.get('peer_count', 0)}
Subscribed Topics: {topics_list}
""",
            size_hint_y=None,
            height=dp(100)
        )
        content.add_widget(info_label)
        
        # Peer ID section
        peer_id_label = MDLabel(
            text="Peer ID:",
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        )
        content.add_widget(peer_id_label)
        
        # Clickable Peer ID card
        peer_id_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(50),
            padding=dp(10),
            md_bg_color=(0.9, 0.95, 1, 1),  # Light blue tint
            on_release=lambda x: self.copy_to_clipboard(peer_id, "Peer ID copied!")
        )
        
        peer_id_text = MDLabel(
            text=peer_id,
            font_style='Body2',
            halign='left',
            valign='middle',
            size_hint_y=1
        )
        peer_id_card.add_widget(peer_id_text)
        content.add_widget(peer_id_card)
        
        # Multiaddr section
        multiaddr_label = MDLabel(
            text="Multiaddr:",
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        )
        content.add_widget(multiaddr_label)
        
        # Clickable Multiaddr card
        multiaddr_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(70),
            padding=dp(10),
            md_bg_color=(0.9, 0.95, 1, 1),  # Light blue tint
            on_release=lambda x: self.copy_to_clipboard(multiaddr, "Multiaddr copied!")
        )
        
        multiaddr_text = MDLabel(
            text=multiaddr,
            font_style='Body2',
            halign='left',
            valign='middle',
            size_hint_y=1
        )
        multiaddr_card.add_widget(multiaddr_text)
        content.add_widget(multiaddr_card)
        
        dialog = MDDialog(
            title="Connection Status",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
    
    def copy_to_clipboard(self, text, success_message):
        """Copy text to clipboard and show confirmation."""
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            logger.info(f"Copied to clipboard: {text[:50]}...")
            self.show_system_message(success_message)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            self.show_system_message("Failed to copy to clipboard")
    
    def show_multiaddr(self, *args):
        """Show multiaddr dialog with clickable text to copy."""
        info = self.headless_service.get_connection_info()
        multiaddr = info.get('multiaddr', 'Unknown')
        
        # Create content layout
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(100)
        )
        
        # Hint text
        hint_label = MDLabel(
            text="Tap multiaddr to copy:",
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        )
        content.add_widget(hint_label)
        
        # Clickable Multiaddr card
        multiaddr_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(70),
            padding=dp(10),
            md_bg_color=(0.9, 0.95, 1, 1),  # Light blue tint
            on_release=lambda x: self.copy_to_clipboard(multiaddr, "Multiaddr copied!")
        )
        
        multiaddr_text = MDLabel(
            text=multiaddr,
            font_style='Body2',
            halign='left',
            valign='middle',
            size_hint_y=1
        )
        multiaddr_card.add_widget(multiaddr_text)
        content.add_widget(multiaddr_card)
        
        dialog = MDDialog(
            title="My Multiaddress",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()


class PeersScreen(Screen):
    """Screen showing list of connected peers."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        
        layout = BoxLayout(orientation='vertical')
        
        # Top app bar
        toolbar = MDTopAppBar(
            title="Connected Peers",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            elevation=2
        )
        layout.add_widget(toolbar)
        
        # Peers list
        self.peers_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            padding=dp(10),
            size_hint_y=None
        )
        self.peers_layout.bind(minimum_height=self.peers_layout.setter('height'))
        
        scroll = MDScrollView()
        scroll.add_widget(self.peers_layout)
        layout.add_widget(scroll)
        
        self.add_widget(layout)
        
        # Update peers periodically
        Clock.schedule_interval(self.update_peers, 1.0)
    
    def go_back(self):
        """Go back to chat screen."""
        self.manager.current = 'chat'
    
    def update_peers(self, dt):
        """Update the peers list."""
        self.peers_layout.clear_widgets()
        
        info = self.headless_service.get_connection_info()
        peers = info.get('connected_peers', set())
        
        if not peers:
            label = MDLabel(
                text="No peers connected",
                halign='center',
                theme_text_color='Hint'
            )
            self.peers_layout.add_widget(label)
            return
        
        for peer in sorted(peers):
            peer_item = OneLineAvatarIconListItem(
                text=f"{peer[:16]}...",
                on_release=lambda x, p=peer: self.show_peer_info(p)
            )
            peer_item.add_widget(IconLeftWidget(icon="account"))
            self.peers_layout.add_widget(peer_item)
    
    def show_peer_info(self, peer_id):
        """Show information about a specific peer."""
        dialog = MDDialog(
            title="Peer Information",
            text=f"Peer ID:\n{peer_id}",
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()


class TopicsScreen(Screen):
    """Main screen showing list of subscribed topics - WhatsApp style selector."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        self.new_topic_dialog = None
        
        layout = BoxLayout(orientation='vertical')
        
        # Top app bar
        toolbar = MDTopAppBar(
            title="Universal Chat",
            right_action_items=[
                ["plus", lambda x: self.show_add_topic_dialog()],
                ["connection", lambda x: self.show_connect_dialog()],
                ["information", lambda x: self.show_app_info()]
            ],
            elevation=2
        )
        layout.add_widget(toolbar)
        
        # Topics list
        self.topics_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            padding=dp(10),
            size_hint_y=None
        )
        self.topics_layout.bind(minimum_height=self.topics_layout.setter('height'))
        
        scroll = MDScrollView()
        scroll.add_widget(self.topics_layout)
        layout.add_widget(scroll)
        
        self.add_widget(layout)
        
        # Update topics periodically
        Clock.schedule_interval(self.update_topics, 1.0)
    
    def go_back(self):
        """Not used - Topics is the main screen now."""
        pass
    
    def update_topics(self, dt):
        """Update the topics list with unread counts."""
        self.topics_layout.clear_widgets()
        
        # Get all topics with their info
        topics_info = self.headless_service.get_all_topics_with_info()
        
        if not topics_info:
            label = MDLabel(
                text="No topics subscribed\nTap + to add a topic",
                halign='center',
                theme_text_color='Hint'
            )
            self.topics_layout.add_widget(label)
            return
        
        # Sort topics by unread count (most unread first), then alphabetically
        sorted_topics = sorted(
            topics_info.items(),
            key=lambda x: (-x[1]['unread_count'], x[0])
        )
        
        for topic, info in sorted_topics:
            unread_count = info['unread_count']
            last_message = info.get('last_message')
            
            # Create topic item with two lines (topic name + last message preview)
            from kivymd.uix.list import TwoLineAvatarIconListItem
            
            # Preview of last message
            preview = ""
            if last_message:
                preview = last_message['message'][:50]
                if len(last_message['message']) > 50:
                    preview += "..."
            
            topic_item = TwoLineAvatarIconListItem(
                text=topic,
                secondary_text=preview or "No messages yet",
                on_release=lambda x, t=topic: self.open_topic_chat(t)
            )
            topic_item.add_widget(IconLeftWidget(icon="pound"))
            
            # Add unread badge if there are unread messages
            if unread_count > 0:
                # Show unread count in the secondary text
                unread_text = f" ({unread_count} unread)"
                topic_item.secondary_text = (preview or "No messages yet") + unread_text
            
            self.topics_layout.add_widget(topic_item)
    
    def open_topic_chat(self, topic):
        """Open the chat screen for a specific topic."""
        # Switch to chat screen
        chat_screen = self.manager.get_screen('chat')
        chat_screen.set_topic(topic)
        self.manager.current = 'chat'
    
    def show_topic_info(self, topic):
        """Show information about a specific topic."""
        info = self.headless_service.get_all_topics_with_info().get(topic, {})
        unread = info.get('unread_count', 0)
        total = info.get('total_count', 0)
        
        dialog = MDDialog(
            title=f"Topic: {topic}",
            text=f"Total messages: {total}\nUnread messages: {unread}",
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                ),
                MDFlatButton(
                    text="OPEN CHAT",
                    on_release=lambda x: (dialog.dismiss(), self.open_topic_chat(topic))
                )
            ]
        )
        dialog.open()
    
    def show_add_topic_dialog(self):
        """Show dialog to add a new topic."""
        # Text field for topic name
        self.topic_input = MDTextField(
            hint_text="Enter topic name",
            size_hint_x=0.9,
            pos_hint={'center_x': 0.5}
        )
        
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(20),
            size_hint_y=None,
            height=dp(100)
        )
        content.add_widget(self.topic_input)
        
        self.new_topic_dialog = MDDialog(
            title="Subscribe to New Topic",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: self.new_topic_dialog.dismiss()
                ),
                MDFlatButton(
                    text="SUBSCRIBE",
                    on_release=self.add_topic
                )
            ]
        )
        self.new_topic_dialog.open()
    
    def show_app_info(self):
        """Show app connection information with clickable text to copy."""
        info = self.headless_service.get_connection_info()
        peer_id = info.get('peer_id', 'Unknown')
        multiaddr = info.get('multiaddr', 'Unknown')
        
        # Create content layout
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=dp(10),
            size_hint_y=None,
            height=dp(200)
        )
        
        # Peer ID section
        peer_id_label = MDLabel(
            text="Peer ID:",
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        )
        content.add_widget(peer_id_label)
        
        # Clickable Peer ID card
        peer_id_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(50),
            padding=dp(10),
            md_bg_color=(0.9, 0.95, 1, 1),  # Light blue tint
            on_release=lambda x: self.copy_to_clipboard(peer_id, "Peer ID copied!")
        )
        
        peer_id_text = MDLabel(
            text=peer_id,
            font_style='Body2',
            halign='left',
            valign='middle',
            size_hint_y=1
        )
        peer_id_card.add_widget(peer_id_text)
        content.add_widget(peer_id_card)
        
        # Multiaddr section
        multiaddr_label = MDLabel(
            text="Multiaddr:",
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None,
            height=dp(20)
        )
        content.add_widget(multiaddr_label)
        
        # Clickable Multiaddr card
        multiaddr_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            height=dp(70),
            padding=dp(10),
            md_bg_color=(0.9, 0.95, 1, 1),  # Light blue tint
            on_release=lambda x: self.copy_to_clipboard(multiaddr, "Multiaddr copied!")
        )
        
        multiaddr_text = MDLabel(
            text=multiaddr,
            font_style='Body2',
            halign='left',
            valign='middle',
            size_hint_y=1
        )
        multiaddr_card.add_widget(multiaddr_text)
        content.add_widget(multiaddr_card)
        
        dialog = MDDialog(
            title="Connection Info",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
    
    def copy_to_clipboard(self, text, success_message):
        """Copy text to clipboard and show confirmation."""
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            logger.info(f"Copied to clipboard: {text[:50]}...")
            self.show_status_dialog("Success", success_message)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            self.show_status_dialog("Error", "Failed to copy to clipboard")
    
    def show_connect_dialog(self):
        """Show dialog to connect to a peer."""
        # Text field for multiaddress
        self.connect_input = MDTextField(
            hint_text="Enter peer multiaddress",
            helper_text="e.g., /ip4/127.0.0.1/tcp/9095/p2p/QmXXXXXXXXXX...",
            helper_text_mode="persistent",
            multiline=True,
            size_hint_y=None,
            height=dp(120)
        )
        
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(20),
            size_hint_y=None,
            height=dp(140)
        )
        content.add_widget(self.connect_input)
        
        self.connect_dialog = MDDialog(
            title="Connect to Peer",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: self.connect_dialog.dismiss()
                ),
                MDFlatButton(
                    text="CONNECT",
                    on_release=self.connect_to_peer
                )
            ]
        )
        self.connect_dialog.open()
    
    def connect_to_peer(self, *args):
        """Connect to a peer using the provided multiaddress."""
        multiaddr = self.connect_input.text.strip()
        
        if not multiaddr:
            self.show_status_dialog("Error", "Please enter a multiaddress")
            return
        
        # Close the dialog
        if self.connect_dialog:
            self.connect_dialog.dismiss()
        
        try:
            # Call the headless service to connect
            success = self.headless_service.connect_to_peer(multiaddr)
            if success:
                self.show_status_dialog("Success", f"Connection request sent!\n\n{multiaddr[:60]}...")
            else:
                self.show_status_dialog("Error", "Failed to queue connection request")
        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            self.show_status_dialog("Error", f"Connection failed: {str(e)}")
    
    def show_status_dialog(self, title, text):
        """Show a status/error dialog."""
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(
                    text="OK",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
    
    def add_topic(self, *args):
        """Add a new topic subscription."""
        topic_name = self.topic_input.text.strip()
        
        if not topic_name:
            return
        
        # Subscribe to the topic
        success = self.headless_service.subscribe_to_topic(topic_name)
        
        if success:
            logger.info(f"Successfully subscribed to topic: {topic_name}")
        else:
            logger.error(f"Failed to subscribe to topic: {topic_name}")
        
        # Close dialog
        if self.new_topic_dialog:
            self.new_topic_dialog.dismiss()
        
        # Update the topics list immediately
        self.update_topics(0)


class ChatApp(MDApp):
    """Main Kivy application for the chat."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"
        
    def build(self):
        """Build the application."""
        # Screen manager
        sm = ScreenManager()
        
        # Add screens
        topics_screen = TopicsScreen(self.headless_service, name='topics')
        chat_screen = ChatScreen(self.headless_service, name='chat')
        peers_screen = PeersScreen(self.headless_service, name='peers')
        
        sm.add_widget(topics_screen)
        sm.add_widget(chat_screen)
        sm.add_widget(peers_screen)
        
        # Set initial screen to topics (main WhatsApp-style selector)
        sm.current = 'topics'
        
        return sm
    
    def on_start(self):
        """Called when the app starts."""
        logger.info("Kivy Chat UI started")
    
    def on_stop(self):
        """Called when the app stops."""
        logger.info("Kivy Chat UI stopped")
        # Cleanup if needed
        return True


def run_kivy_ui(headless_service):
    """
    Run the Kivy UI with the given headless service.
    
    Args:
        headless_service: The HeadlessService instance to use for communication
    """
    logger.info("Starting Kivy UI...")
    
    # Set window size for desktop (will be ignored on mobile)
    Window.size = (400, 600)
    
    # Create and run app
    app = ChatApp(headless_service)
    app.run()
    
    logger.info("Kivy UI stopped")
