using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Principal;

namespace WmiActivityTest
{
    internal static class Program
    {
        private const string FilterPrefix = "EDRTelemetryWmiFilter_";
        private const string ConsumerPrefix = "EDRTelemetryWmiConsumer_";
        private const string SubscriptionNamespace = @"\\.\root\subscription";

        private sealed class WmiState
        {
            public ManagementScope Scope;
            public string FilterName;
            public string ConsumerName;
            public ManagementPath FilterPath;
            public ManagementPath ConsumerPath;
            public ManagementPath BindingPath;
        }

        private static int Main(string[] args)
        {
            string caseId;
            if (!TryGetCase(args, out caseId))
            {
                Console.Error.WriteLine("Usage: WmiActivityTest.exe --case WMI-FILTER-001|WMI-CONSUMER-001|WMI-CONSUMER-TO-FILTER-001");
                return 1;
            }

            string action = caseId == "WMI-FILTER-001" ? "WmiEventFilter"
                          : caseId == "WMI-CONSUMER-001" ? "WmiEventConsumer"
                          : "WmiEventConsumerToFilter";

            var ctx = new RunContext(caseId, "WMI", action, "WmiActivityTest.exe");
            var state = new WmiState();
            bool pass = false;
            int exitCode = 1;

            ctx.BeginRun();
            try
            {
                ctx.BeginSetup();

                if (!IsAdministrator())
                {
                    ctx.Setup("Administrator", "False");
                    throw new InvalidOperationException("Administrator privileges are required for WMI subscription tests.");
                }
                ctx.Setup("Administrator", "True");

                state.Scope = new ManagementScope(SubscriptionNamespace);
                state.Scope.Connect();

                string suffix = ctx.RunId.Replace("-", "").Substring(0, 12);
                state.FilterName = FilterPrefix + suffix;
                state.ConsumerName = ConsumerPrefix + suffix;

                // Residue cleanup supports --no-restore-snapshot repeated runs.
                DeleteWmiResidue(state.Scope);

                ctx.Setup("Namespace", @"root\subscription");
                ctx.Setup("ResidueCleanup", "True");
                ctx.Setup("FilterName", state.FilterName);
                ctx.Setup("ConsumerName", state.ConsumerName);

                if (caseId == "WMI-CONSUMER-TO-FILTER-001")
                {
                    state.FilterPath = CreateFilter(state.Scope, state.FilterName);
                    state.ConsumerPath = CreateConsumer(state.Scope, state.ConsumerName);
                    ctx.Setup("PrecreatedFilter", "True");
                    ctx.Setup("PrecreatedConsumer", "True");
                }

                ctx.EndSetup();
                ctx.BeginTarget();

                if (caseId == "WMI-FILTER-001")
                {
                    state.FilterPath = CreateFilter(state.Scope, state.FilterName);
                    ctx.Target("Operation", "WmiCreate");
                    ctx.Target("WmiClass", "__EventFilter");
                    ctx.Target("TargetName", state.FilterName);
                }
                else if (caseId == "WMI-CONSUMER-001")
                {
                    state.ConsumerPath = CreateConsumer(state.Scope, state.ConsumerName);
                    ctx.Target("Operation", "WmiCreate");
                    ctx.Target("WmiClass", "CommandLineEventConsumer");
                    ctx.Target("TargetName", state.ConsumerName);
                }
                else
                {
                    state.BindingPath = CreateBinding(state.Scope, state.FilterPath, state.ConsumerPath);
                    ctx.Target("Operation", "WmiCreate");
                    ctx.Target("WmiClass", "__FilterToConsumerBinding");
                    ctx.Target("TargetName", state.FilterName + "->" + state.ConsumerName);
                }

                ctx.Target("Namespace", @"root\subscription");
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
            catch (ManagementException ex)
            {
                ctx.Error(ex);
            }
            catch (Exception ex)
            {
                ctx.Error(ex);
            }
            finally
            {
                try { ctx.EndTarget(); } catch { }

                // Cleanup is outside TARGET to keep the correlation window single-action.
                try
                {
                    if (state.Scope != null && state.Scope.IsConnected)
                    {
                        SafeDelete(state.Scope, state.BindingPath);
                        SafeDelete(state.Scope, state.ConsumerPath);
                        SafeDelete(state.Scope, state.FilterPath);
                    }
                }
                catch { }

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
            return caseId == "WMI-FILTER-001"
                || caseId == "WMI-CONSUMER-001"
                || caseId == "WMI-CONSUMER-TO-FILTER-001";
        }

        private static ManagementPath CreateFilter(ManagementScope scope, string name)
        {
            using (ManagementClass cls = new ManagementClass(scope, new ManagementPath("__EventFilter"), null))
            using (ManagementObject obj = cls.CreateInstance())
            {
                obj["Name"] = name;
                obj["EventNamespace"] = @"root\cimv2";
                obj["QueryLanguage"] = "WQL";
                obj["Query"] = "SELECT * FROM __InstanceCreationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_Process'";
                return obj.Put();
            }
        }

        private static ManagementPath CreateConsumer(ManagementScope scope, string name)
        {
            using (ManagementClass cls = new ManagementClass(scope, new ManagementPath("CommandLineEventConsumer"), null))
            using (ManagementObject obj = cls.CreateInstance())
            {
                obj["Name"] = name;
                // Benign, short-lived command. The subscription object is deleted after TARGET.
                obj["CommandLineTemplate"] = Environment.SystemDirectory + @"\cmd.exe /c exit 0";
                obj["RunInteractively"] = false;
                return obj.Put();
            }
        }

        private static ManagementPath CreateBinding(
            ManagementScope scope,
            ManagementPath filterPath,
            ManagementPath consumerPath)
        {
            if (filterPath == null || consumerPath == null)
                throw new InvalidOperationException("Binding prerequisites are missing.");

            using (ManagementClass cls = new ManagementClass(scope, new ManagementPath("__FilterToConsumerBinding"), null))
            using (ManagementObject obj = cls.CreateInstance())
            {
                obj["Filter"] = filterPath.Path;
                obj["Consumer"] = consumerPath.Path;
                return obj.Put();
            }
        }

        private static void DeleteWmiResidue(ManagementScope scope)
        {
            // Binding first, then consumer/filter to satisfy references.
            using (ManagementObjectSearcher searcher = new ManagementObjectSearcher(
                scope, new ObjectQuery("SELECT * FROM __FilterToConsumerBinding")))
            {
                foreach (ManagementObject obj in searcher.Get())
                {
                    using (obj)
                    {
                        string filter = Convert.ToString(obj["Filter"]);
                        string consumer = Convert.ToString(obj["Consumer"]);
                        if ((filter != null && filter.IndexOf(FilterPrefix, StringComparison.OrdinalIgnoreCase) >= 0)
                            || (consumer != null && consumer.IndexOf(ConsumerPrefix, StringComparison.OrdinalIgnoreCase) >= 0))
                        {
                            SafeDeleteObject(obj);
                        }
                    }
                }
            }

            DeleteNamedClassResidue(scope, "CommandLineEventConsumer", "Name", ConsumerPrefix);
            DeleteNamedClassResidue(scope, "__EventFilter", "Name", FilterPrefix);
        }

        private static void DeleteNamedClassResidue(
            ManagementScope scope, string className, string propertyName, string prefix)
        {
            using (ManagementObjectSearcher searcher = new ManagementObjectSearcher(
                scope, new ObjectQuery("SELECT * FROM " + className)))
            {
                foreach (ManagementObject obj in searcher.Get())
                {
                    using (obj)
                    {
                        string value = Convert.ToString(obj[propertyName]);
                        if (value != null && value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                            SafeDeleteObject(obj);
                    }
                }
            }
        }

        private static void SafeDelete(ManagementScope scope, ManagementPath path)
        {
            if (path == null) return;
            try
            {
                using (ManagementObject obj = new ManagementObject(scope, path, null))
                {
                    obj.Delete();
                }
            }
            catch (COMException ex)
            {
                if (unchecked((uint)ex.HResult) == 0x80070002u) return;
                throw;
            }
            catch (FileNotFoundException)
            {
                return;
            }
            catch (InvalidOperationException)
            {
                return;
            }
            catch (ManagementException ex)
            {
                if (ex.ErrorCode == ManagementStatus.NotFound) return;
                throw;
            }
        }

        private static void SafeDeleteObject(ManagementObject obj)
        {
            try
            {
                obj.Delete();
            }
            catch (COMException ex)
            {
                if (unchecked((uint)ex.HResult) == 0x80070002u) return;
                throw;
            }
            catch (FileNotFoundException)
            {
                return;
            }
            catch (InvalidOperationException)
            {
                return;
            }
            catch (ManagementException ex)
            {
                if (ex.ErrorCode == ManagementStatus.NotFound) return;
                throw;
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
