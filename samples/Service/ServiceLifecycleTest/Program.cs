using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;

namespace ServiceLifecycleTest
{
    internal class Program
    {
        private const string ServiceName = "EDR_Telemetry_Test_Service";
        private const string InitialDisplayName = "EDR Telemetry Test Service";
        private const string ModifiedDisplayName = "EDR Telemetry Test Service Modified";

        private const uint SC_MANAGER_CONNECT = 0x0001;
        private const uint SC_MANAGER_CREATE_SERVICE = 0x0002;
        private const uint SERVICE_QUERY_CONFIG = 0x0001;
        private const uint SERVICE_CHANGE_CONFIG = 0x0002;
        private const uint DELETE = 0x00010000;
        private const uint SERVICE_WIN32_OWN_PROCESS = 0x00000010;
        private const uint SERVICE_DEMAND_START = 0x00000003;
        private const uint SERVICE_DISABLED = 0x00000004;
        private const uint SERVICE_ERROR_NORMAL = 0x00000001;
        private const uint SERVICE_NO_CHANGE = 0xFFFFFFFF;
        private const int ERROR_SERVICE_DOES_NOT_EXIST = 1060;
        private const int ERROR_SERVICE_MARKED_FOR_DELETE = 1072;

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenSCManager(string machineName, string databaseName, uint desiredAccess);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenService(IntPtr scmHandle, string serviceName, uint desiredAccess);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateService(
            IntPtr scmHandle, string serviceName, string displayName, uint desiredAccess,
            uint serviceType, uint startType, uint errorControl, string binaryPath,
            string loadOrderGroup, IntPtr tagId, string dependencies,
            string serviceStartName, string password);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool ChangeServiceConfig(
            IntPtr serviceHandle, uint serviceType, uint startType, uint errorControl,
            string binaryPath, string loadOrderGroup, IntPtr tagId, string dependencies,
            string serviceStartName, string password, string displayName);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool DeleteService(IntPtr serviceHandle);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool CloseServiceHandle(IntPtr handle);

        private static int Main(string[] args)
        {
            string runId = Guid.NewGuid().ToString("D");
            string caseId;

            if (!TryGetCaseId(args, out caseId) || !IsKnownCase(caseId))
            {
                BeginRun(runId, caseId ?? "UNKNOWN", "Unknown");
                Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
                Console.WriteLine("[SETUP] Error=Usage: ServiceLifecycleTest.exe --case <SVC-CREATE-001|SVC-MODIFY-001|SVC-DELETE-001>");
                Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                EndRun(runId, false, 2, "Invalid CaseID or arguments.");
                return 2;
            }

            string action = GetAction(caseId);
            BeginRun(runId, caseId, action);

            if (!IsAdministrator())
            {
                Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
                Console.WriteLine("[SETUP] Administrator=False");
                Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                EndRun(runId, false, 3, "Administrator privileges required.");
                return 3;
            }

            IntPtr scm = IntPtr.Zero;
            IntPtr service = IntPtr.Zero;

            try
            {
                scm = OpenSCManager(null, null, SC_MANAGER_CONNECT | SC_MANAGER_CREATE_SERVICE);
                if (scm == IntPtr.Zero)
                    return FinishWin32Failure(runId, "OpenSCManager", 1);

                string cmd = Path.Combine(Environment.SystemDirectory, "cmd.exe");
                string binaryPath = "\"" + cmd + "\" /c exit 0";

                Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
                Console.WriteLine("[SETUP] ServiceName=" + ServiceName);
                Console.WriteLine("[SETUP] BinaryPath=" + binaryPath);

                if (caseId == "SVC-CREATE-001")
                {
                    if (!EnsureServiceAbsent(scm))
                    {
                        Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                        EndRun(runId, false, 3, "Could not establish clean service state.");
                        return 3;
                    }
                    Console.WriteLine("[SETUP] InitialState=Absent");
                }
                else
                {
                    if (!EnsureServiceAbsent(scm))
                    {
                        Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                        EndRun(runId, false, 3, "Could not establish clean service state.");
                        return 3;
                    }

                    service = CreateBaselineService(scm, binaryPath);
                    if (service == IntPtr.Zero)
                    {
                        int error = Marshal.GetLastWin32Error();
                        Console.WriteLine("[SETUP] Win32Error=" + error);
                        Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                        EndRun(runId, false, 3, "Failed to create baseline service.");
                        return 3;
                    }
                    Console.WriteLine("[SETUP] InitialState=Present");
                    Console.WriteLine("[SETUP] StartType=Manual");
                    Console.WriteLine("[SETUP] DisplayName=" + InitialDisplayName);
                }

                Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + TimestampUtc());

                bool targetOk;
                if (caseId == "SVC-CREATE-001")
                {
                    service = CreateBaselineService(scm, binaryPath);
                    targetOk = service != IntPtr.Zero;
                    if (targetOk)
                    {
                        Console.WriteLine("[TARGET] ServiceName=" + ServiceName);
                        Console.WriteLine("[TARGET] Operation=CreateService");
                        Console.WriteLine("[TARGET] DisplayName=" + InitialDisplayName);
                        Console.WriteLine("[TARGET] StartType=Manual");
                    }
                }
                else if (caseId == "SVC-MODIFY-001")
                {
                    targetOk = ChangeServiceConfig(
                        service,
                        SERVICE_NO_CHANGE,
                        SERVICE_DISABLED,
                        SERVICE_NO_CHANGE,
                        null, null, IntPtr.Zero, null, null, null,
                        ModifiedDisplayName);

                    if (targetOk)
                    {
                        Console.WriteLine("[TARGET] ServiceName=" + ServiceName);
                        Console.WriteLine("[TARGET] Operation=ChangeServiceConfig");
                        Console.WriteLine("[TARGET] StartTypeBefore=Manual");
                        Console.WriteLine("[TARGET] StartTypeAfter=Disabled");
                        Console.WriteLine("[TARGET] DisplayNameAfter=" + ModifiedDisplayName);
                    }
                }
                else
                {
                    targetOk = DeleteService(service);
                    if (targetOk)
                    {
                        Console.WriteLine("[TARGET] ServiceName=" + ServiceName);
                        Console.WriteLine("[TARGET] Operation=DeleteService");
                        Console.WriteLine("[TARGET] DeleteRequested=True");
                    }
                }

                if (!targetOk)
                {
                    int error = Marshal.GetLastWin32Error();
                    Console.WriteLine("[TARGET] Win32Error=" + error);
                    Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());
                    CleanupAfterTarget(scm, ref service, caseId);
                    EndRun(runId, false, 1, "Target service operation failed.");
                    return 1;
                }

                Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());

                // Post-target restoration is intentionally outside the TARGET window.
                CleanupAfterTarget(scm, ref service, caseId);

                EndRun(runId, true, 0, null);
                return 0;
            }
            catch (Exception ex)
            {
                EndRun(runId, false, 1, ex.GetType().Name + ": " + ex.Message);
                return 1;
            }
            finally
            {
                if (service != IntPtr.Zero)
                    CloseServiceHandle(service);
                if (scm != IntPtr.Zero)
                    CloseServiceHandle(scm);
            }
        }

        private static IntPtr CreateBaselineService(IntPtr scm, string binaryPath)
        {
            return CreateService(
                scm,
                ServiceName,
                InitialDisplayName,
                SERVICE_QUERY_CONFIG | SERVICE_CHANGE_CONFIG | DELETE,
                SERVICE_WIN32_OWN_PROCESS,
                SERVICE_DEMAND_START,
                SERVICE_ERROR_NORMAL,
                binaryPath,
                null,
                IntPtr.Zero,
                null,
                null,
                null);
        }

        private static bool EnsureServiceAbsent(IntPtr scm)
        {
            IntPtr existing = OpenService(scm, ServiceName, DELETE | SERVICE_QUERY_CONFIG);
            if (existing == IntPtr.Zero)
            {
                int error = Marshal.GetLastWin32Error();
                if (error == ERROR_SERVICE_DOES_NOT_EXIST)
                    return true;
                if (error == ERROR_SERVICE_MARKED_FOR_DELETE)
                    return WaitUntilAbsent(scm, 5000);
                return false;
            }

            try
            {
                if (!DeleteService(existing))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error != ERROR_SERVICE_MARKED_FOR_DELETE)
                        return false;
                }
            }
            finally
            {
                CloseServiceHandle(existing);
            }

            return WaitUntilAbsent(scm, 5000);
        }

        private static bool WaitUntilAbsent(IntPtr scm, int timeoutMs)
        {
            Stopwatch sw = Stopwatch.StartNew();
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                IntPtr handle = OpenService(scm, ServiceName, SERVICE_QUERY_CONFIG);
                if (handle == IntPtr.Zero)
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == ERROR_SERVICE_DOES_NOT_EXIST)
                        return true;
                }
                else
                {
                    CloseServiceHandle(handle);
                }
                Thread.Sleep(100);
            }
            return false;
        }

        private static void CleanupAfterTarget(IntPtr scm, ref IntPtr service, string caseId)
        {
            if (service != IntPtr.Zero)
            {
                if (caseId != "SVC-DELETE-001")
                    DeleteService(service);

                CloseServiceHandle(service);
                service = IntPtr.Zero;
            }

            WaitUntilAbsent(scm, 5000);
        }

        private static bool TryGetCaseId(string[] args, out string caseId)
        {
            caseId = null;
            if (args == null)
                return false;

            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
                {
                    caseId = args[i + 1];
                    return true;
                }
            }
            return false;
        }

        private static bool IsKnownCase(string caseId)
        {
            return caseId == "SVC-CREATE-001" ||
                   caseId == "SVC-MODIFY-001" ||
                   caseId == "SVC-DELETE-001";
        }

        private static string GetAction(string caseId)
        {
            if (caseId == "SVC-CREATE-001") return "Create";
            if (caseId == "SVC-MODIFY-001") return "Modify";
            if (caseId == "SVC-DELETE-001") return "Delete";
            return "Unknown";
        }

        private static void BeginRun(string runId, string caseId, string action)
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + TimestampUtc());
            Console.WriteLine("[META] TestCaseID=" + caseId + " Module=Service Action=" + action);
            Console.WriteLine("[META] Process=ServiceLifecycleTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);
        }

        private static void EndRun(string runId, bool pass, int exitCode, string error)
        {
            if (!string.IsNullOrEmpty(error))
                Console.WriteLine("[ERROR] Message=" + Sanitize(error));
            Console.WriteLine("[RESULT] " + (pass ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
            Console.WriteLine("[RUN-END] RunID=" + runId + " TimeUTC=" + TimestampUtc());
        }

        private static int FinishWin32Failure(string runId, string function, int exitCode)
        {
            int error = Marshal.GetLastWin32Error();
            EndRun(runId, false, exitCode, function + " failed. Win32 error: " + error);
            return exitCode;
        }

        private static bool IsAdministrator()
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
        }

        private static string TimestampUtc()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static string Sanitize(string value)
        {
            return (value ?? string.Empty).Replace("\r", " ").Replace("\n", " ");
        }
    }
}
