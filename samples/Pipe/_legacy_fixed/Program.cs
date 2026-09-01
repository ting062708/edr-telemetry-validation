using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;

namespace PipeLifecycleTest
{
    internal static class Program
    {
        private const string PipePrefix = "EDRTelemetryPipeTest_";

        private const uint PIPE_ACCESS_DUPLEX = 0x00000003;
        private const uint PIPE_TYPE_BYTE = 0x00000000;
        private const uint PIPE_READMODE_BYTE = 0x00000000;
        private const uint PIPE_WAIT = 0x00000000;
        private const uint GENERIC_READ = 0x80000000;
        private const uint GENERIC_WRITE = 0x40000000;
        private const uint OPEN_EXISTING = 3;
        private const int ERROR_PIPE_CONNECTED = 535;
        private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr CreateNamedPipe(
            string lpName, uint dwOpenMode, uint dwPipeMode, uint nMaxInstances,
            uint nOutBufferSize, uint nInBufferSize, uint nDefaultTimeOut, IntPtr lpSecurityAttributes);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool ConnectNamedPipe(IntPtr hNamedPipe, IntPtr lpOverlapped);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool DisconnectNamedPipe(IntPtr hNamedPipe);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr CreateFile(
            string lpFileName, uint dwDesiredAccess, uint dwShareMode, IntPtr lpSecurityAttributes,
            uint dwCreationDisposition, uint dwFlagsAndAttributes, IntPtr hTemplateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private sealed class PipeState
        {
            public string PipeName;
            public string PipePath;
            public IntPtr Server = IntPtr.Zero;
            public IntPtr Client = IntPtr.Zero;
        }

        private static int Main(string[] args)
        {
            string caseId;
            if (!TryGetCase(args, out caseId))
            {
                Console.Error.WriteLine("Usage: PipeLifecycleTest.exe --case PIPE-CREATE-001|PIPE-CONNECT-001|PIPE-DISCONNECT-001");
                return 1;
            }

            string action = caseId == "PIPE-CREATE-001" ? "PipeCreate"
                          : caseId == "PIPE-CONNECT-001" ? "PipeConnect"
                          : "PipeDisconnect";

            var ctx = new RunContext(caseId, "Pipe", action, "PipeLifecycleTest.exe");
            var state = new PipeState();
            bool pass = false;
            int exitCode = 1;

            ctx.BeginRun();
            try
            {
                ctx.BeginSetup();

                if (!IsAdministrator())
                {
                    ctx.Setup("Administrator", "False");
                    throw new InvalidOperationException("Administrator privileges are required by the frozen sample contract.");
                }
                ctx.Setup("Administrator", "True");

                state.PipeName = PipePrefix + ctx.RunId.Replace("-", "").Substring(0, 12);
                state.PipePath = @"\\.\pipe\" + state.PipeName;

                // Named pipes do not have a Delete API. Unique names + handle cleanup
                // are the deterministic equivalent of residue cleanup.
                ctx.Setup("CleanupMode", "UniqueNameAndCloseHandles");
                ctx.Setup("PipeName", state.PipeName);

                if (caseId == "PIPE-CONNECT-001" || caseId == "PIPE-DISCONNECT-001")
                {
                    state.Server = CreateServer(state.PipePath);
                    ctx.Setup("PrecreatedServer", "True");
                }

                if (caseId == "PIPE-DISCONNECT-001")
                {
                    ConnectPair(state);
                    ctx.Setup("Preconnected", "True");
                }

                ctx.EndSetup();
                ctx.BeginTarget();

                if (caseId == "PIPE-CREATE-001")
                {
                    state.Server = CreateServer(state.PipePath);
                    ctx.Target("Operation", "PipeCreate");
                }
                else if (caseId == "PIPE-CONNECT-001")
                {
                    ConnectPair(state);
                    ctx.Target("Operation", "PipeConnect");
                }
                else
                {
                    if (!DisconnectNamedPipe(state.Server))
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "DisconnectNamedPipe failed.");
                    ctx.Target("Operation", "PipeDisconnect");
                }

                ctx.Target("PipeName", state.PipeName);
                ctx.Target("TargetName", state.PipePath);

                pass = true;
                exitCode = 0;
            }
            catch (COMException ex)
            {
                ctx.Error(ex);
            }
            catch (FileNotFoundException ex)
            {
                ctx.Error(ex);
            }
            catch (InvalidOperationException ex)
            {
                ctx.Error(ex);
            }
            catch (Exception ex)
            {
                ctx.Error(ex);
            }
            finally
            {
                // Frozen contract: TARGET-END must exist even when TARGET throws.
                try { ctx.EndTarget(); } catch { }

                // Cleanup is deliberately outside the TARGET window.
                SafeClose(ref state.Client);
                if (state.Server != IntPtr.Zero && state.Server != INVALID_HANDLE_VALUE)
                {
                    try { DisconnectNamedPipe(state.Server); } catch { }
                }
                SafeClose(ref state.Server);

                ctx.FinalizeProtocol(pass, exitCode, "TargetNotReached");
            }
            return exitCode;
        }

        private static bool TryGetCase(string[] args, out string caseId)
        {
            caseId = null;
            if (args == null || args.Length != 2 || !string.Equals(args[0], "--case", StringComparison.Ordinal))
                return false;

            caseId = args[1];
            return caseId == "PIPE-CREATE-001"
                || caseId == "PIPE-CONNECT-001"
                || caseId == "PIPE-DISCONNECT-001";
        }

        private static IntPtr CreateServer(string pipePath)
        {
            IntPtr h = CreateNamedPipe(
                pipePath,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                1, 4096, 4096, 5000, IntPtr.Zero);

            if (h == INVALID_HANDLE_VALUE)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateNamedPipe failed.");
            return h;
        }

        private static void ConnectPair(PipeState state)
        {
            Exception clientError = null;
            var ready = new ManualResetEvent(false);

            Thread clientThread = new Thread(delegate()
            {
                try
                {
                    ready.Set();
                    IntPtr h = CreateFile(
                        state.PipePath,
                        GENERIC_READ | GENERIC_WRITE,
                        0, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);

                    if (h == INVALID_HANDLE_VALUE)
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "Pipe client CreateFile failed.");
                    state.Client = h;
                }
                catch (Exception ex)
                {
                    clientError = ex;
                }
            });
            clientThread.IsBackground = true;
            clientThread.Start();
            ready.WaitOne(2000);

            bool connected = ConnectNamedPipe(state.Server, IntPtr.Zero);
            if (!connected)
            {
                int error = Marshal.GetLastWin32Error();
                if (error != ERROR_PIPE_CONNECTED)
                    throw new Win32Exception(error, "ConnectNamedPipe failed.");
            }

            if (!clientThread.Join(5000))
                throw new InvalidOperationException("Pipe client connection timed out.");
            if (clientError != null)
                throw new InvalidOperationException("Pipe client failed.", clientError);
        }

        private static void SafeClose(ref IntPtr handle)
        {
            if (handle != IntPtr.Zero && handle != INVALID_HANDLE_VALUE)
            {
                try { CloseHandle(handle); } catch { }
                handle = IntPtr.Zero;
            }
        }

        private static bool IsAdministrator()
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
        }
    }

    internal sealed class RunContext
    {
        private readonly string _runId;
        private readonly string _caseId;
        private readonly string _module;
        private readonly string _action;
        private readonly string _processName;
        private bool _setupBegun;
        private bool _setupEnded;
        private bool _targetBegun;
        private bool _targetEnded;
        private bool _resultPrinted;
        private bool _runEnded;

        public RunContext(string caseId, string module, string action, string processName)
        {
            _runId = Guid.NewGuid().ToString("D");
            _caseId = caseId;
            _module = module;
            _action = action;
            _processName = processName;
        }

        public string RunId { get { return _runId; } }

        private static string Utc()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", CultureInfo.InvariantCulture);
        }

        public void BeginRun()
        {
            Console.WriteLine("[RUN-BEGIN] RunID={0} TimeUTC={1}", _runId, Utc());
            Console.WriteLine("[META] TestCaseID={0} Module={1} Action={2}", _caseId, _module, _action);
            Console.WriteLine("[META] Process={0} PID={1} Hostname={2}",
                _processName, Process.GetCurrentProcess().Id, Environment.MachineName);
        }

        public void BeginSetup()
        {
            if (_setupBegun) return;
            _setupBegun = true;
            Console.WriteLine("[SETUP-BEGIN] TimeUTC={0}", Utc());
        }

        public void Setup(string key, object value)
        {
            Console.WriteLine("[SETUP] {0}={1}", key, value == null ? "" : value.ToString());
        }

        public void EndSetup()
        {
            if (_setupEnded) return;
            if (!_setupBegun) BeginSetup();
            _setupEnded = true;
            Console.WriteLine("[SETUP-END] TimeUTC={0}", Utc());
        }

        public void BeginTarget()
        {
            if (_targetBegun) return;
            EndSetup();
            _targetBegun = true;
            Console.WriteLine("[TARGET-BEGIN] TimeUTC={0}", Utc());
        }

        public void Target(string key, object value)
        {
            Console.WriteLine("[TARGET] {0}={1}", key, value == null ? "" : value.ToString());
        }

        public void EndTarget()
        {
            if (_targetEnded) return;
            if (!_targetBegun) BeginTarget();
            _targetEnded = true;
            Console.WriteLine("[TARGET-END] TimeUTC={0}", Utc());
        }

        public void EnsureTargetWindow(string reason)
        {
            if (!_targetBegun)
            {
                BeginTarget();
                Target("Skipped", "True");
                Target("Reason", reason);
            }
            EndTarget();
        }

        public void Error(Exception ex)
        {
            Console.WriteLine("[ERROR] Type={0} HResult=0x{1:X8} Message={2}",
                ex.GetType().Name, unchecked((uint)ex.HResult),
                (ex.Message ?? "").Replace("\r", " ").Replace("\n", " "));
        }

        public void Result(bool pass, int exitCode)
        {
            if (_resultPrinted) return;
            _resultPrinted = true;
            Console.WriteLine("[RESULT] {0} ExitCode={1}", pass ? "PASS" : "FAIL", exitCode);
        }

        public void EndRun()
        {
            if (_runEnded) return;
            _runEnded = true;
            Console.WriteLine("[RUN-END] RunID={0} TimeUTC={1}", _runId, Utc());
        }

        public void FinalizeProtocol(bool pass, int exitCode, string fallbackReason)
        {
            try { EndSetup(); } catch { }
            try
            {
                if (!_targetEnded)
                    EnsureTargetWindow(fallbackReason);
            }
            catch { }
            try { Result(pass, exitCode); } catch { }
            try { EndRun(); } catch { }
        }
    }

}
