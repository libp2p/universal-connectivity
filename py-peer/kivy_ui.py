"""
Kivy UI module for Universal Connectivity Python Peer

This module provides a modern mobile-friendly UI using Kivy and KivyMD.
It works with the headless service and uses queues for communication.
Design inspired by WhatsApp/Telegram for a familiar chat experience.
"""

import os
# Disable Kivy argument parsing to avoid conflicts with our app's arguments
os.environ['KIVY_NO_ARGS'] = '1'

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
from kivymd.uix.button import MDIconButton, MDFlatButton
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.navigationdrawer import MDNavigationDrawer, MDNavigationDrawerMenu

logger = logging.getLogger("kivy_ui")


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


class ChatScreen(Screen):
    """Main chat screen with message list and input."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        self.message_queue = headless_service.get_message_queue()
        self.system_queue = headless_service.get_system_queue()
        self.connection_info = headless_service.get_connection_info()
        
        # Main layout
        layout = BoxLayout(orientation='vertical')
        
        # Top app bar
        self.toolbar = MDTopAppBar(
            title="Universal Chat",
            left_action_items=[["menu", lambda x: self.toggle_nav_drawer()]],
            right_action_items=[
                ["pound", lambda x: self.show_topics()],
                ["account-group", lambda x: self.show_peers()],
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
        scroll = MDScrollView()
        scroll.add_widget(self.messages_layout)
        layout.add_widget(scroll)
        
        # Input area
        input_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            padding=dp(10),
            spacing=dp(10)
        )
        
        # Text input
        self.message_input = MDTextField(
            hint_text="Type a message...",
            multiline=False,
            size_hint_x=0.85
        )
        self.message_input.bind(on_text_validate=self.send_message)
        input_layout.add_widget(self.message_input)
        
        # Send button
        send_btn = MDIconButton(
            icon="send",
            on_release=self.send_message
        )
        input_layout.add_widget(send_btn)
        
        layout.add_widget(input_layout)
        
        self.add_widget(layout)
        
        # Start queue checking
        Clock.schedule_interval(self.check_queues, 0.1)
    
    def toggle_nav_drawer(self):
        """Toggle navigation drawer."""
        app = MDApp.get_running_app()
        if hasattr(app, 'nav_drawer'):
            app.nav_drawer.set_state("toggle")
    
    def show_topics(self):
        """Switch to topics screen."""
        self.manager.current = 'topics'
    
    def send_message(self, *args):
        """Send a message."""
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
            self.headless_service.send_message(message)
            
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
        elif cmd == "/peers":
            self.show_peers()
        elif cmd == "/status":
            self.show_info()
        elif cmd == "/multiaddr":
            self.show_multiaddr()
        else:
            self.show_system_message(f"Unknown command: {command}")
    
    def check_queues(self, dt):
        """Check message queues for new messages."""
        # Check message queue
        try:
            while True:
                try:
                    message_data = self.message_queue.sync_q.get_nowait()
                    if message_data.get('type') == 'chat_message':
                        sender_nick = message_data['sender_nick']
                        sender_id = message_data['sender_id']
                        msg = message_data['message']
                        
                        # Don't display our own messages again
                        our_peer_id = self.connection_info.get('peer_id', '')
                        if sender_id != our_peer_id and sender_id != "self":
                            timestamp = time.strftime("%H:%M")
                            self.add_message_bubble(msg, sender_nick, is_self=False, timestamp=timestamp)
                        
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
        """Show connection info dialog."""
        info = self.headless_service.get_connection_info()
        topics = self.headless_service.get_subscribed_topics()
        topics_list = ", ".join(sorted(topics)) if topics else "None"
        
        content = f"""
Nickname: {info.get('nickname', 'Unknown')}
Peer ID: {info.get('peer_id', 'Unknown')[:16]}...
Connected Peers: {info.get('peer_count', 0)}
Subscribed Topics: {topics_list}
"""
        
        dialog = MDDialog(
            title="Connection Status",
            text=content,
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
        dialog.open()
    
    def show_multiaddr(self, *args):
        """Show multiaddr dialog."""
        info = self.headless_service.get_connection_info()
        
        dialog = MDDialog(
            title="My Multiaddress",
            text=info.get('multiaddr', 'Unknown'),
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
    """Screen showing list of subscribed topics with ability to add new ones."""
    
    def __init__(self, headless_service, **kwargs):
        super().__init__(**kwargs)
        self.headless_service = headless_service
        self.new_topic_dialog = None
        
        layout = BoxLayout(orientation='vertical')
        
        # Top app bar
        toolbar = MDTopAppBar(
            title="Subscribed Topics",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            right_action_items=[["plus", lambda x: self.show_add_topic_dialog()]],
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
        """Go back to chat screen."""
        self.manager.current = 'chat'
    
    def update_topics(self, dt):
        """Update the topics list."""
        self.topics_layout.clear_widgets()
        
        topics = self.headless_service.get_subscribed_topics()
        
        if not topics:
            label = MDLabel(
                text="No topics subscribed",
                halign='center',
                theme_text_color='Hint'
            )
            self.topics_layout.add_widget(label)
            return
        
        for topic in sorted(topics):
            topic_item = OneLineAvatarIconListItem(
                text=topic,
                on_release=lambda x, t=topic: self.show_topic_info(t)
            )
            topic_item.add_widget(IconLeftWidget(icon="pound"))
            self.topics_layout.add_widget(topic_item)
    
    def show_topic_info(self, topic):
        """Show information about a specific topic."""
        dialog = MDDialog(
            title="Topic Information",
            text=f"Topic: {topic}\n\nThis topic is currently subscribed for receiving messages.",
            buttons=[
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: dialog.dismiss()
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
        chat_screen = ChatScreen(self.headless_service, name='chat')
        peers_screen = PeersScreen(self.headless_service, name='peers')
        topics_screen = TopicsScreen(self.headless_service, name='topics')
        
        sm.add_widget(chat_screen)
        sm.add_widget(peers_screen)
        sm.add_widget(topics_screen)
        
        # Set initial screen
        sm.current = 'chat'
        
        # Display welcome message
        connection_info = self.headless_service.get_connection_info()
        chat_screen.show_system_message("Universal Connectivity Chat Started")
        chat_screen.show_system_message(f"Nickname: {connection_info.get('nickname', 'Unknown')}")
        chat_screen.show_system_message("Commands: /quit, /peers, /status, /multiaddr")
        
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
