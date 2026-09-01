using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;

namespace AccountLifecycleTest
{
    internal class Program
    {
        private const string UserName = "EDR_Test_User";
        private const string Password = "EdrT3st!2026_Aa";
        private const string CreatedComment = "EDR Account Lifecycle Test";
        private const string ModifiedComment = "EDR Account Lifecycle Modified";

        private const uint NERR_SUCCESS = 0;
        private const uint NERR_USER_NOT_FOUND = 2221;
        private const uint NERR_USER_EXISTS = 2224;
        private const uint USER_PRIV_USER = 1;
        private const uint UF_SCRIPT = 0x0001;
        private const uint UF_NORMAL_ACCOUNT = 0x0200;

        private const int LOGON32_LOGON_INTERACTIVE = 2;
        private const int LOGON32_PROVIDER_DEFAULT = 0;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct USER_INFO_1
        {
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1_name;
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1_password;
            public uint usri1_password_age;
            public uint usri1_priv;
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1_home_dir;
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1_comment;
            public uint usri1_flags;
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1_script_path;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct USER_INFO_1007
        {
            [MarshalAs(UnmanagedType.LPWStr)] public string usri1007_comment;
        }

        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint NetUserAdd(
            string serverName,
            uint level,
            ref USER_INFO_1 buffer,
            out uint parameterError);

        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint NetUserSetInfo(
            string serverName,
            string userName,
            uint level,
            ref USER_INFO_1007 buffer,
            out uint parameterError);

        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint NetUserDel(string serverName, string userName);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool LogonUser(
            string userName,
            string domain,
            string password,
            int logonType,
            int logonProvider,
            out IntPtr token);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        private sealed class CaseDefinition
        {
            public string Id { get; set; }
            public string Action { get; set; }
        }

        private static int Main(string[] args)
        {
            string caseId = ParseCaseId(args);
            CaseDefinition testCase = GetCase(caseId);

            if (testCase == null)
            {
                Console.Error.WriteLine("Usage: AccountLifecycleTest.exe --case <TestCaseID>");
                Console.Error.WriteLine("Cases: ACCOUNT-CREATE-001, ACCOUNT-MODIFY-001, ACCOUNT-DELETE-001, ACCOUNT-LOGIN-001, ACCOUNT-LOGOFF-001");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            string processName = Process.GetCurrentProcess().ProcessName + ".exe";
            int pid = Process.GetCurrentProcess().Id;
            string hostname = Environment.MachineName;
            IntPtr token = IntPtr.Zero;
            bool accountExistsAfterSetup = false;
            bool targetSucceeded = false;
            int exitCode = 1;

            RunBegin(runId);
            Console.WriteLine("[META] TestCaseID=" + testCase.Id + " Module=Account Action=" + testCase.Action);
            Console.WriteLine("[META] Process=" + processName + " PID=" + pid + " Hostname=" + hostname);

            if (!IsAdministrator())
            {
                Error("Administrator privileges required.");
                Result(false, 1);
                RunEnd(runId);
                return 1;
            }

            try
            {
                SetupBegin();

                switch (testCase.Id)
                {
                    case "ACCOUNT-CREATE-001":
                        RemoveAccountIfPresent();
                        Console.WriteLine("[SETUP] Account=.\\" + UserName);
                        Console.WriteLine("[SETUP] DesiredState=Absent");
                        break;

                    case "ACCOUNT-MODIFY-001":
                    case "ACCOUNT-DELETE-001":
                    case "ACCOUNT-LOGIN-001":
                        CreateFreshAccount();
                        accountExistsAfterSetup = true;
                        Console.WriteLine("[SETUP] Account=.\\" + UserName);
                        Console.WriteLine("[SETUP] DesiredState=Present");
                        break;

                    case "ACCOUNT-LOGOFF-001":
                        CreateFreshAccount();
                        accountExistsAfterSetup = true;
                        token = CreateInteractiveLogon();
                        Console.WriteLine("[SETUP] Account=.\\" + UserName);
                        Console.WriteLine("[SETUP] DesiredState=LoggedOn");
                        Console.WriteLine("[SETUP] LogonType=Interactive");
                        break;
                }

                SetupEnd();
                TargetBegin();

                switch (testCase.Id)
                {
                    case "ACCOUNT-CREATE-001":
                        CreateAccount();
                        accountExistsAfterSetup = true;
                        Console.WriteLine("[TARGET] Account=.\\" + UserName);
                        Console.WriteLine("[TARGET] Operation=Create");
                        break;

                    case "ACCOUNT-MODIFY-001":
                        ModifyAccount();
                        Console.WriteLine("[TARGET] Account=.\\" + UserName);
                        Console.WriteLine("[TARGET] Operation=Modify");
                        Console.WriteLine("[TARGET] Field=Comment");
                        Console.WriteLine("[TARGET] NewValue=" + ModifiedComment);
                        break;

                    case "ACCOUNT-DELETE-001":
                        DeleteAccount();
                        accountExistsAfterSetup = false;
                        Console.WriteLine("[TARGET] Account=.\\" + UserName);
                        Console.WriteLine("[TARGET] Operation=Delete");
                        break;

                    case "ACCOUNT-LOGIN-001":
                        token = CreateInteractiveLogon();
                        Console.WriteLine("[TARGET] Account=.\\" + UserName);
                        Console.WriteLine("[TARGET] Operation=Login");
                        Console.WriteLine("[TARGET] LogonType=Interactive");
                        break;

                    case "ACCOUNT-LOGOFF-001":
                        CloseLogonToken(ref token);
                        Console.WriteLine("[TARGET] Account=.\\" + UserName);
                        Console.WriteLine("[TARGET] Operation=Logoff");
                        Console.WriteLine("[TARGET] Mechanism=CloseLogonToken");
                        // Keep teardown inside the target window so delayed logoff
                        // telemetry can receive a timestamp within this case window.
                        Thread.Sleep(3000);
                        break;
                }

                TargetEnd();
                targetSucceeded = true;
                exitCode = 0;
            }
            catch (Exception ex)
            {
                Error(ex.GetType().Name + ": " + ex.Message);
                exitCode = 1;
            }
            finally
            {
                // Hygiene happens outside TARGET. The parser/correlator must use
                // TARGET-BEGIN..TARGET-END for the target telemetry window.
                try
                {
                    if (token != IntPtr.Zero)
                    {
                        CloseHandle(token);
                        token = IntPtr.Zero;
                        Console.WriteLine("[CLEANUP] LogonToken=Closed");
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("[CLEANUP] TokenCloseError=" + Sanitize(ex.Message));
                }

                try
                {
                    if (accountExistsAfterSetup)
                    {
                        uint cleanupStatus = NetUserDel(null, UserName);
                        Console.WriteLine("[CLEANUP] AccountDeleteStatus=" + cleanupStatus);
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("[CLEANUP] AccountDeleteError=" + Sanitize(ex.Message));
                }
            }

            Result(targetSucceeded, exitCode);
            RunEnd(runId);
            return exitCode;
        }

        private static string ParseCaseId(string[] args)
        {
            if (args == null || args.Length == 0)
                return null;

            if (args.Length == 1 && !args[0].StartsWith("-", StringComparison.Ordinal))
                return args[0].Trim().ToUpperInvariant();

            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    return args[i + 1].Trim().ToUpperInvariant();
            }

            return null;
        }

        private static CaseDefinition GetCase(string caseId)
        {
            switch (caseId)
            {
                case "ACCOUNT-CREATE-001": return new CaseDefinition { Id = caseId, Action = "Create" };
                case "ACCOUNT-MODIFY-001": return new CaseDefinition { Id = caseId, Action = "Modify" };
                case "ACCOUNT-DELETE-001": return new CaseDefinition { Id = caseId, Action = "Delete" };
                case "ACCOUNT-LOGIN-001": return new CaseDefinition { Id = caseId, Action = "Login" };
                case "ACCOUNT-LOGOFF-001": return new CaseDefinition { Id = caseId, Action = "Logoff" };
                default: return null;
            }
        }

        private static void CreateFreshAccount()
        {
            RemoveAccountIfPresent();
            CreateAccount();
        }

        private static void CreateAccount()
        {
            USER_INFO_1 userInfo = new USER_INFO_1
            {
                usri1_name = UserName,
                usri1_password = Password,
                usri1_password_age = 0,
                usri1_priv = USER_PRIV_USER,
                usri1_home_dir = null,
                usri1_comment = CreatedComment,
                usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT,
                usri1_script_path = null
            };

            uint parameterError;
            uint status = NetUserAdd(null, 1, ref userInfo, out parameterError);
            if (status != NERR_SUCCESS)
            {
                if (status == NERR_USER_EXISTS)
                    throw new InvalidOperationException("Test account already exists after setup cleanup.");

                throw new InvalidOperationException(
                    "NetUserAdd failed. Status=" + status + ", Parameter=" + parameterError);
            }
        }

        private static void ModifyAccount()
        {
            USER_INFO_1007 modifyInfo = new USER_INFO_1007
            {
                usri1007_comment = ModifiedComment
            };

            uint parameterError;
            uint status = NetUserSetInfo(null, UserName, 1007, ref modifyInfo, out parameterError);
            if (status != NERR_SUCCESS)
            {
                throw new InvalidOperationException(
                    "NetUserSetInfo failed. Status=" + status + ", Parameter=" + parameterError);
            }
        }

        private static void DeleteAccount()
        {
            uint status = NetUserDel(null, UserName);
            if (status != NERR_SUCCESS)
                throw new InvalidOperationException("NetUserDel failed. Status=" + status);
        }

        private static void RemoveAccountIfPresent()
        {
            uint status = NetUserDel(null, UserName);
            if (status != NERR_SUCCESS && status != NERR_USER_NOT_FOUND)
                throw new InvalidOperationException("Setup NetUserDel failed. Status=" + status);
        }

        private static IntPtr CreateInteractiveLogon()
        {
            IntPtr token;
            bool ok = LogonUser(
                UserName,
                ".",
                Password,
                LOGON32_LOGON_INTERACTIVE,
                LOGON32_PROVIDER_DEFAULT,
                out token);

            if (!ok || token == IntPtr.Zero)
            {
                int error = Marshal.GetLastWin32Error();
                throw new InvalidOperationException("LogonUser failed. Win32Error=" + error);
            }

            return token;
        }

        private static void CloseLogonToken(ref IntPtr token)
        {
            if (token == IntPtr.Zero)
                throw new InvalidOperationException("Logoff precondition failed: logon token is null.");

            if (!CloseHandle(token))
            {
                int error = Marshal.GetLastWin32Error();
                throw new InvalidOperationException("CloseHandle failed. Win32Error=" + error);
            }

            token = IntPtr.Zero;
        }

        private static bool IsAdministrator()
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
        }

        private static void RunBegin(string runId)
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + TimestampUtc());
        }

        private static void SetupBegin()
        {
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
        }

        private static void SetupEnd()
        {
            Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
        }

        private static void TargetBegin()
        {
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + TimestampUtc());
        }

        private static void TargetEnd()
        {
            Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());
        }

        private static void Result(bool pass, int exitCode)
        {
            Console.WriteLine("[RESULT] " + (pass ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
        }

        private static void Error(string message)
        {
            Console.WriteLine("[ERROR] " + Sanitize(message));
        }

        private static void RunEnd(string runId)
        {
            Console.WriteLine("[RUN-END] RunID=" + runId + " TimeUTC=" + TimestampUtc());
        }

        private static string TimestampUtc()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static string Sanitize(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            return value.Replace("\r", " ").Replace("\n", " ");
        }
    }
}
