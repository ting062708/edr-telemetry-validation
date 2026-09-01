using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

namespace PowerShellScriptBlockTest
{
    internal class Program
    {
        private static readonly string RunId = Guid.NewGuid().ToString("N");
        private static readonly int Pid = Process.GetCurrentProcess().Id;
        private static readonly string Host = Environment.MachineName;

        private static int Main(string[] args)
        {
            PrintRunBegin();
            int exitCode = 0;

            try
            {
                string ps = Path.Combine(Environment.SystemDirectory,
                    @"WindowsPowerShell\v1.0\powershell.exe");

                // ── SETUP：检查 powershell ────────────────────────────
                PrintSetupBegin();
                PrintSetup("PowerShellPath", ps);
                PrintSetup("PowerShellExists", File.Exists(ps) ? "true" : "false");
                PrintSetupEnd();

                if (!File.Exists(ps))
                {
                    Console.WriteLine("[ERROR] powershell.exe not found.");
                    exitCode = 1;
                }
                else
                {
                    Thread.Sleep(3000); // 隔离 SETUP / TARGET 窗口

                    string marker = "EDRTelemetryScriptBlock_" + RunId.Substring(0, 8);
                    // 脚本块内容独特，便于 IOA Script-Block / ScriptScan 匹配
                    string script = "$m='" + marker + "'; Write-Output $m; Start-Sleep -Milliseconds 300";

                    // ── TARGET：执行 PowerShell 脚本块 ────────────────
                    PrintTargetBegin();
                    int rc = RunProcess(ps,
                        "-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"" + script + "\"");
                    PrintTarget("Operation", "ScriptBlock");
                    PrintTarget("ScriptText", script);
                    PrintTarget("ExecResult", rc == 0 ? "PASS" : "FAIL");
                    PrintTargetEnd();
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

        private static int RunProcess(string exe, string args)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = exe,
                    Arguments = args,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                using (Process p = Process.Start(psi))
                {
                    if (p == null) return -1;
                    p.WaitForExit(30000);
                    return p.HasExited ? p.ExitCode : -1;
                }
            }
            catch
            {
                return -1;
            }
        }

        // ── 协议输出 ────────────────────────────────────────────────
        private static void PrintRunBegin()
        {
            Console.WriteLine("[RUN-BEGIN] RunID=" + RunId + " TimeUTC=" + UtcNow());
            Console.WriteLine("[META] TestCaseID=PS-BLOCK-001");
            Console.WriteLine("[META] Module=PowerShell");
            Console.WriteLine("[META] Action=script_block");
            Console.WriteLine("[META] Process=PowerShellScriptBlockTest.exe");
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
