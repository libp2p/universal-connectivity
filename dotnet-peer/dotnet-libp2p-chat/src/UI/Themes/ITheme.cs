namespace Chat.UI.Themes;

public interface ITheme
{
    string FormatMessage(string username, string content);
    string FormatSystemMessage(string content);
    string FormatRoomList(IEnumerable<string> rooms);
}