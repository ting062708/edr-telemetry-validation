using System;
using System.Diagnostics;
using System.IO;

namespace TaskXmlTest
{
    internal class Program
    {
        private const string TaskName = "EDRTelemetryTaskXml";
        private const string XmlPath = @"C:\EDRTest\samples\ScheduleTask\EDRTelemetryTask.xml";

        private const string TaskXml =
            "<?xml version=\"1.0\" encoding=\"UTF-16\"?>" +
            "<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">" +
            "  <Triggers><TimeTrigger><StartBoundary>2026-01-01T00:00:00</StartBoundary></TimeTrigger></Triggers>" +
            "  <Actions><Exec><Command>cmd.exe</Command><Arguments>/c exit</Arguments></Exec></Actions>" +
            "  <Settings><Enabled>true</Enabled></Settings>" +
            "</Task>";

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "TASK-CREATE-002")
            {
                Console.Error.WriteLine("Usage: TaskXmlTest.exe --case TASK-CREATE-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=ScheduleTask Action=SchedTaskCreateXml");
            Write("[META] Process=TaskXmlTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                File.WriteAllText(XmlPath, TaskXml, System.Text.Encoding.Unicode);
                Write("[SETUP] XmlPath=" + XmlPath);
                RunCmd("schtasks /delete /tn " + TaskName + " /f");
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=SchedTaskCreate");
                Write("[TARGET] TaskName=" + TaskName);
                Write("[TARGET] Method=XMLImport");

                RunCmd("schtasks /create /tn " + TaskName + " /xml " + XmlPath + " /f");
                string q = RunCmd("schtasks /query /tn " + TaskName + " /fo LIST");
                if (q.IndexOf(TaskName, StringComparison.OrdinalIgnoreCase) < 0)
                    throw new IOException("Scheduled task was not created.");

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
                RunCmd("schtasks /delete /tn " + TaskName + " /f");
                Write("[RESULT] " + (exitCode == 0 ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
                Write("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow());
            }
            return exitCode;
        }

        private static string RunCmd(string cmd)
        {
            var psi = new ProcessStartInfo("cmd.exe", "/c " + cmd)
            {
                UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            using (var p = Process.Start(psi))
            {
                string o = p.StandardOutput.ReadToEnd();
                p.WaitForExit();
                return o;
            }
        }

        private static string UtcNow() { return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"); }
        private static void Write(string line) { Console.WriteLine(line); Console.Out.Flush(); }
        private static string Safe(string v) { return string.IsNullOrEmpty(v) ? "Unknown error" : v.Replace("\r", " ").Replace("\n", " "); }
    }
}
