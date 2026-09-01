using System;
using System.Diagnostics;
using Microsoft.Win32;

namespace RegistryRunTest
{
    internal class Program
    {
        private const string RunKeyPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";
        private const string ValueName = "EDRTelemetryRunTestHklm";
        private const string ValueData = @"C:\Windows\System32\notepad.exe";

        private static int Main(string[] args)
        {
            string caseId = null;
            for (int i = 0; i < (args == null ? 0 : args.Length) - 1; i++)
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                    caseId = args[i + 1].ToUpperInvariant();

            if (caseId != "REG-CREATE-002")
            {
                Console.Error.WriteLine("Usage: RegistryRunTest.exe --case REG-CREATE-002");
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;
            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Registry Action=RegSetValue");
            Write("[META] Process=RegistryRunTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(RunKeyPath, true))
                {
                    if (key == null) throw new InvalidOperationException("Run key not found (HKLM).");
                    if (key.GetValue(ValueName) != null) key.DeleteValue(ValueName, false);
                }
                Write("[SETUP] RegistryPath=HKLM\\" + RunKeyPath);
                Write("[SETUP] ValueName=" + ValueName);
                Write("[SETUP] StaleValueRemoved=true");
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                Write("[TARGET] Operation=RegSetValue");
                Write("[TARGET] RegistryPath=HKLM\\" + RunKeyPath);
                Write("[TARGET] ValueName=" + ValueName);
                Write("[TARGET] NewValue=" + ValueData);

                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(RunKeyPath, true))
                {
                    if (key == null) throw new InvalidOperationException("Run key not found (HKLM).");
                    key.SetValue(ValueName, ValueData, RegistryValueKind.String);
                }
                System.Threading.Thread.Sleep(500);

                string verify = null;
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(RunKeyPath, false))
                {
                    if (key != null) verify = key.GetValue(ValueName) as string;
                }
                Write("[VERIFY] ActualValue=" + verify);
                if (verify != ValueData) throw new InvalidOperationException("Registry value verification failed.");

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
                try
                {
                    using (RegistryKey key = Registry.LocalMachine.OpenSubKey(RunKeyPath, true))
                    { if (key != null && key.GetValue(ValueName) != null) key.DeleteValue(ValueName, false); }
                }
                catch { }
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
