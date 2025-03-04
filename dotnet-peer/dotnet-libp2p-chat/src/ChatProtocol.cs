// using Nethermind.Libp2p.Core;

// public class ChatProtocol : SymmetricProtocol
// {
//     protected override async Task ConnectAsync(IChannel channel, IConnectionContext context, bool isListener)
//     {
//         var reader = channel.Reader;
//         var writer = channel.Writer;

//         _ = Task.Run(async () =>
//         {
//             while (true)
//             {
//                 var input = Console.ReadLine();
//                 if (string.IsNullOrEmpty(input))
//                     continue;

//                 await writer.WriteAsync(System.Text.Encoding.UTF8.GetBytes(input));
//             }
//         });

//         try
//         {
//             while (true)
//             {
//                 var message = await reader.ReadAsync();
//                 var text = System.Text.Encoding.UTF8.GetString(message);
//                 Console.WriteLine($"Received: {text}");
//             }
//         }
//         catch (Exception)
//         {
//             Console.WriteLine("Connection closed");
//         }
//     }
// }