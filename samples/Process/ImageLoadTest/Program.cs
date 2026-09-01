using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace ImageLoadTest
{
    internal class Program
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibrary(string lpFileName);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true)]
        private static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool FreeLibrary(IntPtr hModule);

        [UnmanagedFunctionPointer(CallingConvention.Winapi)]
        private delegate uint GetTestMarkerDelegate();

        private static readonly string RunId = Guid.NewGuid().ToString("N");
        private static readonly string Hostname = Environment.MachineName;
        private static readonly int Pid = Process.GetCurrentProcess().Id;

        private static string NowUtc() =>
            DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");

        private static int Main()
        {
            Console.WriteLine($"[RUN-BEGIN] RunID={RunId} TimeUTC={NowUtc()}");
            Console.WriteLine("[META] TestCaseID=PROC-IMAGE-LOAD-001");
            Console.WriteLine("[META] Module=Process");
            Console.WriteLine("[META] Action=imageload");
            Console.WriteLine("[META] Process=ImageLoadTest.exe");
            Console.WriteLine($"[META] PID={Pid}");
            Console.WriteLine($"[META] Hostname={Hostname}");
            Console.WriteLine($"[META] RunStartUTC={NowUtc()}");

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string dllPath = Path.Combine(baseDir, "Support", "TestLibrary.dll");

            // ── SETUP ──────────────────────────────────────────────────────
            Console.WriteLine($"[SETUP-BEGIN] TimeUTC={NowUtc()}");
            Console.WriteLine($"[SETUP] DllPath={dllPath}");
            bool dllExists = File.Exists(dllPath);
            Console.WriteLine($"[SETUP] DllExists={(dllExists ? "PASS" : "FAIL")}");
            Console.WriteLine($"[SETUP-END] TimeUTC={NowUtc()}");

            if (!dllExists)
            {
                Console.WriteLine("[RESULT] FAIL ExitCode=1");
                Console.WriteLine("[ERROR] TestLibrary.dll not found.");
                Console.WriteLine($"[ERROR] Expected={dllPath}");
                Console.WriteLine($"[RUN-END] RunID={RunId} TimeUTC={NowUtc()}");
                return 1;
            }

            IntPtr module = IntPtr.Zero;
            int exitCode = 1;

            try
            {
                // ── TARGET: LoadLibrary ────────────────────────────────────
                Console.WriteLine($"[TARGET-BEGIN] TimeUTC={NowUtc()}");
                Console.WriteLine("[TARGET] Operation=LoadLibrary");
                Console.WriteLine($"[TARGET] DllPath={dllPath}");
                Console.WriteLine("[TARGET] ExportFunction=GetTestMarker");

                module = LoadLibrary(dllPath);
                if (module == IntPtr.Zero)
                {
                    int err = Marshal.GetLastWin32Error();
                    Console.WriteLine($"[TARGET] LoadLibraryResult=FAIL");
                    Console.WriteLine($"[TARGET] Win32Error={err}");
                    Console.WriteLine($"[TARGET-END] TimeUTC={NowUtc()}");
                    Console.WriteLine("[RESULT] FAIL ExitCode=1");
                    Console.WriteLine("[ERROR] LoadLibrary failed.");
                    Console.WriteLine($"[ERROR] Win32 error: {err}");
                    Console.WriteLine($"[RUN-END] RunID={RunId} TimeUTC={NowUtc()}");
                    return 1;
                }
                Console.WriteLine("[TARGET] LoadLibraryResult=PASS");
                Console.WriteLine($"[TARGET] ModuleHandle=0x{module.ToInt64():X}");

                IntPtr fn = GetProcAddress(module, "GetTestMarker");
                if (fn == IntPtr.Zero)
                {
                    int err = Marshal.GetLastWin32Error();
                    Console.WriteLine($"[TARGET] GetProcAddressResult=FAIL");
                    Console.WriteLine($"[TARGET] Win32Error={err}");
                    Console.WriteLine($"[TARGET-END] TimeUTC={NowUtc()}");
                    Console.WriteLine("[RESULT] FAIL ExitCode=1");
                    Console.WriteLine("[ERROR] GetTestMarker export not found.");
                    Console.WriteLine($"[ERROR] Win32 error: {err}");
                    Console.WriteLine($"[RUN-END] RunID={RunId} TimeUTC={NowUtc()}");
                    return 1;
                }
                Console.WriteLine("[TARGET] GetProcAddressResult=PASS");

                var marker = (GetTestMarkerDelegate)Marshal.GetDelegateForFunctionPointer(
                    fn, typeof(GetTestMarkerDelegate));
                uint m = marker();
                Console.WriteLine($"[TARGET] TestMarker=0x{m:X}");

                // Hold the DLL loaded so EDR has time to capture the image-load.
                Console.WriteLine("[TARGET] HoldingLoaded=15000ms");
                Thread.Sleep(15000);

                Console.WriteLine($"[TARGET-END] TimeUTC={NowUtc()}");

                Console.WriteLine("[RESULT] PASS ExitCode=0");
                exitCode = 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[RESULT] FAIL ExitCode=1");
                Console.WriteLine($"[ERROR] {ex.GetType().Name}: {ex.Message}");
                exitCode = 1;
            }
            finally
            {
                if (module != IntPtr.Zero)
                {
                    bool freed = FreeLibrary(module);
                    Console.WriteLine($"[SETUP] FreeLibrary={freed}");
                }
                Console.WriteLine($"[RUN-END] RunID={RunId} TimeUTC={NowUtc()}");
            }

            return exitCode;
        }
    }
}
