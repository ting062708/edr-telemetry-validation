using System;
using System.Diagnostics;
using System.Threading;
using Microsoft.Win32;

namespace GroupPolicyModifyTest
{
    internal class Program
    {
        private static readonly string RunId = Guid.NewGuid().ToString("N");
        private static readonly int Pid = Process.GetCurrentProcess().Id;
        private static readonly string Host = Environment.MachineName;

        // 用户策略（HKCU Policies）存储路径，无需管理员权限，
        // 仍在组策略标准位置，触发 IOA 组策略修改（RegSetValue + RegGroupName）检测
        private const string PolicyKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer";
        private const string PolicyValueName = "EDRTelemetryGpoTest";
        private const string PolicyValueData = "1";

        private static int Main(string[] args)
        {
            PrintRunBegin();
            int exitCode = 0;

            try
            {
                // ── SETUP：检查目标键，记录初始值 ─────────────────
                PrintSetupBegin();
                PrintSetup("RegKeyPath", @"HKCU\" + PolicyKey);
                PrintSetup("RegValueName", PolicyValueName);
                int? oldValue = ReadPolicyValue();
                PrintSetup("PreExistingValue", oldValue.HasValue ? oldValue.Value.ToString() : "(none)");
                PrintSetupEnd();

                Thread.Sleep(3000); // 隔离 SETUP / TARGET 窗口

                // ── TARGET：写入组策略值（RegSetValue）──────────
                PrintTargetBegin();
                WritePolicyValue(PolicyValueData);
                PrintTarget("Operation", "RegSetValue");
                PrintTarget("RegKeyPath", @"HKCU\" + PolicyKey);
                PrintTarget("RegValueName", PolicyValueName);
                PrintTarget("RegValueData", PolicyValueData);
                PrintTargetEnd();

                // 校验写入成功
                int? after = ReadPolicyValue();
                if (after == null || after.Value.ToString() != PolicyValueData)
                {
                    Console.WriteLine("[ERROR] Failed to verify registry value after write.");
                    exitCode = 1;
                }
                else
                {
                    RestorePolicyValue(oldValue); // cleanup，在 TARGET 窗口外
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("[ERROR] " + ex.GetType().Name + ": " + ex.Message);
                exitCode = 1;
            }
            finally
            {
                Console.WriteLine("[RESULT] " + (exitCode == 0 ? "PASS ExitCode=0" : "FAIL ExitCode=1"));
                PrintRunEnd();
            }

            return exitCode;
        }

        private static int? ReadPolicyValue()
        {
            using (RegistryKey key = Registry.CurrentUser.OpenSubKey(PolicyKey, false))
            {
                if (key == null) return null;
                object v = key.GetValue(PolicyValueName);
                return v == null ? (int?)null : Convert.ToInt32(v);
            }
        }

        private static void WritePolicyValue(string data)
        {
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(PolicyKey))
            {
                key.SetValue(PolicyValueName, data, RegistryValueKind.DWord);
            }
        }

        private static void RestorePolicyValue(int? oldValue)
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(PolicyKey, true))
                {
                    if (key == null) return;
                    if (oldValue.HasValue)
                        key.SetValue(PolicyValueName, oldValue.Value, RegistryValueKind.DWord);
                    else
                        key.DeleteValue(PolicyValueName, false);
                }
            }
            catch { }
        }

        // ── 协议输出 ────────────────────────────────────────────────
        private static void PrintRunBegin()
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + RunId + " TimeUTC=" + UtcNow());
            Console.WriteLine("[META] TestCaseID=GPO-MODIFY-001");
            Console.WriteLine("[META] Module=GPO");
            Console.WriteLine("[META] Action=gpo_modify");
            Console.WriteLine("[META] Process=GroupPolicyModifyTest.exe");
            Console.WriteLine("[META] PID=" + Pid);
            Console.WriteLine("[META] Hostname=" + Host);
            Console.WriteLine("[META] RunStartUTC=" + UtcNow());
        }

        private static void PrintSetupBegin() { Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow()); }
        private static void PrintSetupEnd() { Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow()); }
        private static void PrintSetup(string k, string v) { Console.WriteLine("[SETUP] " + k + "=" + v); }
        private static void PrintTargetBegin() { Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow()); }
        private static void PrintTargetEnd() { Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow()); }
        private static void PrintTarget(string k, string v) { Console.WriteLine("[TARGET] " + k + "=" + v); }
        private static void PrintRunEnd() { Console.WriteLine("[RUN-END] RunID=" + RunId + " TimeUTC=" + UtcNow()); }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }
    }
}
