using System;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace FileLifecycleTest
{
    internal class Program
    {
        private const string OriginalName = "FileLifecycle_Target.txt";
        private const string RenamedName = "FileLifecycle_Renamed.txt";

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
                Console.WriteLine("[RESULT] FAIL");
                Console.WriteLine("[ERROR] Unsupported TestCaseID: " + caseId);
                PrintUsage();
                return 2;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string originalPath = Path.Combine(baseDir, OriginalName);
            string renamedPath = Path.Combine(baseDir, RenamedName);

            PrintBegin(caseId, originalPath, renamedPath);

            try
            {
                ValidatePrecondition(caseId, originalPath, renamedPath);

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
                }

                Console.WriteLine("[RESULT] PASS");
                Console.WriteLine("[CASE-END] " + caseId);
                Console.WriteLine("[END] " + Timestamp());
                return 0;
            }
            catch (PreconditionException ex)
            {
                Console.WriteLine("[RESULT] PRECONDITION-FAIL");
                Console.WriteLine("[ERROR] " + ex.Message);
                Console.WriteLine("[CASE-END] " + caseId);
                Console.WriteLine("[END] " + Timestamp());
                return 3;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[RESULT] FAIL");
                Console.WriteLine("[ERROR] " + ex.GetType().Name + ": " + ex.Message);
                Console.WriteLine("[CASE-END] " + caseId);
                Console.WriteLine("[END] " + Timestamp());
                return 1;
            }
        }

        private static void RunCreate(string path)
        {
            Console.WriteLine("[ACTION] File Creation");

            byte[] bytes = Encoding.UTF8.GetBytes(
                "EDR_FILE_CREATION_TEST\r\n" +
                "Created=" + Timestamp() + "\r\n");

            using (FileStream stream = new FileStream(
                path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            if (!File.Exists(path))
                throw new IOException("File creation verification failed.");

            Console.WriteLine("[TARGET] " + path);
            Console.WriteLine("[SIZE] " + new FileInfo(path).Length);
        }

        private static void RunOpen(string path)
        {
            Console.WriteLine("[ACTION] File Opened");

            int bytesRead;
            byte[] buffer = new byte[4096];
            using (FileStream stream = new FileStream(
                path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                bytesRead = stream.Read(buffer, 0, buffer.Length);
            }

            Console.WriteLine("[TARGET] " + path);
            Console.WriteLine("[BYTES-READ] " + bytesRead);
        }

        private static void RunDelete(string path)
        {
            Console.WriteLine("[ACTION] File Deletion");
            File.Delete(path);

            if (File.Exists(path))
                throw new IOException("File deletion verification failed.");

            Console.WriteLine("[TARGET] " + path);
        }

        private static void RunModify(string path)
        {
            Console.WriteLine("[ACTION] File Modification");

            long beforeSize = new FileInfo(path).Length;
            byte[] bytes = Encoding.UTF8.GetBytes(
                "EDR_FILE_MODIFICATION_TEST\r\n" +
                "Modified=" + Timestamp() + "\r\n");

            using (FileStream stream = new FileStream(
                path, FileMode.Open, FileAccess.Write, FileShare.Read))
            {
                stream.Seek(0, SeekOrigin.End);
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }

            long afterSize = new FileInfo(path).Length;
            if (afterSize <= beforeSize)
                throw new IOException("File modification verification failed.");

            Console.WriteLine("[TARGET] " + path);
            Console.WriteLine("[SIZE-BEFORE] " + beforeSize);
            Console.WriteLine("[SIZE-AFTER] " + afterSize);
        }

        private static void RunRename(string oldPath, string newPath)
        {
            Console.WriteLine("[ACTION] File Renaming");
            File.Move(oldPath, newPath);

            if (File.Exists(oldPath) || !File.Exists(newPath))
                throw new IOException("File rename verification failed.");

            Console.WriteLine("[TARGET-OLD] " + oldPath);
            Console.WriteLine("[TARGET-NEW] " + newPath);
        }

        private static void ValidatePrecondition(string caseId, string originalPath, string renamedPath)
        {
            if (caseId == "FILE-CREATE-001")
            {
                if (File.Exists(originalPath))
                    throw new PreconditionException("Target must not exist before FILE-CREATE-001: " + originalPath);
                return;
            }

            if (!File.Exists(originalPath))
                throw new PreconditionException("Target must exist before " + caseId + ": " + originalPath);

            if (caseId == "FILE-RENAME-001" && File.Exists(renamedPath))
                throw new PreconditionException("Rename destination must not exist: " + renamedPath);
        }

        private static string ParseCaseId(string[] args)
        {
            if (args == null || args.Length == 0)
                return null;

            if (args.Length == 1 && !args[0].StartsWith("-"))
                return args[0];

            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
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

        private static void PrintBegin(string caseId, string originalPath, string renamedPath)
        {
            Console.WriteLine("========================================");
            Console.WriteLine("EDR TELEMETRY TEST SAMPLE");
            Console.WriteLine("[CASE-BEGIN] " + caseId);
            Console.WriteLine("[MODULE] File Manipulation");
            Console.WriteLine("[PROCESS] FileLifecycleTest.exe");
            Console.WriteLine("[PID] " + Process.GetCurrentProcess().Id);
            Console.WriteLine("[START] " + Timestamp());
            Console.WriteLine("[TARGET] " + originalPath);
            if (caseId == "FILE-RENAME-001")
                Console.WriteLine("[RENAME-TARGET] " + renamedPath);
            Console.WriteLine("========================================");
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("  FileLifecycleTest.exe --case <TestCaseID>");
            Console.WriteLine();
            Console.WriteLine("Supported TestCaseID values:");
            Console.WriteLine("  FILE-CREATE-001");
            Console.WriteLine("  FILE-OPEN-001");
            Console.WriteLine("  FILE-DELETE-001");
            Console.WriteLine("  FILE-MODIFY-001");
            Console.WriteLine("  FILE-RENAME-001");
        }

        private static string Timestamp()
        {
            return DateTimeOffset.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz");
        }

        private sealed class PreconditionException : Exception
        {
            public PreconditionException(string message) : base(message) { }
        }
    }
}
