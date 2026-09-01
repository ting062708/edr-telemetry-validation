using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;

namespace DriverLifecycleTest
{
    internal class Program
    {
        private const string ServiceName = "EDR_Telemetry_Test_Driver";
        private const uint SC_MANAGER_CONNECT = 0x0001;
        private const uint SC_MANAGER_CREATE_SERVICE = 0x0002;
        private const uint SERVICE_QUERY_STATUS = 0x0004;
        private const uint SERVICE_START = 0x0010;
        private const uint SERVICE_STOP = 0x0020;
        private const uint DELETE = 0x00010000;
        private const uint SERVICE_KERNEL_DRIVER = 0x00000001;
        private const uint SERVICE_DEMAND_START = 0x00000003;
        private const uint SERVICE_ERROR_NORMAL = 0x00000001;
        private const uint SERVICE_CONTROL_STOP = 0x00000001;
        private const uint SERVICE_STOPPED = 0x00000001;
        private const uint SERVICE_RUNNING = 0x00000004;
        private const int ERROR_SERVICE_DOES_NOT_EXIST = 1060;
        private const int ERROR_SERVICE_NOT_ACTIVE = 1062;

        [StructLayout(LayoutKind.Sequential)]
        private struct SERVICE_STATUS
        {
            public uint dwServiceType;
            public uint dwCurrentState;
            public uint dwControlsAccepted;
            public uint dwWin32ExitCode;
            public uint dwServiceSpecificExitCode;
            public uint dwCheckPoint;
            public uint dwWaitHint;
        }

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenSCManager(string machineName, string databaseName, uint desiredAccess);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenService(IntPtr scmHandle, string serviceName, uint desiredAccess);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateService(IntPtr scmHandle, string serviceName, string displayName,
            uint desiredAccess, uint serviceType, uint startType, uint errorControl, string binaryPath,
            string loadOrderGroup, IntPtr tagId, string dependencies, string serviceStartName, string password);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool StartService(IntPtr serviceHandle, int argumentCount, string[] arguments);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool QueryServiceStatus(IntPtr serviceHandle, out SERVICE_STATUS status);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool ControlService(IntPtr serviceHandle, uint control, out SERVICE_STATUS status);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool DeleteService(IntPtr serviceHandle);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool CloseServiceHandle(IntPtr handle);

        private static int Main(string[] args)
        {
            string caseId;
            if (!TryGetCase(args, out caseId))
            {
                Console.WriteLine("[ERROR] Usage: DriverLifecycleTest.exe --case DRIVER-LOAD-001|DRIVER-MODIFY-001|DRIVER-UNLOAD-001");
                return 2;
            }

            string action = GetAction(caseId);
            if (action == null)
            {
                Console.WriteLine("[ERROR] Unknown TestCaseID=" + caseId);
                return 2;
            }

            string runId = Guid.NewGuid().ToString("N");
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string driverPath = Path.Combine(baseDir, "Support", "nonpnp.sys");
            string modificationTarget = Path.Combine(baseDir, "DriverModification_Target.sys");

            RunBegin(runId);
            Console.WriteLine("[META] TestCaseID=" + caseId + " Module=Driver Action=" + action);
            Console.WriteLine("[META] Process=DriverLifecycleTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            int exitCode = 1;
            try
            {
                if (!IsAdministrator())
                    throw new InvalidOperationException("Administrator privileges required.");
                if (!File.Exists(driverPath))
                    throw new FileNotFoundException("Support\\nonpnp.sys not found.", driverPath);

                switch (caseId)
                {
                    case "DRIVER-LOAD-001":
                        RunLoad(driverPath);
                        break;
                    case "DRIVER-MODIFY-001":
                        RunModify(driverPath, modificationTarget);
                        break;
                    case "DRIVER-UNLOAD-001":
                        RunUnload(driverPath);
                        break;
                }

                exitCode = 0;
                Console.WriteLine("[RESULT] PASS ExitCode=0");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[ERROR] " + Sanitize(ex.GetType().Name + ": " + ex.Message));
                Console.WriteLine("[RESULT] FAIL ExitCode=1");
                return 1;
            }
            finally
            {
                RunEnd(runId);
            }
        }

        private static void RunLoad(string driverPath)
        {
            IntPtr scm = IntPtr.Zero;
            IntPtr service = IntPtr.Zero;
            try
            {
                SetupBegin();
                scm = OpenScm();
                EnsureServiceAbsent(scm);
                service = CreateDriverService(scm, driverPath);
                Console.WriteLine("[SETUP] DriverPath=" + driverPath);
                Console.WriteLine("[SETUP] ServiceName=" + ServiceName);
                SetupEnd();

                TargetBegin();
                if (!StartService(service, 0, null))
                    ThrowWin32("StartService");
                if (!WaitForState(service, SERVICE_RUNNING, 15000))
                    throw new InvalidOperationException("Driver did not reach RUNNING state.");
                Console.WriteLine("[TARGET] DriverPath=" + driverPath);
                Console.WriteLine("[TARGET] ServiceName=" + ServiceName);
                Console.WriteLine("[TARGET] State=RUNNING");
                TargetEnd();
            }
            finally
            {
                if (service != IntPtr.Zero)
                {
                    TryStopService(service);
                    DeleteService(service);
                    CloseServiceHandle(service);
                }
                if (scm != IntPtr.Zero) CloseServiceHandle(scm);
            }
        }

        private static void RunModify(string driverPath, string modificationTarget)
        {
            SetupBegin();
            if (File.Exists(modificationTarget)) File.Delete(modificationTarget);
            File.Copy(driverPath, modificationTarget, true);
            string beforeHash = GetSha256(modificationTarget);
            long beforeSize = new FileInfo(modificationTarget).Length;
            Console.WriteLine("[SETUP] SourceDriverPath=" + driverPath);
            Console.WriteLine("[SETUP] TargetPath=" + modificationTarget);
            Console.WriteLine("[SETUP] BeforeSHA256=" + beforeHash);
            Console.WriteLine("[SETUP] BeforeSize=" + beforeSize);
            SetupEnd();

            try
            {
                string marker = "\r\nEDR_DRIVER_MODIFICATION_TEST_" + DateTime.UtcNow.ToString("yyyyMMdd_HHmmssfff");
                byte[] bytes = Encoding.ASCII.GetBytes(marker);

                TargetBegin();
                using (FileStream fs = new FileStream(modificationTarget, FileMode.Open, FileAccess.Write, FileShare.Read))
                {
                    fs.Seek(0, SeekOrigin.End);
                    fs.Write(bytes, 0, bytes.Length);
                    fs.Flush(true);
                }
                string afterHash = GetSha256(modificationTarget);
                long afterSize = new FileInfo(modificationTarget).Length;
                if (beforeSize >= afterSize || string.Equals(beforeHash, afterHash, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Driver modification verification failed.");
                Console.WriteLine("[TARGET] TargetPath=" + modificationTarget);
                Console.WriteLine("[TARGET] BeforeSHA256=" + beforeHash);
                Console.WriteLine("[TARGET] AfterSHA256=" + afterHash);
                Console.WriteLine("[TARGET] BeforeSize=" + beforeSize);
                Console.WriteLine("[TARGET] AfterSize=" + afterSize);
                TargetEnd();
            }
            finally
            {
                try { if (File.Exists(modificationTarget)) File.Delete(modificationTarget); } catch { }
            }
        }

        private static void RunUnload(string driverPath)
        {
            IntPtr scm = IntPtr.Zero;
            IntPtr service = IntPtr.Zero;
            try
            {
                SetupBegin();
                scm = OpenScm();
                EnsureServiceAbsent(scm);
                service = CreateDriverService(scm, driverPath);
                if (!StartService(service, 0, null))
                    ThrowWin32("StartService setup");
                if (!WaitForState(service, SERVICE_RUNNING, 15000))
                    throw new InvalidOperationException("Driver did not reach RUNNING state during setup.");
                Console.WriteLine("[SETUP] DriverPath=" + driverPath);
                Console.WriteLine("[SETUP] ServiceName=" + ServiceName);
                Console.WriteLine("[SETUP] InitialState=RUNNING");
                SetupEnd();

                TargetBegin();
                SERVICE_STATUS stopStatus;
                if (!ControlService(service, SERVICE_CONTROL_STOP, out stopStatus))
                    ThrowWin32("ControlService");
                if (!WaitForState(service, SERVICE_STOPPED, 15000))
                    throw new InvalidOperationException("Driver did not reach STOPPED state.");
                Console.WriteLine("[TARGET] DriverPath=" + driverPath);
                Console.WriteLine("[TARGET] ServiceName=" + ServiceName);
                Console.WriteLine("[TARGET] State=STOPPED");
                TargetEnd();
            }
            finally
            {
                if (service != IntPtr.Zero)
                {
                    DeleteService(service);
                    CloseServiceHandle(service);
                }
                if (scm != IntPtr.Zero) CloseServiceHandle(scm);
            }
        }

        private static IntPtr OpenScm()
        {
            IntPtr scm = OpenSCManager(null, null, SC_MANAGER_CONNECT | SC_MANAGER_CREATE_SERVICE);
            if (scm == IntPtr.Zero) ThrowWin32("OpenSCManager");
            return scm;
        }

        private static void EnsureServiceAbsent(IntPtr scm)
        {
            IntPtr existing = OpenService(scm, ServiceName, SERVICE_QUERY_STATUS | SERVICE_STOP | DELETE);
            if (existing == IntPtr.Zero)
            {
                int err = Marshal.GetLastWin32Error();
                if (err != ERROR_SERVICE_DOES_NOT_EXIST) ThrowWin32("OpenService verification", err);
                return;
            }
            try
            {
                TryStopService(existing);
                if (!DeleteService(existing)) ThrowWin32("DeleteService setup");
            }
            finally { CloseServiceHandle(existing); }
        }

        private static IntPtr CreateDriverService(IntPtr scm, string driverPath)
        {
            IntPtr service = CreateService(scm, ServiceName, "EDR Telemetry Test Driver",
                SERVICE_QUERY_STATUS | SERVICE_START | SERVICE_STOP | DELETE,
                SERVICE_KERNEL_DRIVER, SERVICE_DEMAND_START, SERVICE_ERROR_NORMAL,
                driverPath, null, IntPtr.Zero, null, null, null);
            if (service == IntPtr.Zero) ThrowWin32("CreateService");
            return service;
        }

        private static void TryStopService(IntPtr service)
        {
            SERVICE_STATUS status;
            if (QueryServiceStatus(service, out status) && status.dwCurrentState != SERVICE_STOPPED)
            {
                if (!ControlService(service, SERVICE_CONTROL_STOP, out status))
                {
                    int err = Marshal.GetLastWin32Error();
                    if (err != ERROR_SERVICE_NOT_ACTIVE) return;
                }
                WaitForState(service, SERVICE_STOPPED, 5000);
            }
        }

        private static bool WaitForState(IntPtr service, uint desiredState, int timeoutMs)
        {
            Stopwatch stopwatch = Stopwatch.StartNew();
            while (stopwatch.ElapsedMilliseconds < timeoutMs)
            {
                SERVICE_STATUS status;
                if (!QueryServiceStatus(service, out status)) return false;
                if (status.dwCurrentState == desiredState) return true;
                Thread.Sleep(250);
            }
            return false;
        }

        private static string GetSha256(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                return BitConverter.ToString(sha.ComputeHash(fs)).Replace("-", "").ToLowerInvariant();
        }

        private static bool IsAdministrator()
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
                return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }

        private static bool TryGetCase(string[] args, out string caseId)
        {
            caseId = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
                {
                    caseId = args[i + 1].Trim().ToUpperInvariant();
                    return caseId.Length > 0;
                }
            }
            return false;
        }

        private static string GetAction(string caseId)
        {
            switch (caseId)
            {
                case "DRIVER-LOAD-001": return "Load";
                case "DRIVER-MODIFY-001": return "Modify";
                case "DRIVER-UNLOAD-001": return "Unload";
                default: return null;
            }
        }

        private static void ThrowWin32(string function) { ThrowWin32(function, Marshal.GetLastWin32Error()); }
        private static void ThrowWin32(string function, int error) { throw new InvalidOperationException(function + " failed. Win32 error: " + error); }
        private static string UtcNow() { return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"); }
        private static string Sanitize(string value) { return (value ?? "").Replace("\r", " ").Replace("\n", " "); }
        private static void RunBegin(string runId) { Console.WriteLine("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow()); }
        private static void RunEnd(string runId) { Console.WriteLine("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow()); }
        private static void SetupBegin() { Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow()); }
        private static void SetupEnd() { Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow()); }
        private static void TargetBegin() { Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow()); }
        private static void TargetEnd() { Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow()); }
    }
}
