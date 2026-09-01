using System;
using System.Diagnostics;
using System.Threading;

namespace ProcessTarget
{
    internal class Program
    {
        private static int Main(string[] args)
        {
            Console.Title = "EDR Process Target";
            Console.WriteLine("[TARGET-READY] Process=ProcessTarget.exe");
            Console.WriteLine("[TARGET-READY] PID=" + Process.GetCurrentProcess().Id);
            Console.WriteLine("[TARGET-READY] StartUTC=" + DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"));

            // 默认存活 60 秒（够 EDR 采集），支持命令行参数指定秒数
            int seconds = 60;
            if (args.Length >= 1 && int.TryParse(args[0], out int parsed) && parsed > 0)
            {
                seconds = parsed;
            }

            Console.WriteLine("[TARGET-READY] LifetimeSeconds=" + seconds);
            Thread.Sleep(TimeSpan.FromSeconds(seconds));
            return 0;
        }
    }
}