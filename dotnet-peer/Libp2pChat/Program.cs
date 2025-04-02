using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using Terminal.Gui;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Nethermind.Libp2p;
using Nethermind.Libp2p.Core;
using Nethermind.Libp2p.Protocols.Pubsub;
using Multiformats.Address;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Collections.Concurrent;

#region TUILogger

// A simple logger that writes to the UI log view and also to a provided ILogger instance.
public class TUILogger : ILogger
{
    private readonly ChatApp chatApp;
    private readonly string category;
    private readonly LogLevel minLevel;

    public TUILogger(ChatApp chatApp, string category, LogLevel minLevel = LogLevel.Debug)
    {
        this.chatApp = chatApp;
        this.category = category;
        this.minLevel = minLevel;
    }

    // Explicitly implement ILogger.BeginScope to handle nullability correctly
    IDisposable ILogger.BeginScope<TState>(TState state) => NullDisposable.Instance;

    public bool IsEnabled(LogLevel logLevel) => logLevel >= minLevel;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel))
            return;

        string message = $"[{DateTime.Now:HH:mm:ss.fff}] [{logLevel}] {formatter(state, exception)}";
        if (exception != null)
            message += $"\nException: {exception.Message}\nStack: {exception.StackTrace}";

        // Log to the UI
        chatApp.AddLog(message);
    }

    // Helper disposable that does nothing, returned by BeginScope
    private class NullDisposable : IDisposable
    {
        public static readonly NullDisposable Instance = new NullDisposable();
        public void Dispose() { }
    }
}
#endregion

#region ChatApp and UI Helper
public class ChatMessage
{
    [JsonPropertyName("Message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("SenderID")]
    public string SenderID { get; set; } = string.Empty;

    [JsonPropertyName("SenderNick")]
    public string SenderNick { get; set; } = string.Empty;
}

public class ChatApp
{
    private readonly TextView chatTextView;
    private readonly TextView logsTextView;
    private readonly ListView peersListView;
    private readonly object uiLock = new();

    private readonly List<string> chatHistory = new();
    private readonly List<string> logHistory = new();
    private readonly List<string> peersHistory = new();

    public ChatApp(TextView chat, TextView logs, ListView peers)
    {
        chatTextView = chat;
        logsTextView = logs;
        peersListView = peers;
    }

    public void AddChatMessage(string message)
    {
        lock (uiLock)
        {
            chatHistory.Add(message);
            Application.MainLoop.Invoke(() => chatTextView.Text = string.Join("\n", chatHistory));
        }
    }

    public void AddLog(string message)
    {
        lock (uiLock)
        {
            logHistory.Add(message);
            Application.MainLoop.Invoke(() => logsTextView.Text = string.Join("\n", logHistory));
        }
    }

    public void AddPeer(string peer)
    {
        lock (uiLock)
        {
            if (!peersHistory.Contains(peer))
            {
                peersHistory.Add(peer);
                Application.MainLoop.Invoke(() =>
                    peersListView.SetSource(new List<string>(peersHistory)));
            }
        }
    }
}
#endregion

#region Program
public class Program
{
    // Track connected peers
    private static readonly ConcurrentDictionary<string, DateTime> knownPeers = new();

    public static async Task Main(string[] args)
    {
        // Set up dependency injection and logging
        var serviceProvider = new ServiceCollection()
            .AddLibp2p(builder => builder.WithPubsub())
            .AddLogging(builder =>
            {
                builder.SetMinimumLevel(LogLevel.Debug)
                    .AddSimpleConsole(options =>
                    {
                        options.SingleLine = true;
                        options.TimestampFormat = "[HH:mm:ss.fff] ";
                    });
            })
            .BuildServiceProvider();

        IPeerFactory peerFactory = serviceProvider.GetService<IPeerFactory>()!;
        var loggerFactory = serviceProvider.GetService<ILoggerFactory>()!;
        CancellationTokenSource ts = new CancellationTokenSource();

        // Initialize Terminal.Gui
        Application.Init();
        var top = Application.Top;

        // Create main window and UI elements
        var win = new Window("Libp2p Chat")
        {
            X = 0,
            Y = 1,
            Width = Dim.Fill(),
            Height = Dim.Fill()
        };

        var infoFrame = new FrameView("Peer Info")
        {
            X = 0,
            Y = 0,
            Width = Dim.Fill(),
            Height = 3
        };

        // TabView for Chat, Peers, and Logs
        var tabView = new TabView()
        {
            X = 0,
            Y = Pos.Bottom(infoFrame),
            Width = Dim.Fill(),
            Height = Dim.Fill(3)
        };

        var chatTextView = new TextView()
        {
            ReadOnly = true,
            WordWrap = true,
            X = 0,
            Y = 0,
            Width = Dim.Fill(),
            Height = Dim.Fill()
        };
        var chatTab = new TabView.Tab("Chat", chatTextView);

        var peersListView = new ListView(new List<string>())
        {
            X = 0,
            Y = 0,
            Width = Dim.Fill(),
            Height = Dim.Fill()
        };
        var peersTab = new TabView.Tab("Peers", peersListView);

        var logsTextView = new TextView()
        {
            ReadOnly = true,
            WordWrap = true,
            X = 0,
            Y = 0,
            Width = Dim.Fill(),
            Height = Dim.Fill()
        };
        var logsTab = new TabView.Tab("Logs", logsTextView);

        tabView.AddTab(chatTab, true);
        tabView.AddTab(peersTab, false);
        tabView.AddTab(logsTab, false);
        win.Add(tabView);

        // Input field and buttons
        var inputField = new TextField("")
        {
            X = 0,
            Y = Pos.Bottom(tabView),
            Width = Dim.Fill(12)
        };
        var sendButton = new Button("Send")
        {
            X = Pos.Right(inputField) + 1,
            Y = Pos.Top(inputField)
        };
        var exitButton = new Button("Exit")
        {
            X = Pos.Right(sendButton) + 1,
            Y = Pos.Top(inputField)
        };

        win.Add(inputField, sendButton, exitButton);
        top.Add(win);

        // Initialize ChatApp and custom logger
        var chatApp = new ChatApp(chatTextView, logsTextView, peersListView);
        ILogger tuiLogger = new TUILogger(chatApp, "TUILogger", LogLevel.Debug);

        // Handle unhandled exceptions globally
        AppDomain.CurrentDomain.UnhandledException += (s, e) =>
        {
            tuiLogger.Log(LogLevel.Critical, new EventId(), e.ExceptionObject, null, (ex, _) => $"Unhandled exception: {ex}");
        };

        // Generate local peer identity
        Identity localPeerIdentity = new Identity();
        string peerIdStr = localPeerIdentity.PeerId.ToString();
        chatApp.AddLog($"[Info] Generated Peer ID: {peerIdStr}");

        var peerIdLabel = new Label($"Peer ID: {peerIdStr}")
        {
            X = 1,
            Y = 0
        };

        // Primary and additional multiaddresses
        string addrString = $"/ip4/127.0.0.1/tcp/9096/p2p/{peerIdStr}";
        chatApp.AddLog($"[Info] Primary multiaddress: {addrString}");
        
        try 
        {
            Multiaddress addr = Multiaddress.Decode(addrString);
            string allIfacesAddrString = $"/ip4/0.0.0.0/tcp/9096/p2p/{peerIdStr}";
            Multiaddress allIfacesAddr = Multiaddress.Decode(allIfacesAddrString);
            chatApp.AddLog($"[Info] Additional multiaddress: {allIfacesAddrString}");
            
            var multiAddrLabel = new Label($"Multiaddr: {addrString}")
            {
                X = 1,
                Y = 1
            };
            infoFrame.Add(peerIdLabel, multiAddrLabel);
            win.Add(infoFrame);

            // Create local peer and router
            ILocalPeer peer = peerFactory.Create(localPeerIdentity);
            PubsubRouter router = serviceProvider.GetService<PubsubRouter>()!;
            if (router == null)
            {
                chatApp.AddLog("[Error] Failed to get PubsubRouter from service provider");
                return;
            }

            string roomName = "universal-connectivity";
            chatApp.AddLog($"[Info] Using topic name: {roomName}");
            ITopic topic = router.GetTopic(roomName);

            // Message handler with robust error handling
            topic.OnMessage += (byte[] msg) =>
            {
                try
                {
                    if (msg == null || msg.Length == 0)
                    {
                        chatApp.AddLog("[Warning] Received empty message");
                        return;
                    }
                    
                    string raw = Encoding.UTF8.GetString(msg).Trim();
                    chatApp.AddLog($"[Debug] Raw message received: {raw}");

                    bool isJsonMessage = raw.StartsWith("{");
                    if (isJsonMessage)
                    {
                        try
                        {
                            ChatMessage? chatMsg = JsonSerializer.Deserialize<ChatMessage>(raw);
                            if (chatMsg != null && !string.IsNullOrEmpty(chatMsg.Message))
                            {
                                string senderNick = string.IsNullOrEmpty(chatMsg.SenderNick) ? "unknown" : chatMsg.SenderNick;
                                string display = $"{senderNick}: {chatMsg.Message}";
                                chatApp.AddChatMessage(display);
                                chatApp.AddLog($"[Info] Received JSON message from {senderNick}");

                                // Update known peers
                                if (!string.IsNullOrEmpty(chatMsg.SenderID) && chatMsg.SenderID != peerIdStr)
                                {
                                    knownPeers[chatMsg.SenderID] = DateTime.Now;
                                    chatApp.AddPeer(chatMsg.SenderNick);
                                }
                            }
                            else
                            {
                                chatApp.AddLog("[Warning] Received invalid JSON message structure");
                                chatApp.AddChatMessage($"[Peer]: {raw}");
                            }
                        }
                        catch (JsonException ex)
                        {
                            chatApp.AddLog($"[Error] JSON parsing error: {ex.Message}");
                            chatApp.AddChatMessage($"[Peer]: {raw}");
                        }
                    }
                    else
                    {
                        chatApp.AddChatMessage($"[Peer]: {raw}");
                        chatApp.AddLog($"[Info] Received plain text message: {raw}");
                        
                        string goDisplayName = "go-peer";
                        string goDisplayKey = "go-peer-" + (DateTime.Now.Ticks % 10000);
                        
                        chatApp.AddPeer(goDisplayName);
                        knownPeers[goDisplayKey] = DateTime.Now;
                        chatApp.AddLog("[Info] Detected Go peer from message");
                    }
                }
                catch (Exception ex)
                {
                    chatApp.AddLog($"[Error] Message handling error: {ex.Message}");
                    chatApp.AddLog($"[Error] Stack trace: {ex.StackTrace}");
                }
            };

            // Send button logic with error handling
            sendButton.Clicked += () =>
            {
                try
                {
                    string message = inputField.Text?.ToString() ?? string.Empty;
                    if (!string.IsNullOrWhiteSpace(message))
                    {
                        try
                        {
                            topic.Publish(Encoding.UTF8.GetBytes(message));
                            chatApp.AddChatMessage($"[You]: {message}");
                            chatApp.AddLog($"[Info] Sent message: {message}");
                            inputField.Text = "";
                        }
                        catch (Exception ex)
                        {
                            chatApp.AddLog($"[Error] Failed to publish message: {ex.Message}");
                        }
                    }
                }
                catch (Exception ex)
                {
                    chatApp.AddLog($"[Error] Send button error: {ex.Message}");
                }
            };

            // Exit button and global key binding for exit
            exitButton.Clicked += () =>
            {
                chatApp.AddLog("[Info] Exit command triggered via button.");
                ts.Cancel();
                Application.RequestStop();
            };

            // Global key binding: Ctrl+Q to exit
            top.KeyPress += (args) => {
                if (args.KeyEvent.Key == (Key.Q | Key.CtrlMask)) {
                    chatApp.AddLog("[Info] Exit command triggered via Ctrl+Q.");
                    ts.Cancel();
                    Application.RequestStop();
                    args.Handled = true;
                }
            };

            // Start peer listener and router in background tasks
            _ = Task.Run(async () =>
            {
                try
                {
                    chatApp.AddLog("[Info] Starting peer listener...");
                    var addrList = new[] { addr, allIfacesAddr };
                    await peer.StartListenAsync(addrList, ts.Token);
                    chatApp.AddLog("[Info] Peer listener started successfully");
                    chatApp.AddLog($"[Info] Configured to listen on: {addrString}");
                    chatApp.AddLog($"[Info] Configured to listen on: {allIfacesAddrString}");

                    chatApp.AddLog("\n[Help] GO PEER CONNECTION INSTRUCTIONS:");
                    chatApp.AddLog($"[Help] Connect using the following command:");
                    chatApp.AddLog($"[Help] ./go-peer --connect /ip4/127.0.0.1/tcp/9096/p2p/{peerIdStr}");
                    chatApp.AddLog("[Help] Ensure ports and peer IDs match as configured.");

                    chatApp.AddLog("[Info] Starting router...");
                    await router.StartAsync(peer, ts.Token);
                    chatApp.AddLog("[Info] Router started successfully");

                    // Periodically log and clean up peer info
                    _ = Task.Run(async () =>
                    {
                        while (!ts.IsCancellationRequested)
                        {
                            try
                            {
                                chatApp.AddLog($"[Info] Known peers: {knownPeers.Count}");
                                if (knownPeers.Count > 0)
                                {
                                    chatApp.AddLog("[Info] Peer list:");
                                    foreach (var p in knownPeers)
                                    {
                                        TimeSpan sinceLastSeen = DateTime.Now - p.Value;
                                        string lastSeen = sinceLastSeen.TotalMinutes < 1 
                                            ? $"{sinceLastSeen.TotalSeconds:0}s ago" 
                                            : $"{sinceLastSeen.TotalMinutes:0.0}m ago";
                                        chatApp.AddLog($"[Info]   - {p.Key} (last seen {lastSeen})");
                                    }
                                }
                                DateTime cutoff = DateTime.Now.AddMinutes(-5);
                                foreach (var peer in knownPeers)
                                {
                                    if (peer.Value < cutoff && knownPeers.TryRemove(peer.Key, out _))
                                    {
                                        chatApp.AddLog($"[Info] Removed inactive peer: {peer.Key}");
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                chatApp.AddLog($"[Error] Failed to check peers: {ex.Message}");
                            }
                            await Task.Delay(30000, ts.Token);
                        }
                    }, ts.Token);
                }
                catch (OperationCanceledException)
                {
                    chatApp.AddLog("[Info] Peer startup canceled");
                }
                catch (Exception ex)
                {
                    chatApp.AddLog($"[Error] Peer startup error: {ex.Message}");
                    chatApp.AddLog($"[Error] Stack trace: {ex.StackTrace}");
                }
            }, ts.Token);

            // Run the Terminal.Gui application
            try
            {
                Application.Run();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"UI error: {ex.Message}");
            }
            finally
            {
                ts.Cancel();
                Application.Shutdown();
            }
        }
        catch (Exception ex)
        {
            chatApp.AddLog($"[Error] Multiaddress decoding error: {ex.Message}");
            chatApp.AddLog($"[Error] Stack trace: {ex.StackTrace}");
        }
        await Task.CompletedTask;
    }
}
#endregion
