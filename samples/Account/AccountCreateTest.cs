using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace AccountCreateTest
{
    internal class Program
    {
        private const string UserName = "EDRAccountTest";
        private const string Password = "Test@12345";

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct USER_INFO_1
        {
            public string usri1_name;
            public string usri1_password;
            public int usri1_password_age;
            public int usri1_priv;
            public string usri1_home_dir;
            public string usri1_comment;
            public int usri1_flags;
            public string usri1_script_path;
        }

        [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern int NetUserAdd(string servername, int level, ref USER_INFO_1 buf, out int parm_err);

        [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern int NetUserDel(string servername, string username);

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "ACCOUNT-CREATE-002")
            {
                Console.Error.WriteLine("Usage: AccountCreateTest.exe --case ACCOUNT-CREATE-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Account Action=AccountCreate");
            Write("[META] Process=AccountCreateTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                NetUserDel(null, UserName);
                Write("[SETUP] UserName=" + UserName);
                Write("[SETUP] StaleUserRemoved=true");
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=AccountCreate");
                Write("[TARGET] UserName=" + UserName);
                Write("[TARGET] Method=NetUserAdd");

                USER_INFO_1 ui = new USER_INFO_1();
                ui.usri1_name = UserName;
                ui.usri1_password = Password;
                ui.usri1_priv = 1; // USER_PRIV_USER
                ui.usri1_flags = 1; // UF_SCRIPT
                int parmErr;
                int rc = NetUserAdd(null, 1, ref ui, out parmErr);
                Write("[TARGET] NetUserAddResult=" + rc);
                if (rc != 0) throw new InvalidOperationException("NetUserAdd failed. rc=" + rc + " parm_err=" + parmErr);

                System.Threading.Thread.Sleep(500);
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
                NetUserDel(null, UserName);
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
