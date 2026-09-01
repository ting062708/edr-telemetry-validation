using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;

namespace FileLifecycleTest
{
    internal class Program
    {
        private const string OriginalName = "FileLifecycle_Target.exe";
        private const string RenamedName = "FileLifecycle_Renamed.exe";

        private static int Main(string[] args)
        {
            string caseId = ParseCaseId(args);
            if (string.IsNullOrWhiteSpace(caseId))
            {
                PrintUsage();
                return 2;
            }

            caseId = caseId.Trim().ToUpperInvariant();
            if (!IsSupportedCase(caseId))
            {
                Console.WriteLine("[ERROR] Unsupported TestCaseID=" + caseId);
                PrintUsage();
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            string processName = Process.GetCurrentProcess().ProcessName + ".exe";
            int pid = Process.GetCurrentProcess().Id;
            string hostname = Environment.MachineName;
            string action = GetAction(caseId);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string originalPath = Path.Combine(baseDir, OriginalName);
            string renamedPath = Path.Combine(baseDir, RenamedName);

            WriteRunBegin(runId);
            Console.WriteLine("[META] TestCaseID={0} Module=File Action={1}", caseId, action);
            Console.WriteLine("[META] Process={0} PID={1} Hostname={2}", processName, pid, hostname);

            try
            {
                WriteSetupBegin();
                PrepareCase(caseId, originalPath, renamedPath);
                WriteSetupEnd();
            }
            catch (Exception ex)
            {
                // Keep the frozen protocol parseable even when setup fails.
                WriteSetupEnd();
                Console.WriteLine("[ERROR] Stage=Setup Type={0} Message={1}", ex.GetType().Name, OneLine(ex.Message));
                WriteResult(false, 1);
                WriteRunEnd(runId);
                return 1;
            }

            bool targetStarted = false;
            try
            {
                WriteTargetBegin();
                targetStarted = true;
                ExecuteTarget(caseId, originalPath, renamedPath);
                WriteTargetEnd();
                WriteResult(true, 0);
                WriteRunEnd(runId);
                return 0;
            }
            catch (Exception ex)
            {
                if (targetStarted)
                {
                    WriteTargetEnd();
                }

                Console.WriteLine("[ERROR] Stage=Target Type={0} Message={1}", ex.GetType().Name, OneLine(ex.Message));
                WriteResult(false, 1);
                WriteRunEnd(runId);
                return 1;
            }
        }

        private static void PrepareCase(string caseId, string originalPath, string renamedPath)
        {
            // SETUP may generate file telemetry. That is intentional: the runner/parser
            // correlates the event under test using only TARGET-BEGIN..TARGET-END.
            RemoveIfExists(originalPath, "StaleOriginalRemoved");
            RemoveIfExists(renamedPath, "StaleRenamedRemoved");

            switch (caseId)
            {
                case "FILE-CREATE-001":
                    Console.WriteLine("[SETUP] TargetAbsent=true");
                    Console.WriteLine("[SETUP] TargetPath=" + originalPath);
                    break;

                case "FILE-OPEN-001":
                case "FILE-DELETE-001":
                case "FILE-MODIFY-001":
                    CreateBaselineFile(originalPath, caseId);
                    Console.WriteLine("[SETUP] BaselineCreated=true");
                    Console.WriteLine("[SETUP] TargetPath=" + originalPath);
                    break;

                case "FILE-RENAME-001":
                    CreateBaselineFile(originalPath, caseId);
                    Console.WriteLine("[SETUP] SourcePrepared=" + originalPath);
                    Console.WriteLine("[SETUP] DestinationAbsent=" + renamedPath);
                    break;
            }
        }

        private static void ExecuteTarget(string caseId, string originalPath, string renamedPath)
        {
            switch (caseId)
            {
                case "FILE-CREATE-001":
                    RunCreate(originalPath);
                    break;
                case "FILE-OPEN-001":
                    RunOpen(originalPath);
                    break;
                case "FILE-DELETE-001":
                    RunDelete(originalPath);
                    break;
                case "FILE-MODIFY-001":
                    RunModify(originalPath);
                    break;
                case "FILE-RENAME-001":
                    RunRename(originalPath, renamedPath);
                    break;
                default:
                    throw new InvalidOperationException("Unsupported TestCaseID: " + caseId);
            }
        }

        private static void RunCreate(string path)
        {
            // Pure create: create the file handle and close it WITHOUT writing.
            // A CreateNew+Write+Flush sequence is coalesced by the IOA sensor into
            // FileWriteClose; a create-only sequence leaves a distinct FileCreate.
            using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
            {
                // No Write()/Flush() here on purpose.
            }

            if (!File.Exists(path))
                throw new IOException("File creation verification failed.");

            Console.WriteLine("[TARGET] Path=" + path);
            Console.WriteLine("[TARGET] Operation=Create");
            Console.WriteLine("[TARGET] Size=" + new FileInfo(path).Length);
        }

        private static void RunOpen(string path)
        {
            string content;
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
            {
                content = reader.ReadToEnd();
            }

            if (content.Length == 0)
                throw new IOException("File open/read verification returned no content.");

            Console.WriteLine("[TARGET] Path=" + path);
            Console.WriteLine("[TARGET] Operation=Open");
            Console.WriteLine("[TARGET] CharactersRead=" + content.Length);
        }

        private static void RunDelete(string path)
        {
            // The SETUP stage creates the baseline file (FileWriteClose) and the
            // TARGET stage deletes it. Without a pause both land in the same
            // millisecond and the IOA sensor coalesces the create->delete
            // sequence into a single event, dropping the distinct FileDelete.
            // Sleep here so the delete is recorded as its own FileDelete event.
            System.Threading.Thread.Sleep(2000);

            File.Delete(path);
            if (File.Exists(path))
                throw new IOException("File deletion verification failed.");

            Console.WriteLine("[TARGET] Path=" + path);
            Console.WriteLine("[TARGET] Operation=Delete");
        }

        private static void RunModify(string path)
        {
            long beforeSize = new FileInfo(path).Length;
            string modification = "EDR_FILE_MODIFICATION_TEST\r\nModifiedUTC=" + UtcNow() + "\r\n";
            byte[] bytes = Encoding.UTF8.GetBytes(modification);

            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Write, FileShare.Read))
            {
                stream.Seek(0, SeekOrigin.End);
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            long afterSize = new FileInfo(path).Length;
            if (afterSize <= beforeSize)
                throw new IOException("File modification verification failed.");

            Console.WriteLine("[TARGET] Path=" + path);
            Console.WriteLine("[TARGET] Operation=Modify");
            Console.WriteLine("[TARGET] SizeBefore=" + beforeSize);
            Console.WriteLine("[TARGET] SizeAfter=" + afterSize);
        }

        private static void RunRename(string sourcePath, string destinationPath)
        {
            File.Move(sourcePath, destinationPath);
            if (File.Exists(sourcePath) || !File.Exists(destinationPath))
                throw new IOException("File rename verification failed.");

            Console.WriteLine("[TARGET] SourcePath=" + sourcePath);
            Console.WriteLine("[TARGET] DestinationPath=" + destinationPath);
            Console.WriteLine("[TARGET] Operation=Rename");
        }

        private static void CreateBaselineFile(string path, string caseId)
        {
            string content =
                "EDR_FILE_PRECONDITION\r\n" +
                "Case=" + caseId + "\r\n" +
                "PreparedUTC=" + UtcNow() + "\r\n";

            byte[] bytes = Encoding.UTF8.GetBytes(content);
            using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            if (!File.Exists(path))
                throw new IOException("Baseline file creation failed.");
        }

        private static void RemoveIfExists(string path, string key)
        {
            if (File.Exists(path))
            {
                File.Delete(path);
                Console.WriteLine("[SETUP] " + key + "=true");
            }
            else
            {
                Console.WriteLine("[SETUP] " + key + "=false");
            }
        }

        private static string ParseCaseId(string[] args)
        {
            if (args == null || args.Length == 0)
                return null;

            if (args.Length == 1)
            {
                if (IsHelp(args[0]))
                    return null;
                return args[0];
            }

            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            }

            return null;
        }

        private static bool IsHelp(string value)
        {
            return string.Equals(value, "--help", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "-h", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "/?", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSupportedCase(string caseId)
        {
            return caseId == "FILE-CREATE-001" ||
                   caseId == "FILE-OPEN-001" ||
                   caseId == "FILE-DELETE-001" ||
                   caseId == "FILE-MODIFY-001" ||
                   caseId == "FILE-RENAME-001";
        }

        private static string GetAction(string caseId)
        {
            switch (caseId)
            {
                case "FILE-CREATE-001": return "Create";
                case "FILE-OPEN-001": return "Open";
                case "FILE-DELETE-001": return "Delete";
                case "FILE-MODIFY-001": return "Modify";
                case "FILE-RENAME-001": return "Rename";
                default: return "Unknown";
            }
        }

        private static void WriteRunBegin(string runId)
        {
            Console.WriteLine("[RUN-BEGIN] RunID={0} TimeUTC={1}", runId, UtcNow());
        }

        private static void WriteSetupBegin()
        {
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow());
        }

        private static void WriteSetupEnd()
        {
            Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow());
        }

        private static void WriteTargetBegin()
        {
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow());
        }

        private static void WriteTargetEnd()
        {
            Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow());
        }

        private static void WriteResult(bool pass, int exitCode)
        {
            Console.WriteLine("[RESULT] {0} ExitCode={1}", pass ? "PASS" : "FAIL", exitCode);
        }

        private static void WriteRunEnd(string runId)
        {
            Console.WriteLine("[RUN-END] RunID={0} TimeUTC={1}", runId, UtcNow());
        }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static string OneLine(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;
            return value.Replace('\r', ' ').Replace('\n', ' ');
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("  FileLifecycleTest.exe --case <TestCaseID>");
            Console.WriteLine("  FileLifecycleTest.exe <TestCaseID>");
            Console.WriteLine();
            Console.WriteLine("Supported TestCaseID values:");
            Console.WriteLine("  FILE-CREATE-001");
            Console.WriteLine("  FILE-OPEN-001");
            Console.WriteLine("  FILE-DELETE-001");
            Console.WriteLine("  FILE-MODIFY-001");
            Console.WriteLine("  FILE-RENAME-001");
        }
    }
}
