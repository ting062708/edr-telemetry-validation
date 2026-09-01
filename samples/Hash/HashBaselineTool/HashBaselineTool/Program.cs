using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace HashBaselineTool
{
    internal class Program
    {
        private const string CaseMd5 = "HASH-MD5-001";
        private const string CaseSha = "HASH-SHA-001";
        private const string CaseImpHash = "HASH-IMPHASH-001";

        private static int Main(string[] args)
        {
            string caseId;
            string explicitTarget;
            if (!TryParseArguments(args, out caseId, out explicitTarget))
            {
                Console.Error.WriteLine("Usage: HashBaselineTool.exe --case <HASH-MD5-001|HASH-SHA-001|HASH-IMPHASH-001> [--target <path>]");
                return 2;
            }

            string action;
            switch (caseId)
            {
                case CaseMd5: action = "MD5"; break;
                case CaseSha: action = "SHA"; break;
                case CaseImpHash: action = "IMPHASH"; break;
                default:
                    Console.Error.WriteLine("[ERROR] Unsupported TestCaseID=" + caseId);
                    return 2;
            }

            string targetPath = ResolveTargetPath(explicitTarget);
            string runId = Guid.NewGuid().ToString("D");
            string processName = Process.GetCurrentProcess().ProcessName + ".exe";
            int pid = Process.GetCurrentProcess().Id;
            string hostname = Environment.MachineName;

            WriteRunBegin(runId);
            Console.WriteLine("[META] TestCaseID={0} Module=Hash Action={1}", caseId, action);
            Console.WriteLine("[META] Process={0} PID={1} Hostname={2}", processName, pid, hostname);

            int exitCode = 0;
            bool targetStarted = false;
            try
            {
                WriteSetupBegin();
                Console.WriteLine("[SETUP] TargetPath=" + targetPath);
                if (!File.Exists(targetPath))
                    throw new SetupException("Target file does not exist: " + targetPath);

                FileInfo info = new FileInfo(targetPath);
                Console.WriteLine("[SETUP] TargetSize=" + info.Length);
                WriteSetupEnd();

                WriteTargetBegin();
                targetStarted = true;

                if (caseId == CaseMd5)
                {
                    string md5 = ComputeHash(targetPath, MD5.Create());
                    Console.WriteLine("[TARGET] Algorithm=MD5");
                    Console.WriteLine("[TARGET] TargetPath=" + targetPath);
                    Console.WriteLine("[TARGET] MD5=" + md5);
                }
                else if (caseId == CaseSha)
                {
                    string sha1 = ComputeHash(targetPath, SHA1.Create());
                    string sha256 = ComputeHash(targetPath, SHA256.Create());
                    Console.WriteLine("[TARGET] Algorithm=SHA");
                    Console.WriteLine("[TARGET] TargetPath=" + targetPath);
                    Console.WriteLine("[TARGET] SHA1=" + sha1);
                    Console.WriteLine("[TARGET] SHA256=" + sha256);
                }
                else
                {
                    ImpHashResult result = ComputeImpHash(targetPath);
                    Console.WriteLine("[TARGET] Algorithm=IMPHASH");
                    Console.WriteLine("[TARGET] TargetPath=" + targetPath);
                    Console.WriteLine("[TARGET] IMPHASH=" + result.Hash);
                    Console.WriteLine("[TARGET] ImportCount=" + result.ImportCount);
                }

                WriteTargetEnd();
                targetStarted = false;
                exitCode = 0;
            }
            catch (SetupException ex)
            {
                Console.WriteLine("[ERROR] " + Sanitize(ex.Message));
                exitCode = 3;
            }
            catch (Exception ex)
            {
                Console.WriteLine("[ERROR] {0}: {1}", ex.GetType().Name, Sanitize(ex.Message));
                exitCode = 1;
            }
            finally
            {
                // If a TARGET operation threw, still close the target window so the
                // frozen parser receives a complete, forward time range.
                if (targetStarted)
                    WriteTargetEnd();

                Console.WriteLine("[RESULT] {0} ExitCode={1}", exitCode == 0 ? "PASS" : "FAIL", exitCode);
                Console.WriteLine("[RUN-END] RunID={0} TimeUTC={1}", runId, UtcNow());
            }

            return exitCode;
        }

        private static bool TryParseArguments(string[] args, out string caseId, out string target)
        {
            caseId = null;
            target = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase))
                {
                    if (i + 1 >= args.Length) return false;
                    caseId = args[++i];
                }
                else if (string.Equals(args[i], "--target", StringComparison.OrdinalIgnoreCase))
                {
                    if (i + 1 >= args.Length) return false;
                    target = args[++i];
                }
                else
                {
                    return false;
                }
            }
            return !string.IsNullOrWhiteSpace(caseId);
        }

        private static string ResolveTargetPath(string explicitTarget)
        {
            if (!string.IsNullOrWhiteSpace(explicitTarget))
                return Path.GetFullPath(explicitTarget);

            return Path.GetFullPath(Path.Combine(
                AppDomain.CurrentDomain.BaseDirectory,
                "..", "Support", "TestLibrary.dll"));
        }

        private static void WriteRunBegin(string runId)
        {
            Console.WriteLine("[RUN-BEGIN] RunID={0} TimeUTC={1}", runId, UtcNow());
        }

        private static void WriteSetupBegin() { Console.WriteLine("[SETUP-BEGIN] TimeUTC=" + UtcNow()); }
        private static void WriteSetupEnd() { Console.WriteLine("[SETUP-END] TimeUTC=" + UtcNow()); }
        private static void WriteTargetBegin() { Console.WriteLine("[TARGET-BEGIN] TimeUTC=" + UtcNow()); }
        private static void WriteTargetEnd() { Console.WriteLine("[TARGET-END] TimeUTC=" + UtcNow()); }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static string Sanitize(string text)
        {
            return (text ?? string.Empty).Replace('\r', ' ').Replace('\n', ' ');
        }

        private static string ComputeHash(string path, HashAlgorithm algorithm)
        {
            using (algorithm)
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                byte[] hash = algorithm.ComputeHash(stream);
                return ToHex(hash);
            }
        }

        private static string ToHex(byte[] bytes)
        {
            return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        }

        // Computes an import-table hash from a PE image. Imports are normalized
        // as "module.function" (lower-case, module extension removed), joined
        // with commas, then MD5-hashed. Ordinal-only imports use "ord<N>".
        private static ImpHashResult ComputeImpHash(string path)
        {
            byte[] data = File.ReadAllBytes(path);
            PeImage pe = new PeImage(data);
            List<string> imports = pe.ReadNormalizedImports();
            if (imports.Count == 0)
                throw new InvalidDataException("PE file has no import entries; IMPHASH cannot be produced.");

            string canonical = string.Join(",", imports.ToArray());
            byte[] bytes = Encoding.ASCII.GetBytes(canonical);
            using (MD5 md5 = MD5.Create())
            {
                return new ImpHashResult(ToHex(md5.ComputeHash(bytes)), imports.Count);
            }
        }

        private sealed class SetupException : Exception
        {
            public SetupException(string message) : base(message) { }
        }

        private sealed class ImpHashResult
        {
            public string Hash { get; private set; }
            public int ImportCount { get; private set; }
            public ImpHashResult(string hash, int count) { Hash = hash; ImportCount = count; }
        }

        private sealed class PeImage
        {
            private readonly byte[] _data;
            private readonly List<Section> _sections = new List<Section>();
            private readonly bool _pe32Plus;
            private readonly uint _importRva;

            public PeImage(byte[] data)
            {
                _data = data ?? throw new ArgumentNullException("data");
                if (_data.Length < 0x40 || ReadUInt16(0) != 0x5A4D)
                    throw new InvalidDataException("Target is not a valid PE image (MZ header missing).");

                int peOffset = CheckedOffset(ReadUInt32(0x3C), 24);
                if (ReadUInt32(peOffset) != 0x00004550)
                    throw new InvalidDataException("Target is not a valid PE image (PE signature missing).");

                ushort sectionCount = ReadUInt16(peOffset + 6);
                ushort optionalHeaderSize = ReadUInt16(peOffset + 20);
                int optional = peOffset + 24;
                Ensure(optional, optionalHeaderSize);

                ushort magic = ReadUInt16(optional);
                if (magic == 0x20B) _pe32Plus = true;
                else if (magic == 0x10B) _pe32Plus = false;
                else throw new InvalidDataException("Unsupported PE optional-header format.");

                int dataDirectory = optional + (_pe32Plus ? 112 : 96);
                if (dataDirectory + 16 > optional + optionalHeaderSize)
                    throw new InvalidDataException("PE optional header has no import data directory.");
                _importRva = ReadUInt32(dataDirectory + 8); // directory index 1

                int sectionTable = optional + optionalHeaderSize;
                for (int i = 0; i < sectionCount; i++)
                {
                    int off = sectionTable + (i * 40);
                    Ensure(off, 40);
                    uint virtualSize = ReadUInt32(off + 8);
                    uint virtualAddress = ReadUInt32(off + 12);
                    uint rawSize = ReadUInt32(off + 16);
                    uint rawPointer = ReadUInt32(off + 20);
                    _sections.Add(new Section(virtualAddress, virtualSize, rawPointer, rawSize));
                }
            }

            public List<string> ReadNormalizedImports()
            {
                if (_importRva == 0)
                    return new List<string>();

                var result = new List<string>();
                int descriptor = RvaToOffset(_importRva);
                for (int guard = 0; guard < 4096; guard++, descriptor += 20)
                {
                    Ensure(descriptor, 20);
                    uint originalFirstThunk = ReadUInt32(descriptor);
                    uint nameRva = ReadUInt32(descriptor + 12);
                    uint firstThunk = ReadUInt32(descriptor + 16);
                    if (originalFirstThunk == 0 && nameRva == 0 && firstThunk == 0)
                        break;
                    if (nameRva == 0)
                        throw new InvalidDataException("Malformed PE import descriptor.");

                    string module = NormalizeModule(ReadAsciiZ(RvaToOffset(nameRva)));
                    uint thunkRva = originalFirstThunk != 0 ? originalFirstThunk : firstThunk;
                    int thunk = RvaToOffset(thunkRva);
                    int width = _pe32Plus ? 8 : 4;

                    for (int thunkGuard = 0; thunkGuard < 65536; thunkGuard++, thunk += width)
                    {
                        ulong value = _pe32Plus ? ReadUInt64(thunk) : ReadUInt32(thunk);
                        if (value == 0) break;

                        string function;
                        bool ordinal = _pe32Plus
                            ? (value & 0x8000000000000000UL) != 0
                            : (value & 0x80000000UL) != 0;
                        if (ordinal)
                        {
                            function = "ord" + (value & 0xFFFFUL).ToString();
                        }
                        else
                        {
                            uint hintNameRva = checked((uint)value);
                            int hintName = RvaToOffset(hintNameRva);
                            Ensure(hintName, 2);
                            function = ReadAsciiZ(hintName + 2).ToLowerInvariant();
                        }
                        result.Add(module + "." + function);
                    }
                }
                return result;
            }

            private static string NormalizeModule(string name)
            {
                string lower = (name ?? string.Empty).ToLowerInvariant();
                int dot = lower.LastIndexOf('.');
                if (dot > 0)
                {
                    string ext = lower.Substring(dot);
                    if (ext == ".dll" || ext == ".ocx" || ext == ".sys")
                        lower = lower.Substring(0, dot);
                }
                return lower;
            }

            private int RvaToOffset(uint rva)
            {
                foreach (Section section in _sections)
                {
                    uint span = Math.Max(section.VirtualSize, section.RawSize);
                    if (rva >= section.VirtualAddress && rva < section.VirtualAddress + span)
                    {
                        uint delta = rva - section.VirtualAddress;
                        if (delta >= section.RawSize)
                            throw new InvalidDataException("RVA points outside section raw data.");
                        return CheckedOffset(section.RawPointer + delta, 1);
                    }
                }

                // RVAs in PE headers map directly to file offsets.
                return CheckedOffset(rva, 1);
            }

            private string ReadAsciiZ(int offset)
            {
                Ensure(offset, 1);
                int end = offset;
                while (end < _data.Length && _data[end] != 0) end++;
                if (end >= _data.Length)
                    throw new InvalidDataException("Unterminated string in PE image.");
                return Encoding.ASCII.GetString(_data, offset, end - offset);
            }

            private ushort ReadUInt16(int offset)
            {
                Ensure(offset, 2);
                return BitConverter.ToUInt16(_data, offset);
            }

            private uint ReadUInt32(int offset)
            {
                Ensure(offset, 4);
                return BitConverter.ToUInt32(_data, offset);
            }

            private ulong ReadUInt64(int offset)
            {
                Ensure(offset, 8);
                return BitConverter.ToUInt64(_data, offset);
            }

            private int CheckedOffset(uint offset, int length)
            {
                if (offset > int.MaxValue) throw new InvalidDataException("PE offset is outside supported range.");
                int result = (int)offset;
                Ensure(result, length);
                return result;
            }

            private void Ensure(int offset, int length)
            {
                if (offset < 0 || length < 0 || offset > _data.Length - length)
                    throw new InvalidDataException("PE structure points outside the file.");
            }

            private sealed class Section
            {
                public uint VirtualAddress { get; private set; }
                public uint VirtualSize { get; private set; }
                public uint RawPointer { get; private set; }
                public uint RawSize { get; private set; }
                public Section(uint va, uint vs, uint rp, uint rs)
                {
                    VirtualAddress = va; VirtualSize = vs; RawPointer = rp; RawSize = rs;
                }
            }
        }
    }
}
