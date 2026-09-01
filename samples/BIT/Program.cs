using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

namespace BitsJobTest
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
                string bitsadmin = Path.Combine(Environment.SystemDirectory, "bitsadmin.exe");

                // ── SETUP：检查 bitsadmin ─────────────────────────────
                PrintSetupBegin();
                PrintSetup("BitsadminPath", bitsadmin);
                PrintSetup("BitsadminExists", File.Exists(bitsadmin) ? "true" : "false");
                PrintSetupEnd();

                if (!File.Exists(bitsadmin))
                {
                    Console.WriteLine("[ERROR] bitsadmin.exe not found.");
                    exitCode = 1;
                }
                else
                {
                    Thread.Sleep(3000); // 隔离 SETUP / TARGET 窗口

                    string jobName = "EDRTelemetryBitJob_" + RunId.Substring(0, 8);
                    string localFile = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "bits_test.bin");

                    // ── TARGET：创建 BITS 下载作业 ────────────────────
                    PrintTargetBegin();
                    int createRc = RunProcess(bitsadmin,
                        "/create /download \"" + jobName + "\" http://127.0.0.1/bits_test.bin \"" + localFile + "\"");
                    PrintTarget("Operation", "BitsJobCreate");
                    PrintTarget("JobName", jobName);
                    PrintTarget("JobType", "download");
                    PrintTarget("CreateResult", createRc == 0 ? "PASS" : "FAIL");
                    PrintTargetEnd();

                    // cleanup：取消并删除作业（TARGET 窗口外）
                    RunProcess(bitsadmin, "/cancel \"" + jobName + "\"");
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
            Console.WriteLine("[META] TestCaseID=BITS-JOB-001");
            Console.WriteLine("[META] Module=BITS");
            Console.WriteLine("[META] Action=bits_job_create");
            Console.WriteLine("[META] Process=BitsJobTest.exe");
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
