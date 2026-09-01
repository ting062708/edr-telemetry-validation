using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace SvcCreateTest
{
    internal class Program
    {
        private const string ServiceName = "EDRTelemetrySvcCreate";

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr OpenSCManager(string lpMachineName, string lpDatabaseName, uint dwDesiredAccess);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr CreateService(IntPtr hSCManager, string lpServiceName, string lpDisplayName,
            uint dwDesiredAccess, uint dwServiceType, uint dwStartType, uint dwErrorControl,
            string lpBinaryPathName, string lpLoadOrderGroup, string lpdwTagId, string lpDependencies,
            string lpServiceStartName, string lpPassword);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool DeleteService(IntPtr hService);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool CloseServiceHandle(IntPtr hSCObject);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr OpenService(IntPtr hSCManager, string lpServiceName, uint dwDesiredAccess);

        private const uint SC_MANAGER_CREATE_SERVICE = 0x0002;
        private const uint SERVICE_ALL_ACCESS = 0xF01FF;
        private const uint SERVICE_WIN32_OWN_PROCESS = 0x00000010;
        private const uint SERVICE_DEMAND_START = 0x00000003;
        private const uint SERVICE_ERROR_NORMAL = 0x00000001;
        private const uint DELETE = 0x00010000;

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "SVC-CREATE-002")
            {
                Console.Error.WriteLine("Usage: SvcCreateTest.exe --case SVC-CREATE-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Service Action=CreateService");
            Write("[META] Process=SvcCreateTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            IntPtr scm = IntPtr.Zero;
            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                scm = OpenSCManager(null, null, SC_MANAGER_CREATE_SERVICE);
                if (scm == IntPtr.Zero) throw new InvalidOperationException("OpenSCManager failed. Win32Error=" + Marshal.GetLastWin32Error());
                // 清理旧服务
                IntPtr old = OpenService(scm, ServiceName, DELETE);
                if (old != IntPtr.Zero) { DeleteService(old); CloseServiceHandle(old); }
                Write("[SETUP] ServiceName=" + ServiceName);
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=CreateService");
                Write("[TARGET] ServiceName=" + ServiceName);

                IntPtr svc = CreateService(scm, ServiceName, ServiceName, SERVICE_ALL_ACCESS,
                    SERVICE_WIN32_OWN_PROCESS, SERVICE_DEMAND_START, SERVICE_ERROR_NORMAL,
                    @"C:\Windows\System32\cmd.exe", null, null, null, null, null);
                if (svc == IntPtr.Zero) throw new InvalidOperationException("CreateService failed. Win32Error=" + Marshal.GetLastWin32Error());
                Write("[TARGET] ServiceHandle=" + svc);
                System.Threading.Thread.Sleep(500);
                CloseServiceHandle(svc);

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
                if (scm != IntPtr.Zero)
                {
                    IntPtr old = OpenService(scm, ServiceName, DELETE);
                    if (old != IntPtr.Zero) { DeleteService(old); CloseServiceHandle(old); }
                    CloseServiceHandle(scm);
                }
                Write("[RESULT] " + (exitCode == 0 ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
                Write("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow());
            }
            return exitCode;
        }

        private static string UtcNow() { return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"); }
        private static void Write(string line) { Console.WriteLine(line); Console.Out.Flush(); }
        private static string Safe(string v) { return string.IsNullOrEmpty(v) ? "Unknown error" : v.Replace("\r", " ").Replace("\n", " "); }
    }
}
