namespace Chat.UI.Themes;

public class DefaultTheme : ITheme
{
    private const string Reset = "\x1B[0m";
    private const string Bold = "\x1B[1m";
    private const string Dim = "\x1B[2m";
    private const string Blue = "\x1B[34m";
    private const string Green = "\x1B[32m";
    private const string Yellow = "\x1B[33m";
    private const string Red = "\x1B[31m";
    private const string Cyan = "\x1B[36m";
    private const string Gray = "\x1B[90m";

    public string FormatMessage(string username, string content)
    {
        var timestamp = $"{Gray}[{DateTime.Now:HH:mm:ss}]{Reset}";
        return $"{timestamp} {Bold}{Blue}{username}{Reset}: {content}";
    }

    public string FormatRoomList(IEnumerable<string> rooms)
    {
        var header = $"{Bold}{Green}Available Rooms:{Reset}\n";
        var roomList = string.Join("\n", rooms.Select(r => $"  {Cyan}• {r}{Reset}"));
        return $"{header}{roomList}";
    }

    public string FormatSystemMessage(string message)
    {
        return $"{Yellow}[System] {message}{Reset}";
    }

    public string FormatErrorMessage(string message)
    {
        return $"{Red}[Error] {message}{Reset}";
    }

    public string FormatPeerStatus(string peerId, bool isConnected)
    {
        var status = isConnected ? $"{Green}●{Reset}" : $"{Gray}○{Reset}";
        return $"{status} {Dim}{peerId}{Reset}";
    }

    public string FormatHelp()
    {
        return $@"{Bold}{Green}Available Commands:{Reset}
  {Cyan}/join <room>{Reset} - Join a chat room
  {Cyan}/leave <room>{Reset} - Leave a chat room
  {Cyan}/rooms{Reset} - List available rooms
  {Cyan}/peers{Reset} - List connected peers
  {Cyan}/connect <address>{Reset} - Connect to a peer
  {Cyan}/help{Reset} - Show this help message";
    }
}