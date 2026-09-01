using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;

namespace VirtualDiskMountTest
{
    internal static class Program
    {
        private const string FilePrefix = "EDRTelemetryMountTest_";
        private const uint VIRTUAL_STORAGE_TYPE_DEVICE_VHDX = 3;
        private static readonly Guid VIRTUAL_STORAGE_TYPE_VENDOR_MICROSOFT =
            new Guid("EC984AEC-A0F9-47E9-901F-71415A66345B");

        private const uint VIRTUAL_DISK_ACCESS_ATTACH_RW = 0x00020000;
        private const uint VIRTUAL_DISK_ACCESS_DETACH = 0x00040000;
        private const uint VIRTUAL_DISK_ACCESS_CREATE = 0x00100000;

        private const uint CREATE_VIRTUAL_DISK_FLAG_NONE = 0;
        private const uint OPEN_VIRTUAL_DISK_FLAG_NONE = 0;
        private const uint ATTACH_VIRTUAL_DISK_FLAG_NO_DRIVE_LETTER = 0x00000001;
        private const uint DETACH_VIRTUAL_DISK_FLAG_NONE = 0;

        private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

        [StructLayout(LayoutKind.Sequential)]
        private struct VIRTUAL_STORAGE_TYPE
        {
            public uint DeviceId;
            public Guid VendorId;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct CREATE_VIRTUAL_DISK_PARAMETERS
        {
            public uint Version;
            public Guid UniqueId;
            public ulong MaximumSize;
            public uint BlockSizeInBytes;
            public uint SectorSizeInBytes;
            [MarshalAs(UnmanagedType.LPWStr)]
            public string ParentPath;
            [MarshalAs(UnmanagedType.LPWStr)]
            public string SourcePath;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct OPEN_VIRTUAL_DISK_PARAMETERS
        {
            public uint Version;
            public uint RWDepth;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ATTACH_VIRTUAL_DISK_PARAMETERS
        {
            public uint Version;
            public uint Reserved;
        }

        [DllImport("virtdisk.dll", CharSet = CharSet.Unicode)]
        private static extern uint CreateVirtualDisk(
            ref VIRTUAL_STORAGE_TYPE VirtualStorageType,
            string Path,
            uint VirtualDiskAccessMask,
            IntPtr SecurityDescriptor,
            uint Flags,
            uint ProviderSpecificFlags,
            ref CREATE_VIRTUAL_DISK_PARAMETERS Parameters,
            IntPtr Overlapped,
            out IntPtr Handle);

        [DllImport("virtdisk.dll", CharSet = CharSet.Unicode)]
        private static extern uint OpenVirtualDisk(
            ref VIRTUAL_STORAGE_TYPE VirtualStorageType,
            string Path,
            uint VirtualDiskAccessMask,
            uint Flags,
            ref OPEN_VIRTUAL_DISK_PARAMETERS Parameters,
            out IntPtr Handle);

        [DllImport("virtdisk.dll")]
        private static extern uint AttachVirtualDisk(
            IntPtr VirtualDiskHandle,
            IntPtr SecurityDescriptor,
            uint Flags,
            uint ProviderSpecificFlags,
            ref ATTACH_VIRTUAL_DISK_PARAMETERS Parameters,
            IntPtr Overlapped);

        [DllImport("virtdisk.dll")]
        private static extern uint DetachVirtualDisk(
            IntPtr VirtualDiskHandle,
            uint Flags,
            uint ProviderSpecificFlags);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private sealed class DiskState
        {
            public string Directory;
            public string Path;
            public IntPtr Handle = IntPtr.Zero;
            public bool Attached;
        }

        private static int Main(string[] args)
        {
            string caseId;
            if (!TryGetCase(args, out caseId))
            {
                Console.Error.WriteLine("Usage: VirtualDiskMountTest.exe --case DEVICE-VDISK-MOUNT-001");
                return 1;
            }

            var ctx = new RunContext(caseId, "Device", "VirtualDiskMount", "VirtualDiskMountTest.exe");
            var state = new DiskState();
            bool pass = false;
            int exitCode = 1;

            ctx.BeginRun();
            try
            {
                ctx.BeginSetup();

                if (!IsAdministrator())
                {
                    ctx.Setup("Administrator", "False");
                    throw new InvalidOperationException("Administrator privileges are required for virtual disk attach.");
                }
                ctx.Setup("Administrator", "True");

                state.Directory = Path.Combine(Path.GetTempPath(), "EDRTelemetryVirtualDisk");
                Directory.CreateDirectory(state.Directory);

                // Clean any leftovers from a prior --no-restore-snapshot run.
                CleanupResidue(state.Directory);
                ctx.Setup("ResidueCleanup", "True");

                string suffix = ctx.RunId.Replace("-", "").Substring(0, 12);
                state.Path = Path.Combine(state.Directory, FilePrefix + suffix + ".vhdx");

                CreateVhdx(state.Path, 64UL * 1024UL * 1024UL);
                state.Handle = OpenForAttach(state.Path);

                ctx.Setup("VirtualDiskPath", state.Path);
                ctx.Setup("PrecreatedVhdx", "True");
                ctx.Setup("OpenedForAttach", "True");

                ctx.EndSetup();
                ctx.BeginTarget();

                var attach = new ATTACH_VIRTUAL_DISK_PARAMETERS
                {
                    Version = 1,
                    Reserved = 0
                };

                uint result = AttachVirtualDisk(
                    state.Handle,
                    IntPtr.Zero,
                    ATTACH_VIRTUAL_DISK_FLAG_NO_DRIVE_LETTER,
                    0,
                    ref attach,
                    IntPtr.Zero);

                if (result != 0)
                    throw new Win32Exception((int)result, "AttachVirtualDisk failed.");

                state.Attached = true;

                ctx.Target("Operation", "VirtualDiskMount");
                ctx.Target("VirtualDiskPath", state.Path);
                ctx.Target("TargetName", Path.GetFileName(state.Path));
                ctx.Target("AttachFlag", "NO_DRIVE_LETTER");

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
                try { ctx.EndTarget(); } catch { }

                // Cleanup after TARGET-END so detach/delete do not pollute mount window.
                if (state.Handle != IntPtr.Zero && state.Handle != INVALID_HANDLE_VALUE)
                {
                    if (state.Attached)
                    {
                        try { DetachVirtualDisk(state.Handle, DETACH_VIRTUAL_DISK_FLAG_NONE, 0); } catch { }
                    }
                    try { CloseHandle(state.Handle); } catch { }
                    state.Handle = IntPtr.Zero;
                }

                if (!string.IsNullOrEmpty(state.Path))
                {
                    try { if (File.Exists(state.Path)) File.Delete(state.Path); } catch { }
                }

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
            return caseId == "DEVICE-VDISK-MOUNT-001";
        }

        private static VIRTUAL_STORAGE_TYPE StorageType()
        {
            return new VIRTUAL_STORAGE_TYPE
            {
                DeviceId = VIRTUAL_STORAGE_TYPE_DEVICE_VHDX,
                VendorId = VIRTUAL_STORAGE_TYPE_VENDOR_MICROSOFT
            };
        }

        private static void CreateVhdx(string path, ulong bytes)
        {
            VIRTUAL_STORAGE_TYPE storage = StorageType();
            var parameters = new CREATE_VIRTUAL_DISK_PARAMETERS
            {
                Version = 1,
                UniqueId = Guid.Empty,
                MaximumSize = bytes,
                BlockSizeInBytes = 0,
                SectorSizeInBytes = 512,
                ParentPath = null,
                SourcePath = null
            };

            IntPtr handle;
            uint result = CreateVirtualDisk(
                ref storage, path, VIRTUAL_DISK_ACCESS_CREATE, IntPtr.Zero,
                CREATE_VIRTUAL_DISK_FLAG_NONE, 0, ref parameters, IntPtr.Zero, out handle);

            if (result != 0)
                throw new Win32Exception((int)result, "CreateVirtualDisk failed.");

            if (handle != IntPtr.Zero && handle != INVALID_HANDLE_VALUE)
                CloseHandle(handle);
        }

        private static IntPtr OpenForAttach(string path)
        {
            VIRTUAL_STORAGE_TYPE storage = StorageType();
            var parameters = new OPEN_VIRTUAL_DISK_PARAMETERS
            {
                Version = 1,
                RWDepth = 1
            };

            IntPtr handle;
            uint result = OpenVirtualDisk(
                ref storage,
                path,
                VIRTUAL_DISK_ACCESS_ATTACH_RW | VIRTUAL_DISK_ACCESS_DETACH,
                OPEN_VIRTUAL_DISK_FLAG_NONE,
                ref parameters,
                out handle);

            if (result != 0)
                throw new Win32Exception((int)result, "OpenVirtualDisk failed.");
            return handle;
        }

        private static void CleanupResidue(string directory)
        {
            foreach (string path in Directory.GetFiles(directory, FilePrefix + "*.vhdx"))
            {
                IntPtr handle = IntPtr.Zero;
                try
                {
                    handle = OpenForAttach(path);
                    // Detach is safe to attempt; failure commonly means it was not attached.
                    try { DetachVirtualDisk(handle, DETACH_VIRTUAL_DISK_FLAG_NONE, 0); } catch { }
                }
                catch (COMException ex)
                {
                    if (unchecked((uint)ex.HResult) != 0x80070002u) throw;
                }
                catch (FileNotFoundException)
                {
                }
                catch (InvalidOperationException)
                {
                }
                catch (Win32Exception)
                {
                    // Continue to deletion attempt; a stale file may not be attachable.
                }
                finally
                {
                    if (handle != IntPtr.Zero && handle != INVALID_HANDLE_VALUE)
                    {
                        try { CloseHandle(handle); } catch { }
                    }
                }

                try
                {
                    if (File.Exists(path)) File.Delete(path);
                }
                catch (IOException)
                {
                    // If still attached or locked, leave it and use this run's unique filename.
                }
                catch (UnauthorizedAccessException)
                {
                }
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
