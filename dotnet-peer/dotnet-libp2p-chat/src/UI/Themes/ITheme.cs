namespace Chat.UI.Themes;

public interface ITheme
{
    string FormatMessage(string username, string content);
    string FormatSystemMessage(string message);
    string FormatErrorMessage(string message);
    string FormatRoomList(IEnumerable<string> rooms);
    string FormatPeerStatus(string peerId, bool isConnected);
    string FormatHelp();
}