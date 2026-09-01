using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Security.Principal;

namespace ScheduledTaskLifecycleTest
{
    internal class Program
    {
        private const string TaskName = "EDR_Telemetry_Test_Task";
        private const string TaskPath = "\\EDR_Telemetry_Test_Task";
        private const string CommandPath = @"C:\Windows\System32\cmd.exe";
        private const string CommandArgs = "/c exit 0";

        private static int Main(string[] args)
        {
            string caseId;
            if (!TryGetCase(args, out caseId))
            {
                Console.WriteLine("[ERROR] Usage: ScheduledTaskLifecycleTest.exe --case TASK-CREATE-001|TASK-MODIFY-001|TASK-DELETE-001");
                return 2;
            }

            string action = GetAction(caseId);
            if (action == null)
            {
                Console.WriteLine("[ERROR] Unknown TestCaseID=" + caseId);
                return 2;
            }

            string runId = Guid.NewGuid().ToString("N");
            RunBegin(runId);
            Console.WriteLine("[META] TestCaseID=" + caseId + " Module=ScheduledTask Action=" + action);
            Console.WriteLine("[META] Process=ScheduledTaskLifecycleTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                switch (caseId)
                {
                    case "TASK-CREATE-001": RunCreate(); break;
                    case "TASK-MODIFY-001": RunModify(); break;
                    case "TASK-DELETE-001": RunDelete(); break;
                }

                Console.WriteLine("[RESULT] PASS ExitCode=0");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[ERROR] " + Sanitize(FormatException(ex)));
                Console.WriteLine("[RESULT] FAIL ExitCode=1");
                return 1;
            }
            finally
            {
                RunEnd(runId);
            }
        }

        private static void RunCreate()
        {
            SetupBegin();
            DeleteTaskIfPresent();
            string trigger = XmlTime(DateTime.Now.AddHours(24));
            string xmlPath = WriteTaskXml("EDR Scheduled Task Creation Test", trigger, CommandPath, CommandArgs, Environment.UserName);
            Console.WriteLine("[SETUP] TaskName=" + TaskName);
            Console.WriteLine("[SETUP] Trigger=" + trigger);
            SetupEnd();

            TargetBegin();
            RunSchtasks("/create /tn \"" + TaskName + "\" /xml \"" + xmlPath + "\" /f");
            Console.WriteLine("[TARGET] TaskName=" + TaskName);
            Console.WriteLine("[TARGET] TaskPath=" + TaskPath);
            Console.WriteLine("[TARGET] Operation=Create");
            Console.WriteLine("[TARGET] Command=" + CommandPath);
            Console.WriteLine("[TARGET] CommandArgs=" + CommandArgs);
            Console.WriteLine("[TARGET] Author=" + Environment.UserName);
            Console.WriteLine("[TARGET] Description=EDR Scheduled Task Creation Test");
            TargetEnd();
        }

        private static void RunModify()
        {
            SetupBegin();
            DeleteTaskIfPresent();
            string baseTrigger = XmlTime(DateTime.Now.AddHours(24));
            string baseXml = WriteTaskXml("EDR Scheduled Task Baseline", baseTrigger, CommandPath, CommandArgs, Environment.UserName);
            RunSchtasks("/create /tn \"" + TaskName + "\" /xml \"" + baseXml + "\" /f");
            Console.WriteLine("[SETUP] TaskName=" + TaskName);
            Console.WriteLine("[SETUP] BaselineTrigger=" + baseTrigger);
            SetupEnd();

            string modTrigger = XmlTime(DateTime.Now.AddHours(48));
            string modXml = WriteTaskXml("EDR Scheduled Task Modification Test", modTrigger, CommandPath, CommandArgs, Environment.UserName);
            TargetBegin();
            RunSchtasks("/create /tn \"" + TaskName + "\" /xml \"" + modXml + "\" /f");
            Console.WriteLine("[TARGET] TaskName=" + TaskName);
            Console.WriteLine("[TARGET] TaskPath=" + TaskPath);
            Console.WriteLine("[TARGET] Operation=Modify");
            Console.WriteLine("[TARGET] Command=" + CommandPath);
            Console.WriteLine("[TARGET] CommandArgs=" + CommandArgs);
            Console.WriteLine("[TARGET] Author=" + Environment.UserName);
            Console.WriteLine("[TARGET] Description=EDR Scheduled Task Modification Test");
            TargetEnd();
        }

        private static void RunDelete()
        {
            SetupBegin();
            DeleteTaskIfPresent();
            string baseTrigger = XmlTime(DateTime.Now.AddHours(24));
            string baseXml = WriteTaskXml("EDR Scheduled Task Delete Baseline", baseTrigger, CommandPath, CommandArgs, Environment.UserName);
            RunSchtasks("/create /tn \"" + TaskName + "\" /xml \"" + baseXml + "\" /f");
            Console.WriteLine("[SETUP] TaskName=" + TaskName);
            Console.WriteLine("[SETUP] BaselineState=Present");
            SetupEnd();

            TargetBegin();
            RunSchtasks("/delete /tn \"" + TaskName + "\" /f");
            Console.WriteLine("[TARGET] TaskName=" + TaskName);
            Console.WriteLine("[TARGET] TaskPath=" + TaskPath);
            Console.WriteLine("[TARGET] Operation=Delete");
            Console.WriteLine("[TARGET] Command=" + CommandPath);
            Console.WriteLine("[TARGET] CommandArgs=" + CommandArgs);
            Console.WriteLine("[TARGET] Author=" + Environment.UserName);
            Console.WriteLine("[TARGET] Description=EDR Scheduled Task Delete Baseline");
            Console.WriteLine("[TARGET] FinalState=Absent");
            TargetEnd();
        }

        private static string WriteTaskXml(string description, string triggerTime, string command, string arguments, string author)
        {
            string sid;
            try { sid = WindowsIdentity.GetCurrent().User.Value; }
            catch { sid = ""; }

            var sb = new StringBuilder();
            sb.AppendLine("<?xml version=\"1.0\" encoding=\"UTF-16\"?>");
            sb.AppendLine("<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">");
            sb.AppendLine("  <RegistrationInfo>");
            sb.AppendLine("    <Description>" + description + "</Description>");
            sb.AppendLine("    <Author>" + author + "</Author>");
            sb.AppendLine("  </RegistrationInfo>");
            sb.AppendLine("  <Triggers>");
            sb.AppendLine("    <TimeTrigger>");
            sb.AppendLine("      <StartBoundary>" + triggerTime + "</StartBoundary>");
            sb.AppendLine("      <Enabled>true</Enabled>");
            sb.AppendLine("    </TimeTrigger>");
            sb.AppendLine("  </Triggers>");
            sb.AppendLine("  <Principals>");
            sb.AppendLine("    <Principal id=\"Author\">");
            sb.AppendLine("      <UserId>" + sid + "</UserId>");
            sb.AppendLine("      <LogonType>InteractiveToken</LogonType>");
            sb.AppendLine("      <RunLevel>LeastPrivilege</RunLevel>");
            sb.AppendLine("    </Principal>");
            sb.AppendLine("  </Principals>");
            sb.AppendLine("  <Settings>");
            sb.AppendLine("    <Enabled>true</Enabled>");
            sb.AppendLine("    <Hidden>false</Hidden>");
            sb.AppendLine("    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>");
            sb.AppendLine("  </Settings>");
            sb.AppendLine("  <Actions Context=\"Author\">");
            sb.AppendLine("    <Exec>");
            sb.AppendLine("      <Command>" + command + "</Command>");
            sb.AppendLine("      <Arguments>" + arguments + "</Arguments>");
            sb.AppendLine("    </Exec>");
            sb.AppendLine("  </Actions>");
            sb.AppendLine("</Task>");

            string path = Path.Combine(Path.GetTempPath(), "edr_task_" + Guid.NewGuid().ToString("N").Substring(0, 8) + ".xml");
            File.WriteAllText(path, sb.ToString(), Encoding.Unicode);
            return path;
        }

        private static void RunSchtasks(string arguments)
        {
            string schtasks = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "schtasks.exe");
            using (var p = new Process())
            {
                p.StartInfo.FileName = schtasks;
                p.StartInfo.Arguments = arguments;
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.RedirectStandardOutput = true;
                p.StartInfo.RedirectStandardError = true;
                p.Start();
                string so = p.StandardOutput.ReadToEnd();
                string se = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0)
                    throw new InvalidOperationException("schtasks failed exit=" + p.ExitCode + " out=" + Sanitize(so) + " err=" + Sanitize(se));
            }
        }

        private static void DeleteTaskIfPresent()
        {
            try
            {
                string schtasks = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "schtasks.exe");
                using (var p = new Process())
                {
                    p.StartInfo.FileName = schtasks;
                    p.StartInfo.Arguments = "/delete /tn \"" + TaskName + "\" /f";
                    p.StartInfo.UseShellExecute = false;
                    p.StartInfo.CreateNoWindow = true;
                    p.Start();
                    p.WaitForExit();
                }
            }
            catch { }
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
                case "TASK-CREATE-001": return "Create";
                case "TASK-MODIFY-001": return "Modify";
                case "TASK-DELETE-001": return "Delete";
                default: return null;
            }
        }

        private static string XmlTime(DateTime value) { return value.ToString("yyyy-MM-dd'T'HH:mm:ss"); }
        private static string UtcNow() { return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"); }
        private static string Sanitize(string value) { return (value ?? "").Replace("\r", " ").Replace("\n", " "); }
        private static string FormatException(Exception ex)
        {
            return ex.GetType().Name + ": " + ex.Message + " | STACK: " + Sanitize(ex.StackTrace);
        }
        private static void RunBegin(string runId) { Console.WriteLine("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow()); }
        private static void RunEnd(string runId) { Console.WriteLine("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow()); }
        private static void SetupBegin() { Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow()); }
        private static void SetupEnd() { Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow()); }
        private static void TargetBegin() { Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow()); }
        private static void TargetEnd() { Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow()); }
    }
}
