using System;
using System.Diagnostics;
using System.Threading;
using Microsoft.Win32;

namespace RegistryLifecycleTest
{
    internal class Program
    {
        private const string RegistryPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string RegistryPathDisplay = @"HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run";
        private const string ValueName = "EDRTelemetryRunTest";
        private const string CreatedValue = @"C:\Windows\System32\notepad.exe";
        private const string ModifiedValue = @"C:\Windows\System32\calc.exe";
        private const int SetupDelayMs = 5000;

        private static string _runId;
        private static string _action;
        private static int _pid;
        private static string _host;

        private static int Main(string[] args)
        {
            _runId = Guid.NewGuid().ToString("N");
            _pid = Process.GetCurrentProcess().Id;
            _host = Environment.MachineName;

            if (args.Length != 1)
            {
                PrintUsage();
                return 2;
            }

            _action = args[0].Trim().ToLowerInvariant();

            if (_action != "create" &&
                _action != "modify" &&
                _action != "delete" &&
                _action != "cleanup")
            {
                PrintUsage();
                return 2;
            }

            PrintRunBegin();

            try
            {
                int result;

                switch (_action)
                {
                    case "create":
                        result = RunCreate();
                        break;
                    case "modify":
                        result = RunModify();
                        break;
                    case "delete":
                        result = RunDelete();
                        break;
                    case "cleanup":
                        result = RunCleanup();
                        break;
                    default:
                        result = 2;
                        break;
                }

                Console.WriteLine("[RUN-END] TimeUTC=" + UtcNow());
                return result;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[RESULT] FAIL ExitCode=1");
                Console.WriteLine("[ERROR] " + ex.GetType().Name + ": " + ex.Message);
                Console.WriteLine("[RUN-END] TimeUTC=" + UtcNow());
                return 1;
            }
        }

        private static int RunCreate()
        {
            SetupBegin();
            DeleteTestValueIfPresent();
            SetupEnd();

            Thread.Sleep(SetupDelayMs);

            TargetBegin();
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(RegistryPath))
            {
                if (key == null)
                {
                    return FailInsideTarget("CreateSubKey returned null.");
                }

                key.SetValue(ValueName, CreatedValue, RegistryValueKind.String);
            }
            PrintTarget("Operation", "RegistryCreate");
            PrintTarget("RegistryPath", RegistryPathDisplay);
            PrintTarget("ValueName", ValueName);
            PrintTarget("ValueType", "REG_SZ");
            PrintTarget("NewValue", CreatedValue);
            TargetEnd();

            if (!ValueEquals(CreatedValue))
            {
                return Fail("Create verification failed.");
            }

            return Pass();
        }

        private static int RunModify()
        {
            SetupBegin();
            string existingValue = GetTestValue();
            Console.WriteLine("[SETUP] ExistingValue=" + (existingValue ?? "<missing>"));

            if (!string.Equals(existingValue, CreatedValue, StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("[SETUP] Validation=FAIL");
                SetupEnd();
                return Fail("Modify prerequisite missing or unexpected. Expected existing value: " + CreatedValue);
            }

            Console.WriteLine("[SETUP] Validation=PASS");
            SetupEnd();

            Thread.Sleep(SetupDelayMs);

            TargetBegin();
            SetTestValue(ModifiedValue);
            PrintTarget("Operation", "RegistryModify");
            PrintTarget("RegistryPath", RegistryPathDisplay);
            PrintTarget("ValueName", ValueName);
            PrintTarget("ValueType", "REG_SZ");
            PrintTarget("OldValue", CreatedValue);
            PrintTarget("NewValue", ModifiedValue);
            TargetEnd();

            if (!ValueEquals(ModifiedValue))
            {
                return Fail("Modify verification failed.");
            }

            return Pass();
        }

        private static string GetTestValue()
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RegistryPath, false))
            {
                if (key == null)
                {
                    return null;
                }

                return key.GetValue(ValueName, null) as string;
            }
        }

        private static int RunDelete()
        {
            SetupBegin();
            SetTestValue(ModifiedValue);
            Console.WriteLine("[SETUP] InitialValue=" + ModifiedValue);
            SetupEnd();

            Thread.Sleep(SetupDelayMs);

            TargetBegin();
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
            {
                if (key == null)
                {
                    return FailInsideTarget("Run registry key cannot be opened.");
                }

                key.DeleteValue(ValueName, true);
            }
            PrintTarget("Operation", "RegistryDelete");
            PrintTarget("RegistryPath", RegistryPathDisplay);
            PrintTarget("ValueName", ValueName);
            PrintTarget("OldValue", ModifiedValue);
            TargetEnd();

            if (TestValueExists())
            {
                return Fail("Delete verification failed; value still exists.");
            }

            return Pass();
        }

        private static int RunCleanup()
        {
            SetupBegin();
            Console.WriteLine("[SETUP] No prerequisite required.");
            SetupEnd();

            TargetBegin();
            bool existed = DeleteTestValueIfPresent();
            PrintTarget("Operation", "RegistryCleanup");
            PrintTarget("RegistryPath", RegistryPathDisplay);
            PrintTarget("ValueName", ValueName);
            PrintTarget("ValueExisted", existed ? "true" : "false");
            TargetEnd();

            if (TestValueExists())
            {
                return Fail("Cleanup verification failed; value still exists.");
            }

            return Pass();
        }

        private static void SetTestValue(string value)
        {
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(RegistryPath))
            {
                if (key == null)
                {
                    throw new InvalidOperationException("Cannot open or create Run registry key.");
                }

                key.SetValue(ValueName, value, RegistryValueKind.String);
            }
        }

        private static bool DeleteTestValueIfPresent()
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RegistryPath, true))
            {
                if (key == null)
                {
                    return false;
                }

                if (key.GetValue(ValueName, null) == null)
                {
                    return false;
                }

                key.DeleteValue(ValueName, false);
                return true;
            }
        }

        private static bool TestValueExists()
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RegistryPath, false))
            {
                return key != null && key.GetValue(ValueName, null) != null;
            }
        }

        private static bool ValueEquals(string expected)
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RegistryPath, false))
            {
                if (key == null)
                {
                    return false;
                }

                string actual = key.GetValue(ValueName, null) as string;
                return string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase);
            }
        }

        private static void PrintRunBegin()
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + _runId + " TimeUTC=" + UtcNow());
            Console.WriteLine("[META] TestCaseID=" + TestCaseId());
            Console.WriteLine("[META] Module=Registry");
            Console.WriteLine("[META] Action=" + _action);
            Console.WriteLine("[META] Process=RegistryLifecycleTest.exe");
            Console.WriteLine("[META] PID=" + _pid);
            Console.WriteLine("[META] Hostname=" + _host);
            Console.WriteLine("[META] RegistryPath=" + RegistryPathDisplay);
            Console.WriteLine("[META] ValueName=" + ValueName);
            Console.WriteLine("[META] RunStartUTC=" + UtcNow());
        }

        private static void SetupBegin()
        {
            Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow());
        }

        private static void SetupEnd()
        {
            Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow());
        }

        private static void TargetBegin()
        {
            Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow());
        }

        private static void TargetEnd()
        {
            Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow());
        }

        private static void PrintTarget(string key, string value)
        {
            Console.WriteLine("[TARGET] " + key + "=" + value);
        }

        private static int Pass()
        {
            Console.WriteLine("[RESULT] PASS ExitCode=0");
            return 0;
        }

        private static int Fail(string message)
        {
            Console.WriteLine("[RESULT] FAIL ExitCode=1");
            Console.WriteLine("[ERROR] " + message);
            return 1;
        }

        private static int FailInsideTarget(string message)
        {
            Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow());
            return Fail(message);
        }

        private static string TestCaseId()
        {
            switch (_action)
            {
                case "create": return "REG-CREATE-001";
                case "modify": return "REG-MODIFY-001";
                case "delete": return "REG-DELETE-001";
                case "cleanup": return "REG-CLEANUP-001";
                default: return "REG-UNKNOWN";
            }
        }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static void PrintUsage()
        {
            Console.WriteLine("Usage: RegistryLifecycleTest.exe <create|modify|delete|cleanup>");
        }
    }
}
