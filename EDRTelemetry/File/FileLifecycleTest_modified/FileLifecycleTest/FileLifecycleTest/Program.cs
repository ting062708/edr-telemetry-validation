using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

namespace FileLifecycleTest
{
    internal class Program
    {
        private const string OriginalName = "FileLifecycle_Target.txt";
        private const string RenamedName = "FileLifecycle_Renamed.txt";
        private const int SetupDelayMilliseconds = 2000;
        private const int PostCaseDelayMilliseconds = 10000;

        private static int Main(string[] args)
        {
            string caseId = ParseCaseId(args);

            if (string.IsNullOrEmpty(caseId))
            {
                PrintUsage();
                return 2;
            }

            caseId = caseId.ToUpperInvariant();

            if (!IsSupportedCase(caseId))
            {
                Console.WriteLine("[RESULT] FAIL");
                Console.WriteLine("[ERROR] Unsupported TestCaseID: " + caseId);
                PrintUsage();
                return 2;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string originalPath = Path.Combine(baseDir, OriginalName);
            string renamedPath = Path.Combine(baseDir, RenamedName);

            PrintHeader(caseId, originalPath);

            try
            {
                PrepareCleanState(originalPath, renamedPath);

                int result;

                switch (caseId)
                {
                    case "FILE-CREATE-001":
                        result = RunCreate(originalPath);
                        break;

                    case "FILE-OPEN-001":
                        PrepareExistingFile(originalPath, caseId);
                        result = RunOpen(originalPath);
                        break;

                    case "FILE-MODIFY-001":
                        PrepareExistingFile(originalPath, caseId);
                        result = RunModify(originalPath);
                        break;

                    case "FILE-RENAME-001":
                        PrepareExistingFile(originalPath, caseId);
                        result = RunRename(originalPath, renamedPath);
                        break;

                    case "FILE-DELETE-001":
                        PrepareExistingFile(originalPath, caseId);
                        result = RunDelete(originalPath);
                        break;

                    default:
                        result = 2;
                        break;
                }

                if (result != 0)
                {
                    return result;
                }

                Console.WriteLine();
                Console.WriteLine("[RESULT] PASS");
                Console.WriteLine("[END] " + Timestamp());

                // Intentionally leave non-deletion test artifacts in place.
                // Cleaning them here would generate extra file telemetry after
                // the target phase. The next invocation removes stale artifacts
                // before its own target phase instead.
                Thread.Sleep(PostCaseDelayMilliseconds);
                return 0;
            }
            catch (Exception ex)
            {
                Fail(ex.GetType().Name + ": " + ex.Message);
                return 1;
            }
        }

        private static int RunCreate(string originalPath)
        {
            PhaseBegin("FILE-CREATE-001", "File Creation");

            string content =
                "EDR_FILE_CREATION_TEST\r\n" +
                "Created=" + Timestamp() + "\r\n";

            byte[] bytes = Encoding.UTF8.GetBytes(content);

            using (FileStream stream = new FileStream(
                originalPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.Read))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            if (!File.Exists(originalPath))
            {
                Fail("File creation verification failed.");
                return 1;
            }

            Console.WriteLine("[INFO] File created.");
            Console.WriteLine("[INFO] Path = " + originalPath);
            Console.WriteLine("[INFO] Size = " + new FileInfo(originalPath).Length);

            PhaseEnd("FILE-CREATE-001");
            return 0;
        }

        private static int RunOpen(string originalPath)
        {
            PhaseBegin("FILE-OPEN-001", "File Opened");

            string readContent;

            using (FileStream stream = new FileStream(
                originalPath,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite))
            using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
            {
                readContent = reader.ReadToEnd();
            }

            if (string.IsNullOrEmpty(readContent))
            {
                Fail("File read returned no content.");
                return 1;
            }

            Console.WriteLine("[INFO] File opened and read.");
            Console.WriteLine("[INFO] Path = " + originalPath);
            Console.WriteLine("[INFO] Characters Read = " + readContent.Length);

            PhaseEnd("FILE-OPEN-001");
            return 0;
        }

        private static int RunModify(string originalPath)
        {
            PhaseBegin("FILE-MODIFY-001", "File Modification");

            long beforeSize = new FileInfo(originalPath).Length;

            string modification =
                "EDR_FILE_MODIFICATION_TEST\r\n" +
                "Modified=" + Timestamp() + "\r\n";

            byte[] bytes = Encoding.UTF8.GetBytes(modification);

            using (FileStream stream = new FileStream(
                originalPath,
                FileMode.Open,
                FileAccess.Write,
                FileShare.Read))
            {
                stream.Seek(0, SeekOrigin.End);
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            long afterSize = new FileInfo(originalPath).Length;

            if (afterSize <= beforeSize)
            {
                Fail("File modification verification failed.");
                return 1;
            }

            Console.WriteLine("[INFO] Existing file modified.");
            Console.WriteLine("[INFO] Path = " + originalPath);
            Console.WriteLine("[INFO] Size Before = " + beforeSize);
            Console.WriteLine("[INFO] Size After  = " + afterSize);

            PhaseEnd("FILE-MODIFY-001");
            return 0;
        }

        private static int RunRename(string originalPath, string renamedPath)
        {
            PhaseBegin("FILE-RENAME-001", "File Renaming");

            File.Move(originalPath, renamedPath);

            if (File.Exists(originalPath) || !File.Exists(renamedPath))
            {
                Fail("File rename verification failed.");
                return 1;
            }

            Console.WriteLine("[INFO] File renamed.");
            Console.WriteLine("[INFO] Old Path = " + originalPath);
            Console.WriteLine("[INFO] New Path = " + renamedPath);

            PhaseEnd("FILE-RENAME-001");
            return 0;
        }

        private static int RunDelete(string originalPath)
        {
            PhaseBegin("FILE-DELETE-001", "File Deletion");

            File.Delete(originalPath);

            if (File.Exists(originalPath))
            {
                Fail("File deletion verification failed.");
                return 1;
            }

            Console.WriteLine("[INFO] File deleted.");
            Console.WriteLine("[INFO] Deleted Path = " + originalPath);

            PhaseEnd("FILE-DELETE-001");
            return 0;
        }

        private static void PrepareCleanState(string originalPath, string renamedPath)
        {
            bool changed = false;

            Console.WriteLine();
            Console.WriteLine("[SETUP-BEGIN] Clean stale test artifacts");
            Console.WriteLine("[TIME] " + Timestamp());

            if (File.Exists(originalPath))
            {
                Console.WriteLine("[SETUP] Removing stale file: " + originalPath);
                File.Delete(originalPath);
                changed = true;
            }

            if (File.Exists(renamedPath))
            {
                Console.WriteLine("[SETUP] Removing stale file: " + renamedPath);
                File.Delete(renamedPath);
                changed = true;
            }

            if (!changed)
            {
                Console.WriteLine("[SETUP] No stale test artifacts found.");
            }

            Console.WriteLine("[SETUP-END] Clean stale test artifacts");
            Console.WriteLine("[TIME] " + Timestamp());
        }

        private static void PrepareExistingFile(string originalPath, string caseId)
        {
            Console.WriteLine();
            Console.WriteLine("[SETUP-BEGIN] Prepare existing file for " + caseId);
            Console.WriteLine("[TIME] " + Timestamp());

            string content =
                "EDR_FILE_PRECONDITION\r\n" +
                "Case=" + caseId + "\r\n" +
                "Prepared=" + Timestamp() + "\r\n";

            byte[] bytes = Encoding.UTF8.GetBytes(content);

            using (FileStream stream = new FileStream(
                originalPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.Read))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            if (!File.Exists(originalPath))
            {
                throw new IOException("Precondition file creation failed.");
            }

            Console.WriteLine("[SETUP] Prepared Path = " + originalPath);
            Console.WriteLine("[SETUP-END] Prepare existing file for " + caseId);
            Console.WriteLine("[TIME] " + Timestamp());

            // Keep setup telemetry clearly separated from the target phase.
            Thread.Sleep(SetupDelayMilliseconds);
        }

        private static string ParseCaseId(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return null;
            }

            if (args.Length == 1)
            {
                if (args[0] == "--help" || args[0] == "-h" || args[0] == "/?")
                {
                    return null;
                }

                return args[0];
            }

            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                {
                    return args[i + 1];
                }
            }

            return null;
        }

        private static bool IsSupportedCase(string caseId)
        {
            return caseId == "FILE-CREATE-001" ||
                   caseId == "FILE-OPEN-001" ||
                   caseId == "FILE-DELETE-001" ||
                   caseId == "FILE-MODIFY-001" ||
                   caseId == "FILE-RENAME-001";
        }

        private static void PrintHeader(string caseId, string targetPath)
        {
            Console.WriteLine("========================================");
            Console.WriteLine("EDR TELEMETRY FILE TEST");
            Console.WriteLine("Module    : File");
            Console.WriteLine("Case      : " + caseId);
            Console.WriteLine("Process   : FileLifecycleTest.exe");
            Console.WriteLine("PID       : " + Process.GetCurrentProcess().Id);
            Console.WriteLine("Start     : " + Timestamp());
            Console.WriteLine("Target    : " + targetPath);
            Console.WriteLine("========================================");
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("  FileLifecycleTest.exe <TestCaseID>");
            Console.WriteLine("  FileLifecycleTest.exe --case <TestCaseID>");
            Console.WriteLine();
            Console.WriteLine("Supported TestCaseID values:");
            Console.WriteLine("  FILE-CREATE-001");
            Console.WriteLine("  FILE-OPEN-001");
            Console.WriteLine("  FILE-DELETE-001");
            Console.WriteLine("  FILE-MODIFY-001");
            Console.WriteLine("  FILE-RENAME-001");
        }

        private static void PhaseBegin(string id, string telemetry)
        {
            Console.WriteLine();
            Console.WriteLine("----------------------------------------");
            Console.WriteLine("[PHASE-BEGIN] " + id);
            Console.WriteLine("[TELEMETRY] " + telemetry);
            Console.WriteLine("[TIME] " + Timestamp());
        }

        private static void PhaseEnd(string id)
        {
            Console.WriteLine("[PHASE-END] " + id);
            Console.WriteLine("[TIME] " + Timestamp());
            Console.WriteLine("----------------------------------------");
        }

        private static void Fail(string message)
        {
            Console.WriteLine("[RESULT] FAIL");
            Console.WriteLine("[ERROR] " + message);
            Console.WriteLine("[END] " + Timestamp());
        }

        private static string Timestamp()
        {
            return DateTimeOffset.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz");
        }
    }
}
