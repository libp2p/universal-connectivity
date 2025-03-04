namespace Chat.UI.Themes;

public class DefaultTheme : ITheme
{
    public string FormatMessage(string username, string content)
    {
        return $"\x1B[34m{username}\x1B[0m: {content}";
    }

    public string FormatRoomList(IEnumerable<string> rooms)
    {
        return $"Available rooms:\n{string.Join("\n", rooms.Select(r => $"\x1B[32m{r}\x1B[0m"))}";
    }

    public string FormatSystemMessage(string message)
    {
        return $"\x1B[31m{message}\x1B[0m";
    }
}