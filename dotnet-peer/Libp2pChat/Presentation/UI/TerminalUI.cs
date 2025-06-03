using Libp2pChat.Domain.Models;
using Terminal.Gui;
using System.Linq;
using System.Runtime.InteropServices;

namespace Libp2pChat.Presentation.UI;

/// <summary>
/// Implementation of the terminal user interface using Terminal.Gui.
/// </summary>
public class TerminalUI : IChatUI, IDisposable
{
    private readonly object _uiLock = new();
    private readonly List<string> _chatHistory = new();
    private readonly List<string> _logHistory = new();
    private readonly List<string> _peersHistory = new();
    private bool _isInitialized;
    private bool _isDisposed;
    
    // UI elements
    private Window? _mainWindow;
    private FrameView? _infoFrame;
    private Label? _peerIdLabel;
    private Label? _multiAddrLabel;
    private TabView? _tabView;
    private TextView? _chatTextView;
    private TextView? _logsTextView;
    private ListView? _peersListView;
    private TextField? _inputField;
    private Button? _sendButton;
    private Button? _exitButton;
    
    /// <inheritdoc />
    public event EventHandler<string>? MessageSent;
    
    /// <inheritdoc />
    public event EventHandler? ExitRequested;
    
    /// <summary>
    /// Creates a new instance of the <see cref="TerminalUI"/> class.
    /// </summary>
    public TerminalUI()
    {
    }
    
    /// <inheritdoc />
    public void Initialize()
    {
        if (_isInitialized)
            return;
        
        try
        {    
            // Check for Windows console issues
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                Console.WriteLine("Running on Windows. Checking console environment...");
                
                try
                {
                    int width = Console.WindowWidth;
                    int height = Console.WindowHeight;
                    Console.WriteLine($"Console dimensions: {width}x{height}");
                    
                    Console.CursorVisible = true;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Warning: Console environment issue detected: {ex.Message}");
                    Console.WriteLine("You may need to run this application in a proper console window.");
                }
            }
            
            Terminal.Gui.Application.Init();
            Console.WriteLine("Terminal.Gui initialized successfully");
            
            var top = Terminal.Gui.Application.Top;
            
            _mainWindow = new Window("Libp2p Chat")
            {
                X = 0,
                Y = 1,
                Width = Dim.Fill(),
                Height = Dim.Fill()
            };
            
            _infoFrame = new FrameView("Peer Info")
            {
                X = 0,
                Y = 0,
                Width = Dim.Fill(),
                Height = 3
            };
            
            _peerIdLabel = new Label("Peer ID: [Not Connected]")
            {
                X = 1,
                Y = 0
            };
            
            _multiAddrLabel = new Label("Multiaddr: [Not Connected]")
            {
                X = 1,
                Y = 1
            };
            
            _infoFrame.Add(_peerIdLabel, _multiAddrLabel);
            
            _tabView = new TabView()
            {
                X = 0,
                Y = Pos.Bottom(_infoFrame),
                Width = Dim.Fill(),
                Height = Dim.Fill(3)
            };
            
            _chatTextView = new TextView()
            {
                ReadOnly = true,
                WordWrap = true,
                X = 0,
                Y = 0,
                Width = Dim.Fill(),
                Height = Dim.Fill()
            };
            
            // Create peers list view
            _peersListView = new ListView(new List<string>())
            {
                X = 0,
                Y = 0,
                Width = Dim.Fill(),
                Height = Dim.Fill()
            };
            
            // Create logs text view
            _logsTextView = new TextView()
            {
                ReadOnly = true,
                WordWrap = true,
                X = 0,
                Y = 0,
                Width = Dim.Fill(),
                Height = Dim.Fill()
            };
            
            // Add tabs to tab view
            var chatTab = new TabView.Tab("Chat", _chatTextView);
            var peersTab = new TabView.Tab("Peers", _peersListView);
            var logsTab = new TabView.Tab("Logs", _logsTextView);
            
            _tabView.AddTab(chatTab, true);
            _tabView.AddTab(peersTab, false);
            _tabView.AddTab(logsTab, false);
            
            // Create input field and buttons
            _inputField = new TextField("")
            {
                X = 0,
                Y = Pos.Bottom(_tabView),
                Width = Dim.Fill(12)
            };
            
            // Add support for Enter key to send message
            _inputField.KeyPress += OnInputFieldKeyPress;
            
            _sendButton = new Button("Send")
            {
                X = Pos.Right(_inputField) + 1,
                Y = Pos.Top(_inputField)
            };
            
            _exitButton = new Button("Exit")
            {
                X = Pos.Right(_sendButton) + 1,
                Y = Pos.Top(_inputField)
            };
            
            // Wire up events
            _sendButton.Clicked += OnSendButtonClicked;
            _exitButton.Clicked += OnExitButtonClicked;
            
            // Add input field and buttons to main window
            _mainWindow.Add(_infoFrame, _tabView, _inputField, _sendButton, _exitButton);
            top.Add(_mainWindow);
            
            // Add global key binding: Ctrl+Q to exit
            top.KeyPress += OnKeyPress;
            
            _isInitialized = true;
            Console.WriteLine("Terminal UI initialized successfully");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error initializing Terminal UI: {ex.Message}");
            Console.WriteLine(ex.StackTrace);
            throw;
        }
    }
    
    /// <inheritdoc />
    public void Run()
    {
        if (!_isInitialized)
            throw new InvalidOperationException("UI must be initialized before running");
        
        try
        {
            Console.WriteLine("Starting Terminal.Gui application...");
            Terminal.Gui.Application.Run();
            Console.WriteLine("Terminal.Gui application ended");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error running Terminal UI: {ex.Message}");
            Console.WriteLine(ex.StackTrace);
            throw;
        }
    }
    
    /// <inheritdoc />
    public void AddChatMessage(string message)
    {
        lock (_uiLock)
        {
            _chatHistory.Add(message);
            
            Terminal.Gui.Application.MainLoop?.Invoke(() =>
            {
                if (_chatTextView != null)
                {
                    _chatTextView.Text = string.Join("\n", _chatHistory);
                    ScrollToEnd(_chatTextView);
                }
            });
        }
    }
    
    /// <inheritdoc />
    public void AddChatMessage(ChatMessage chatMessage)
    {
        string displayName = string.IsNullOrEmpty(chatMessage.SenderNick) ? 
            (string.IsNullOrEmpty(chatMessage.SenderID) ? "Unknown" : chatMessage.SenderID) : 
            chatMessage.SenderNick;
            
        AddChatMessage($"{displayName}: {chatMessage.Message}");
    }
    
    /// <inheritdoc />
    public void AddLog(string message)
    {
        lock (_uiLock)
        {
            _logHistory.Add(message);
            
            Terminal.Gui.Application.MainLoop?.Invoke(() =>
            {
                if (_logsTextView != null)
                {
                    _logsTextView.Text = string.Join("\n", _logHistory);
                    ScrollToEnd(_logsTextView);
                }
            });
        }
    }
    
    /// <inheritdoc />
    public void AddPeer(Peer peer)
    {
        lock (_uiLock)
        {
            string displayName = string.IsNullOrEmpty(peer.DisplayName) ? peer.ShortId : peer.DisplayName;
            
            if (!_peersHistory.Contains(displayName))
            {
                _peersHistory.Add(displayName);
                
                Terminal.Gui.Application.MainLoop?.Invoke(() =>
                {
                    if (_peersListView != null)
                    {
                        _peersListView.SetSource(new List<string>(_peersHistory));
                    }
                });
            }
        }
    }
    
    /// <inheritdoc />
    public void UpdatePeerInfo(string peerId, string multiaddress)
    {
        Terminal.Gui.Application.MainLoop?.Invoke(() =>
        {
            if (_peerIdLabel != null)
            {
                _peerIdLabel.Text = $"Peer ID: {peerId}";
            }
            
            if (_multiAddrLabel != null)
            {
                _multiAddrLabel.Text = $"Multiaddr: {multiaddress}";
            }
        });
    }
    
    /// <inheritdoc />
    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }
    
    /// <summary>
    /// Disposes resources.
    /// </summary>
    /// <param name="disposing">Whether to dispose managed resources.</param>
    protected virtual void Dispose(bool disposing)
    {
        if (_isDisposed)
            return;
            
        if (disposing)
        {
            // Clean up managed resources
            if (_inputField != null)
                _inputField.KeyPress -= OnInputFieldKeyPress;
                
            if (_sendButton != null)
                _sendButton.Clicked -= OnSendButtonClicked;
                
            if (_exitButton != null)
                _exitButton.Clicked -= OnExitButtonClicked;
            
            var top = Terminal.Gui.Application.Top;
            top.KeyPress -= OnKeyPress;
            
            Terminal.Gui.Application.Shutdown();
        }
        
        _isDisposed = true;
    }
    
    private void OnSendButtonClicked()
    {
        try
        {
            string message = _inputField?.Text?.ToString() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(message))
                return;
                
            // Clear input field
            _inputField!.Text = string.Empty;
            
            // Show message in chat
            AddChatMessage($"[You]: {message}");
            
            // Notify subscribers
            MessageSent?.Invoke(this, message);
        }
        catch (Exception ex)
        {
            AddLog($"[Error] Send button error: {ex.Message}");
        }
    }
    
    private void OnExitButtonClicked()
    {
        AddLog("[Info] Exit requested via button");
        ExitRequested?.Invoke(this, EventArgs.Empty);
    }
    
    private void OnKeyPress(View.KeyEventEventArgs args)
    {
        if (args.KeyEvent.Key == (Key.Q | Key.CtrlMask))
        {
            AddLog("[Info] Exit requested via Ctrl+Q");
            ExitRequested?.Invoke(this, EventArgs.Empty);
            args.Handled = true;
        }
    }
    
    private void OnInputFieldKeyPress(View.KeyEventEventArgs args)
    {
        if (args.KeyEvent.Key == Key.Enter)
        {
            OnSendButtonClicked();
            args.Handled = true;
        }
    }
    
    private void ScrollToEnd(TextView textView)
    {
        if (textView == null || textView.Text == null)
            return;
            
        // Count the number of lines by counting newline characters
        string text = textView.Text.ToString() ?? string.Empty;
        if (string.IsNullOrEmpty(text))
            return;
            
        int lineCount = text.Count(c => c == '\n') + 1;
        
        textView.CursorPosition = new Point(0, Math.Max(0, lineCount - 1));
    }
} 