using System;
using System.Diagnostics;
using System.IO;

namespace FileJsonTest
{
    internal class Program
    {
        private const string TestDir = @"C:\EDRTest\samples\File";
        private const string JsonFileName = "EDRTelemetryFileTest.json";
        private const string JsonContent = "{\"module\":\"File\",\"action\":\"create\",\"marker\":\"EDRTelemetryFileTest\"}";

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "FILE-CREATE-002")
            {
                Console.Error.WriteLine("Usage: FileJsonTest.exe --case FILE-CREATE-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=File Action=FileCreateJson");
            Write("[META] Process=FileJsonTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                string fullPath = Path.Combine(TestDir, JsonFileName);
                if (File.Exists(fullPath)) File.Delete(fullPath);
                Write("[SETUP] TargetPath=" + fullPath);
                Write("[SETUP] FileType=json");
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=FileCreate");
                Write("[TARGET] TargetPath=" + fullPath);
                Write("[TARGET] FileType=json");

                File.WriteAllText(fullPath, JsonContent);
                System.Threading.Thread.Sleep(500);
                if (!File.Exists(fullPath)) throw new IOException("JSON file was not created: " + fullPath);
                Write("[TARGET] FileSize=" + new FileInfo(fullPath).Length);
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

        private static string UtcNow() { return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"); }
        private static void Write(string line) { Console.WriteLine(line); Console.Out.Flush(); }
        private static string Safe(string v) { return string.IsNullOrEmpty(v) ? "Unknown error" : v.Replace("\r", " ").Replace("\n", " "); }
    }
}
