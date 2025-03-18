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
    private TextView chatTextView;
    private TextView logsTextView;
    private ListView peersListView;
    private readonly object uiLock = new();

    private List<string> chatHistory = new();
    private List<string> logHistory = new();
    private List<string> peersHistory = new();

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
            Application.MainLoop.Invoke(() =>
            {
                chatTextView.Text = string.Join("\n", chatHistory);
            });
        }
    }

    public void AddLog(string message)
    {
        lock (uiLock)
        {
            logHistory.Add(message);
            Application.MainLoop.Invoke(() =>
            {
                logsTextView.Text = string.Join("\n", logHistory);
            });
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
                {
                    peersListView.SetSource(new List<string>(peersHistory));
                });
            }
        }
    }
}

public class Program
{
    public static async Task Main(string[] args)
    {
        var serviceProvider = new ServiceCollection()
            .AddLibp2p(builder => builder.WithPubsub())
            .AddLogging(builder =>
            {
                builder.SetMinimumLevel(LogLevel.Information)
                    .AddSimpleConsole(options =>
                    {
                        options.SingleLine = true;
                        options.TimestampFormat = "[HH:mm:ss.fff] ";
                    });
            })
            .BuildServiceProvider();

        IPeerFactory peerFactory = serviceProvider.GetService<IPeerFactory>()!;
        ILogger logger = serviceProvider.GetService<ILoggerFactory>()!.CreateLogger("Pubsub Chat");
        CancellationTokenSource ts = new CancellationTokenSource();

        Identity localPeerIdentity = new Identity();
        string peerIdStr = localPeerIdentity.PeerId.ToString();

        string addrString = $"/ip4/0.0.0.0/tcp/9096/p2p/{peerIdStr}";
        Multiaddress addr = Multiaddress.Decode(addrString);

        ILocalPeer peer = peerFactory.Create(localPeerIdentity);

        PubsubRouter router = serviceProvider.GetService<PubsubRouter>()!;
        string roomName = "universal-connectivity";
        ITopic topic = router.GetTopic(roomName);

        Application.Init();
        var top = Application.Top;

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
        var peerIdLabel = new Label($"Peer ID: {peerIdStr}")
        {
            X = 1,
            Y = 0
        };
        var multiAddrLabel = new Label($"Multiaddr: {addrString}")
        {
            X = 1,
            Y = 1
        };
        infoFrame.Add(peerIdLabel, multiAddrLabel);
        win.Add(infoFrame);

        // --- TabView for Chat, Peers, and Logs ---
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

        win.Add(inputField, sendButton);
        top.Add(win);

        var chatApp = new ChatApp(chatTextView, logsTextView, peersListView);

        topic.OnMessage += (byte[] msg) =>
        {
            try
            {
                string raw = Encoding.UTF8.GetString(msg).Trim();

                ChatMessage? chatMsg = null;
                try
                {
                    chatMsg = JsonSerializer.Deserialize<ChatMessage>(raw);
                }
                catch (JsonException)
                {
                }

                if (chatMsg != null && !string.IsNullOrEmpty(chatMsg.Message))
                {
                    string display = $"{chatMsg.SenderNick}: {chatMsg.Message}";
                    chatApp.AddChatMessage(display);
                    chatApp.AddLog($"Received JSON message: {raw}");
                    if (chatMsg.SenderID != peerIdStr)
                    {
                        string displayId = chatMsg.SenderID.Length > 10
                            ? chatMsg.SenderID.Substring(0, 10) + "..."
                            : chatMsg.SenderID;
                        chatApp.AddPeer(displayId);
                    }
                }
                else
                {
                    chatApp.AddChatMessage(raw);
                    chatApp.AddLog($"Received plain text message: {raw}");
                }
            }
            catch (Exception ex)
            {
                chatApp.AddLog($"[Error] {ex.Message}");
            }
        };

        chatApp.AddLog($"[Info] Generated Peer ID: {peerIdStr}");
        chatApp.AddLog($"[Info] Multiaddress: {addrString}");

        sendButton.Clicked += () =>
        {
            string message = inputField.Text.ToString();
            if (!string.IsNullOrWhiteSpace(message))
            {
                var chatMessage = new ChatMessage
                {
                    Message = message,
                    SenderID = peerIdStr,
                    SenderNick = "libp2p-dotnet"
                };
                string jsonMessage = JsonSerializer.Serialize(chatMessage);
                topic.Publish(Encoding.UTF8.GetBytes(jsonMessage));

                chatApp.AddChatMessage($"[You]: {message}");
                chatApp.AddLog($"Sent JSON message: {jsonMessage}");
                inputField.Text = "";
            }
        };

        _ = Task.Run(async () =>
        {
            try
            {
                await peer.StartListenAsync(new[] { addr }, ts.Token);
                await router.StartAsync(peer, ts.Token);
                chatApp.AddLog("[Info] Peer started successfully");
            }
            catch (Exception ex)
            {
                chatApp.AddLog($"[Error] {ex.Message}");
            }
        });

        Application.Run();
        ts.Cancel();
        Application.Shutdown();
        await Task.CompletedTask;
    }
}
