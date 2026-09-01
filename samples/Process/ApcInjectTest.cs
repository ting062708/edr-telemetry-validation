using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace ApcInjectTest
{
    internal class Program
    {
        private const string TargetPath = @"C:\EDRTest\samples\Process\ProcessTarget.exe";

        // P/Invoke: process injection primitives
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr VirtualAllocEx(IntPtr hProcess, IntPtr lpAddress, uint dwSize, uint flAllocationType, uint flProtect);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool WriteProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, uint nSize, out UIntPtr lpNumberOfBytesWritten);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenThread(uint dwDesiredAccess, bool bInheritHandle, uint dwThreadId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint QueueUserAPC(IntPtr pfnAPC, IntPtr hThread, UIntPtr dwData);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private const uint PROCESS_ALL_ACCESS = 0x001F0FFF;
        private const uint MEM_COMMIT = 0x1000;
        private const uint MEM_RESERVE = 0x2000;
        private const uint PAGE_EXECUTE_READWRITE = 0x40;
        private const uint THREAD_SET_CONTEXT = 0x0010;

        // Minimal x64 APC payload: a plain "ret" (the APC routine just returns).
        private static readonly byte[] Shellcode = { 0xC3 };

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "PROC-TAMPER-002")
            {
                Console.Error.WriteLine("Usage: ApcInjectTest.exe --case PROC-TAMPER-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Process Action=APCInject");
            Write("[META] Process=ApcInjectTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            Process target = null;
            IntPtr hProcess = IntPtr.Zero;
            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                Write("[SETUP] TargetPath=" + TargetPath);
                if (!File.Exists(TargetPath)) throw new IOException("ProcessTarget.exe not found: " + TargetPath);
                target = Process.Start(new ProcessStartInfo(TargetPath) { UseShellExecute = false });
                Thread.Sleep(1000); // let the target fully start + spawn its threads
                Write("[SETUP] TargetPid=" + target.Id);
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=QueueUserAPC");
                Write("[TARGET] TargetPid=" + target.Id);

                hProcess = OpenProcess(PROCESS_ALL_ACCESS, false, target.Id);
                if (hProcess == IntPtr.Zero) throw new IOException("OpenProcess failed. Win32Error=" + Marshal.GetLastWin32Error());
                Write("[TARGET] OpenProcess=OK");

                IntPtr remote = VirtualAllocEx(hProcess, IntPtr.Zero, (uint)Shellcode.Length, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
                if (remote == IntPtr.Zero) throw new IOException("VirtualAllocEx failed. Win32Error=" + Marshal.GetLastWin32Error());
                Write("[TARGET] AllocatedBase=0x" + remote.ToString("X"));

                UIntPtr written;
                if (!WriteProcessMemory(hProcess, remote, Shellcode, (uint)Shellcode.Length, out written))
                    throw new IOException("WriteProcessMemory failed. Win32Error=" + Marshal.GetLastWin32Error());
                Write("[TARGET] BytesWritten=" + written);

                int queued = 0;
                target.Refresh();
                foreach (ProcessThread t in target.Threads)
                {
                    IntPtr hThread = OpenThread(THREAD_SET_CONTEXT, false, (uint)t.Id);
                    if (hThread == IntPtr.Zero) continue;
                    uint r = QueueUserAPC(remote, hThread, UIntPtr.Zero);
                    if (r != 0) queued++;
                    CloseHandle(hThread);
                }
                Write("[TARGET] ApcQueued=" + queued);
                if (queued == 0) throw new IOException("QueueUserAPC queued zero threads.");

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
                if (hProcess != IntPtr.Zero) CloseHandle(hProcess);
                if (target != null) { try { if (!target.HasExited) target.Kill(); } catch { } }
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
