using System;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using Microsoft.Win32;

namespace RegistryLifecycleTest
{
    internal static class Program
    {
        private const string TestCaseCreate = "REG-CREATE-001";
        private const string TestCaseModify = "REG-MODIFY-001";
        private const string TestCaseDelete = "REG-DELETE-001";

        private const string RegistryPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string ValueName = "EDRTelemetryRunTest";
        private const string CreatedValue = @"C:\Windows\System32\notepad.exe";
        private const string ModifiedValue = @"C:\Windows\System32\calc.exe";

        private static int Main(string[] args)
        {
            string runId = Guid.NewGuid().ToString("D");
            string caseId;

            if (!TryGetCaseId(args, out caseId) || !IsKnownCase(caseId))
            {
                BeginRun(runId, caseId ?? "UNKNOWN", "Unknown");
                Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
                Console.WriteLine("[SETUP] Error=Usage: RegistryLifecycleTest.exe --case <REG-CREATE-001|REG-MODIFY-001|REG-DELETE-001>");
                Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                EndRun(runId, false, 2, "Invalid CaseID or arguments.");
                return 2;
            }

            string action = GetAction(caseId);
            BeginRun(runId, caseId, action);

            try
            {
                if (caseId == TestCaseCreate)
                    return RunCreate(runId);
                if (caseId == TestCaseModify)
                    return RunModify(runId);
                if (caseId == TestCaseDelete)
                    return RunDelete(runId);

                EndRun(runId, false, 2, "Unhandled CaseID.");
                return 2;
            }
            catch (Exception ex)
            {
                EndRun(runId, false, 1, ex.GetType().Name + ": " + ex.Message);
                return 1;
            }
        }

        // ── REG-CREATE-001: 写入 notepad.exe ─────────────────────────────
        private static int RunCreate(string runId)
        {
            // SETUP: 确保值不存在（自带清理）
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
            Console.WriteLine("[SETUP] RegistryPath=" + RegistryPath);
            Console.WriteLine("[SETUP] ValueName=" + ValueName);

            if (!TryOpenRunKey(true, out RegistryKey setupKey, out string setupError))
            {
                Console.WriteLine("[SETUP] Validation=FAIL");
                Console.WriteLine("[SETUP] Reason=" + Sanitize(setupError));
                Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());
                EndRun(runId, false, 1, "Setup failed: " + setupError);
                return 1;
            }

            using (setupKey)
            {
                if (ValueExists(setupKey, ValueName))
                {
                    setupKey.DeleteValue(ValueName, false);
                    Console.WriteLine("[SETUP] StaleValueRemoved=true");
                }
                else
                {
                    Console.WriteLine("[SETUP] StaleValueRemoved=false");
                }
            }

            Console.WriteLine("[SETUP] ExpectedValueState=ABSENT");
            Console.WriteLine("[SETUP] Validation=PASS");
            Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());

            // TARGET: RegSetValue notepad.exe
            Thread.Sleep(5000);
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + TimestampUtc());
            using (RegistryKey writeKey = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
            {
                if (writeKey == null)
                    throw new InvalidOperationException("Unable to open HKCU Run key for write access.");
                writeKey.SetValue(ValueName, CreatedValue, RegistryValueKind.String);
            }
            Console.WriteLine("[TARGET] Operation=RegSetValue");
            Console.WriteLine("[TARGET] RegistryPath=" + RegistryPath);
            Console.WriteLine("[TARGET] ValueName=" + ValueName);
            Console.WriteLine("[TARGET] NewValue=" + CreatedValue);
            Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());

            bool verified = VerifyExactValue(CreatedValue, out string verifyMessage);
            Console.WriteLine("[VERIFY] " + Sanitize(verifyMessage));
            Console.WriteLine("[VERIFY] Validation=" + (verified ? "PASS" : "FAIL"));

            EndRun(runId, verified, verified ? 0 : 1, verified ? null : "Verify failed: " + verifyMessage);
            return verified ? 0 : 1;
        }

        // ── REG-MODIFY-001: notepad.exe → calc.exe ──────────────────────
        private static int RunModify(string runId)
        {
            // SETUP: 确保值存在且等于 notepad.exe（自带清理/预置）
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
            Console.WriteLine("[SETUP] RegistryPath=" + RegistryPath);
            Console.WriteLine("[SETUP] ValueName=" + ValueName);

            bool setupValid = VerifyExactValue(CreatedValue, out string setupMessage);
            Console.WriteLine("[SETUP] ExpectedValue=" + CreatedValue);
            Console.WriteLine("[SETUP] " + Sanitize(setupMessage));

            if (!setupValid)
            {
                // 前置值不存在或不对，预置为 notepad.exe
                using (RegistryKey preKey = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
                {
                    if (preKey == null)
                        throw new InvalidOperationException("Unable to open HKCU Run key for write access.");
                    preKey.SetValue(ValueName, CreatedValue, RegistryValueKind.String);
                }
                Console.WriteLine("[SETUP] PreconditionSeeded=true");
                setupValid = VerifyExactValue(CreatedValue, out setupMessage);
                Console.WriteLine("[SETUP] " + Sanitize(setupMessage));
            }
            else
            {
                Console.WriteLine("[SETUP] PreconditionSeeded=false");
            }

            Console.WriteLine("[SETUP] Validation=" + (setupValid ? "PASS" : "FAIL"));
            Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());

            if (!setupValid)
            {
                EndRun(runId, false, 1, "Unable to establish precondition (notepad.exe).");
                return 1;
            }

            // TARGET: RegSetValue calc.exe
            Thread.Sleep(5000);
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + TimestampUtc());
            using (RegistryKey writeKey = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
            {
                if (writeKey == null)
                    throw new InvalidOperationException("Unable to open HKCU Run key for write access.");
                writeKey.SetValue(ValueName, ModifiedValue, RegistryValueKind.String);
            }
            Console.WriteLine("[TARGET] Operation=RegSetValue");
            Console.WriteLine("[TARGET] RegistryPath=" + RegistryPath);
            Console.WriteLine("[TARGET] ValueName=" + ValueName);
            Console.WriteLine("[TARGET] OldValue=" + CreatedValue);
            Console.WriteLine("[TARGET] NewValue=" + ModifiedValue);
            Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());

            bool verified = VerifyExactValue(ModifiedValue, out string verifyMessage);
            Console.WriteLine("[VERIFY] " + Sanitize(verifyMessage));
            Console.WriteLine("[VERIFY] Validation=" + (verified ? "PASS" : "FAIL"));

            EndRun(runId, verified, verified ? 0 : 1, verified ? null : "Verify failed: " + verifyMessage);
            return verified ? 0 : 1;
        }

        // ── REG-DELETE-001: 删除值 ──────────────────────────────────────
        private static int RunDelete(string runId)
        {
            // SETUP: 确保值存在且等于 calc.exe（自带清理/预置）
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + TimestampUtc());
            Console.WriteLine("[SETUP] RegistryPath=" + RegistryPath);
            Console.WriteLine("[SETUP] ValueName=" + ValueName);

            bool setupValid = VerifyExactValue(ModifiedValue, out string setupMessage);
            Console.WriteLine("[SETUP] ExpectedValue=" + ModifiedValue);
            Console.WriteLine("[SETUP] " + Sanitize(setupMessage));

            if (!setupValid)
            {
                using (RegistryKey preKey = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
                {
                    if (preKey == null)
                        throw new InvalidOperationException("Unable to open HKCU Run key for write access.");
                    preKey.SetValue(ValueName, ModifiedValue, RegistryValueKind.String);
                }
                Console.WriteLine("[SETUP] PreconditionSeeded=true");
                setupValid = VerifyExactValue(ModifiedValue, out setupMessage);
                Console.WriteLine("[SETUP] " + Sanitize(setupMessage));
            }
            else
            {
                Console.WriteLine("[SETUP] PreconditionSeeded=false");
            }

            Console.WriteLine("[SETUP] Validation=" + (setupValid ? "PASS" : "FAIL"));
            Console.WriteLine("[SETUP-END] TimeUTC=" + TimestampUtc());

            if (!setupValid)
            {
                EndRun(runId, false, 1, "Unable to establish precondition (calc.exe).");
                return 1;
            }

            // TARGET: RegDeleteValue
            Thread.Sleep(5000);
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + TimestampUtc());
            using (RegistryKey writeKey = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
            {
                if (writeKey == null)
                    throw new InvalidOperationException("Unable to open HKCU Run key for write access.");
                writeKey.DeleteValue(ValueName, true);
            }
            Console.WriteLine("[TARGET] Operation=RegDeleteValue");
            Console.WriteLine("[TARGET] RegistryPath=" + RegistryPath);
            Console.WriteLine("[TARGET] ValueName=" + ValueName);
            Console.WriteLine("[TARGET] OldValue=" + ModifiedValue);
            Console.WriteLine("[TARGET-END] TimeUTC=" + TimestampUtc());

            bool verified = VerifyValueAbsent(out string verifyMessage);
            Console.WriteLine("[VERIFY] " + Sanitize(verifyMessage));
            Console.WriteLine("[VERIFY] Validation=" + (verified ? "PASS" : "FAIL"));

            EndRun(runId, verified, verified ? 0 : 1, verified ? null : "Verify failed: " + verifyMessage);
            return verified ? 0 : 1;
        }

        // ── 参数解析 ─────────────────────────────────────────────────────
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
            return caseId == TestCaseCreate ||
                   caseId == TestCaseModify ||
                   caseId == TestCaseDelete;
        }

        private static string GetAction(string caseId)
        {
            if (caseId == TestCaseCreate) return "Create";
            if (caseId == TestCaseModify) return "Modify";
            if (caseId == TestCaseDelete) return "Delete";
            return "Unknown";
        }

        // ── 验证 ─────────────────────────────────────────────────────────
        private static bool VerifyExactValue(string expected, out string message)
        {
            if (!TryOpenRunKey(false, out RegistryKey key, out string openError))
            {
                message = "ReadError=" + openError;
                return false;
            }

            using (key)
            {
                if (!ValueExists(key, ValueName))
                {
                    message = "ActualValueState=ABSENT";
                    return false;
                }

                RegistryValueKind kind;
                try
                {
                    kind = key.GetValueKind(ValueName);
                }
                catch (Exception ex)
                {
                    message = "GetValueKindError=" + ex.Message;
                    return false;
                }

                object raw = key.GetValue(ValueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                string actual = raw as string;

                message = "ActualKind=" + kind + " ActualValue=" + (actual ?? "<null>");
                return kind == RegistryValueKind.String &&
                       string.Equals(actual, expected, StringComparison.Ordinal);
            }
        }

        private static bool VerifyValueAbsent(out string message)
        {
            if (!TryOpenRunKey(false, out RegistryKey key, out string openError))
            {
                message = "ReadError=" + openError;
                return false;
            }

            using (key)
            {
                bool exists = ValueExists(key, ValueName);
                message = "ActualValueState=" + (exists ? "PRESENT" : "ABSENT");
                return !exists;
            }
        }

        private static bool TryOpenRunKey(bool writable, out RegistryKey key, out string error)
        {
            key = null;
            error = null;

            try
            {
                key = Registry.CurrentUser.OpenSubKey(RegistryPath, writable);
                if (key == null)
                {
                    error = @"HKCU\" + RegistryPath + " is unavailable.";
                    return false;
                }
                return true;
            }
            catch (Exception ex)
            {
                error = ex.GetType().Name + ": " + ex.Message;
                return false;
            }
        }

        private static bool ValueExists(RegistryKey key, string name)
        {
            return key.GetValueNames().Any(v => string.Equals(v, name, StringComparison.OrdinalIgnoreCase));
        }

        // ── stdout 标签 ─────────────────────────────────────────────────
        private static void BeginRun(string runId, string caseId, string action)
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + TimestampUtc());
            Console.WriteLine("[META] TestCaseID=" + caseId + " Module=Registry Action=" + action);
            Console.WriteLine("[META] Process=RegistryLifecycleTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);
        }

        private static void EndRun(string runId, bool pass, int exitCode, string error)
        {
            if (!string.IsNullOrEmpty(error))
                Console.WriteLine("[ERROR] Message=" + Sanitize(error));
            Console.WriteLine("[RESULT] " + (pass ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
            Console.WriteLine("[RUN-END] RunID=" + runId + " TimeUTC=" + TimestampUtc());
        }

        private static string TimestampUtc()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static string Sanitize(string value)
        {
            if (string.IsNullOrEmpty(value))
                return value;
            return value.Replace("\r", " ").Replace("\n", " ");
        }
    }
}
