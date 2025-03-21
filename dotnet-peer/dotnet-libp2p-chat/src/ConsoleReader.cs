// // SPDX-License-Identifier: MIT

// internal class ConsoleReader
// {
//     private readonly Queue<TaskCompletionSource<string>> _requests = new();
//     private bool _isRequested;

//     public Task<string> ReadLineAsync(CancellationToken token = default)
//     {
//         TaskCompletionSource<string> result = new();
//         token.Register(() => result.TrySetResult(""));

//         _requests.Enqueue(result);

//         if (!_isRequested)
//         {
//             _isRequested = true;
//             Task.Run(() =>
//             {
//                 string? input = Console.ReadLine();
//                 while (_requests.TryDequeue(out var src))
//                 {
//                     Task.Run(() => src.SetResult(input ?? ""));
//                 }
//                 _isRequested = false;
//             });
//         }

//         return result.Task;
//     }
// }

public class ConsoleReader
{
    private readonly AutoResetEvent _inputReady = new(false);
    private readonly Queue<string> _inputQueue = new();

    public ConsoleReader()
    {
        Task.Run(() =>
        {
            while (true)
            {
                string input = Console.ReadLine() ?? string.Empty;
                lock (_inputQueue)
                {
                    _inputQueue.Enqueue(input);
                }
                _inputReady.Set();
            }
        });
    }

    public async Task<string> ReadLineAsync()
    {
        while (true)
        {
            lock (_inputQueue)
            {
                if (_inputQueue.Count > 0)
                {
                    return _inputQueue.Dequeue();
                }
            }

            await Task.Run(() => _inputReady.WaitOne());
        }
    }
}
