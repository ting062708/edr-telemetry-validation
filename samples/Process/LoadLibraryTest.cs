using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace LoadLibraryTest
{
    internal class Program
    {
        private const string DllPath = @"C:\EDRTest\samples\Process\Support\TestLibrary.dll";

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr LoadLibrary(string lpFileName);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool FreeLibrary(IntPtr hModule);

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "PROC-IMAGE-LOAD-002")
            {
                Console.Error.WriteLine("Usage: LoadLibraryTest.exe --case PROC-IMAGE-LOAD-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Process Action=ImageLoad");
            Write("[META] Process=LoadLibraryTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                Write("[SETUP] DllPath=" + DllPath);
                if (!File.Exists(DllPath))
                {
                    Write("[SETUP] Required=Missing");
                    throw new IOException("TestLibrary.dll not found: " + DllPath);
                }
                Write("[SETUP] Required=Present");
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=LoadLibrary");
                Write("[TARGET] DllPath=" + DllPath);

                IntPtr h = LoadLibrary(DllPath);
                if (h == IntPtr.Zero)
                {
                    Write("[TARGET] ModuleHandle=0");
                    throw new IOException("LoadLibrary failed. Win32Error=" + Marshal.GetLastWin32Error());
                }
                Write("[TARGET] ModuleHandle=" + h);
                System.Threading.Thread.Sleep(500);
                FreeLibrary(h);
                Write("[TARGET] Freed=true");
                Write("[TARGET-END] TimeUTC=" + UtcNow());
                exitCode = 0;
            }
            catch (Exception ex)
            {
                Write("[ERROR] " + ex.GetType().Name + ": " + Safe(ex.Message));
                exitCode = 1;
            }
            finally
            {
                Write("[RESULT] " + (exitCode == 0 ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
                Write("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow());
            }
            return exitCode;
        }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static void Write(string line)
        {
            Console.WriteLine(line);
            Console.Out.Flush();
        }

        private static string Safe(string value)
        {
            if (string.IsNullOrEmpty(value)) return "Unknown error";
            return value.Replace("\r", " ").Replace("\n", " ");
        }
    }
}
