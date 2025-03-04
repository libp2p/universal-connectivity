using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Chat.Core.Interfaces;
using Chat.Services;
using Chat.UI;
using Chat.UI.Themes;

var services = new ServiceCollection()
    .AddLogging(builder => builder.AddConsole())
    .AddSingleton<IMessageStore, InMemoryMessageStore>()
    .AddSingleton<IChatService, ChatService>()
    .AddSingleton<IUserInterface, ConsoleUI>()
    .AddSingleton<ITheme, DefaultTheme>()
    .BuildServiceProvider();

try
{
    var ui = services.GetRequiredService<IUserInterface>();
    await ui.RunAsync(CancellationToken.None);
}
catch (Exception ex)
{
    var logger = services.GetRequiredService<ILogger<Program>>();
    logger.LogError(ex, "An error occurred while running the application.");
}
