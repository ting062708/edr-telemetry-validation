using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

namespace NetworkActivityTest
{
    internal class Program
    {
        private const string TcpTargetIp = "93.184.216.34";
        private const int TcpTargetPort = 80;

        private const string UdpTargetIp = "8.8.8.8";
        private const int UdpTargetPort = 53;
        private const string UdpQueryName = "example.com";

        private const string UrlTarget = "https://www.baidu.com";
        private const uint INTERNET_OPEN_TYPE_DIRECT = 1;
        private const uint INTERNET_FLAG_RELOAD = 0x80000000;
        private const uint INTERNET_FLAG_NO_CACHE_WRITE = 0x04000000;

        private const ushort DNS_TYPE_A = 0x0001;
        private const uint DNS_QUERY_BYPASS_CACHE = 0x00000008;
        private const string DnsQueryName = "example.com";

        private const string DownloadHost = "proof.ovh.net";
        private const string DownloadResourcePath = "/files/1Mb.dat";
        private const ushort HttpsPort = 443;
        private const uint WINHTTP_ACCESS_TYPE_DEFAULT_PROXY = 0;
        private const uint WINHTTP_FLAG_SECURE = 0x00800000;
        private const string TestDirectory = @"C:\Temp\EDRTest";
        private const string DownloadFileName = "NetworkActivityTest_download.dat";

        [DllImport("wininet.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr InternetOpen(string lpszAgent, uint dwAccessType, string lpszProxy, string lpszProxyBypass, uint dwFlags);

        [DllImport("wininet.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr InternetOpenUrl(IntPtr hInternet, string lpszUrl, string lpszHeaders, uint dwHeadersLength, uint dwFlags, IntPtr dwContext);

        [DllImport("wininet.dll", SetLastError = true)]
        private static extern bool InternetReadFile(IntPtr hFile, byte[] lpBuffer, uint dwNumberOfBytesToRead, out uint lpdwNumberOfBytesRead);

        [DllImport("wininet.dll", SetLastError = true)]
        private static extern bool InternetCloseHandle(IntPtr hInternet);

        private enum DNS_FREE_TYPE
        {
            DnsFreeFlat = 0,
            DnsFreeRecordList = 1,
            DnsFreeParsedMessageFields = 2
        }

        [DllImport("dnsapi.dll", CharSet = CharSet.Unicode, EntryPoint = "DnsQuery_W")]
        private static extern int DnsQuery_W(string pszName, ushort wType, uint options, IntPtr pExtra, out IntPtr ppQueryResults, IntPtr pReserved);

        [DllImport("dnsapi.dll", EntryPoint = "DnsRecordListFree")]
        private static extern void DnsRecordListFree(IntPtr pRecordList, DNS_FREE_TYPE freeType);

        [DllImport("winhttp.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr WinHttpOpen(string pwszUserAgent, uint dwAccessType, string pwszProxyName, string pwszProxyBypass, uint dwFlags);

        [DllImport("winhttp.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr WinHttpConnect(IntPtr hSession, string pswzServerName, ushort nServerPort, uint dwReserved);

        [DllImport("winhttp.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr WinHttpOpenRequest(IntPtr hConnect, string pwszVerb, string pwszObjectName, string pwszVersion, string pwszReferrer, IntPtr ppwszAcceptTypes, uint dwFlags);

        [DllImport("winhttp.dll", SetLastError = true)]
        private static extern bool WinHttpSendRequest(IntPtr hRequest, string pwszHeaders, uint dwHeadersLength, IntPtr lpOptional, uint dwOptionalLength, uint dwTotalLength, UIntPtr dwContext);

        [DllImport("winhttp.dll", SetLastError = true)]
        private static extern bool WinHttpReceiveResponse(IntPtr hRequest, IntPtr lpReserved);

        [DllImport("winhttp.dll", SetLastError = true)]
        private static extern bool WinHttpReadData(IntPtr hRequest, byte[] lpBuffer, uint dwNumberOfBytesToRead, out uint lpdwNumberOfBytesRead);

        [DllImport("winhttp.dll", SetLastError = true)]
        private static extern bool WinHttpCloseHandle(IntPtr hInternet);

        private static int Main(string[] args)
        {
            string caseId = ParseCaseId(args);
            if (caseId == null)
            {
                Console.Error.WriteLine("Usage: NetworkActivityTest.exe --case <TestCaseID>");
                Console.Error.WriteLine("Cases: NET-TCP-001, NET-UDP-001, NET-URL-001, NET-DNS-001, NET-DOWNLOAD-001");
                return 2;
            }

            string action = GetAction(caseId);
            if (action == null)
            {
                Console.Error.WriteLine("Unknown TestCaseID: " + caseId);
                return 2;
            }

            string runId = Guid.NewGuid().ToString("D");
            int exitCode = 1;

            Write("[RUN-BEGIN] RunID=" + runId + " TimeUTC=" + UtcNow());
            Write("[META] TestCaseID=" + caseId + " Module=Network Action=" + action);
            Write("[META] Process=NetworkActivityTest.exe PID=" + Process.GetCurrentProcess().Id + " Hostname=" + Environment.MachineName);

            try
            {
                Write("[SETUP-BEGIN] TimeUTC=" + UtcNow());
                Setup(caseId);
                Write("[SETUP-END] TimeUTC=" + UtcNow());

                Write("[TARGET-BEGIN] TimeUTC=" + UtcNow());
                exitCode = RunTarget(caseId);
                Write("[TARGET-END] TimeUTC=" + UtcNow());
            }
            catch (PreconditionException ex)
            {
                Write("[ERROR] " + Safe(ex.Message));
                exitCode = 3;
            }
            catch (Exception ex)
            {
                Write("[ERROR] " + ex.GetType().Name + ": " + Safe(ex.Message));
                exitCode = 1;
            }
            finally
            {
                Write("[RESULT] " + (exitCode == 0 ? "PASS" : "FAIL") + " ExitCode=" + exitCode);
                Write("[RUN-END] RunID=" + runId + " TimeUTC=" + UtcNow());
            }

            return exitCode;
        }

        private static string ParseCaseId(string[] args)
        {
            if (args == null) return null;
            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "--case", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
                    return args[i + 1].Trim().ToUpperInvariant();
            }
            return null;
        }

        private static string GetAction(string caseId)
        {
            switch (caseId)
            {
                case "NET-TCP-001": return "TCPConnection";
                case "NET-UDP-001": return "UDPConnection";
                case "NET-URL-001": return "URL";
                case "NET-DNS-001": return "DNSQuery";
                case "NET-DOWNLOAD-001": return "FileDownloaded";
                default: return null;
            }
        }

        private static void Setup(string caseId)
        {
            if (caseId == "NET-DOWNLOAD-001")
            {
                Directory.CreateDirectory(TestDirectory);
                string outputPath = Path.Combine(TestDirectory, DownloadFileName);
                if (File.Exists(outputPath)) File.Delete(outputPath);
                Write("[SETUP] OutputPath=" + outputPath);
            }
            else
            {
                Write("[SETUP] Required=None");
            }
        }

        private static int RunTarget(string caseId)
        {
            switch (caseId)
            {
                case "NET-TCP-001": return RunTcp();
                case "NET-UDP-001": return RunUdp();
                case "NET-URL-001": return RunUrl();
                case "NET-DNS-001": return RunDns();
                case "NET-DOWNLOAD-001": return RunDownload();
                default: return 2;
            }
        }

        private static int RunTcp()
        {
            Socket socket = null;
            try
            {
                socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                socket.SendTimeout = 10000;
                socket.ReceiveTimeout = 10000;
                IPEndPoint remote = new IPEndPoint(IPAddress.Parse(TcpTargetIp), TcpTargetPort);

                Write("[TARGET] Protocol=TCP");
                Write("[TARGET] RemoteIP=" + TcpTargetIp);
                Write("[TARGET] RemotePort=" + TcpTargetPort);

                // Synchronous Connect (IOA records TCP connect only on the
                // blocking connect() syscall; async BeginConnect was missed).
                socket.Connect(remote);

                if (!socket.Connected) throw new IOException("TCP socket is not connected.");
                Write("[TARGET] LocalEndpoint=" + socket.LocalEndPoint);
                Write("[TARGET] RemoteEndpoint=" + socket.RemoteEndPoint);

                // Send a minimal HTTP request so the TCP connection carries
                // real traffic (target 93.184.216.34:80 is example.com:80).
                string httpRequest =
                    "GET / HTTP/1.1\r\n" +
                    "Host: example.com\r\n" +
                    "Connection: close\r\n" +
                    "\r\n";
                byte[] requestBytes = Encoding.ASCII.GetBytes(httpRequest);
                int sent = socket.Send(requestBytes);
                Write("[TARGET] BytesSent=" + sent);

                byte[] buffer = new byte[4096];
                int totalReceived = 0;
                while (true)
                {
                    int received;
                    try
                    {
                        received = socket.Receive(buffer);
                    }
                    catch (SocketException)
                    {
                        break; // peer closed the connection
                    }
                    if (received <= 0) break;
                    totalReceived += received;
                    if (totalReceived >= 65536) break; // cap to avoid long reads
                }
                Write("[TARGET] BytesReceived=" + totalReceived);

                return 0;
            }
            finally
            {
                if (socket != null)
                {
                    try { if (socket.Connected) socket.Shutdown(SocketShutdown.Both); } catch { }
                    socket.Close();
                }
            }
        }

        private static int RunUdp()
        {
            Socket socket = null;
            try
            {
                socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
                socket.ReceiveTimeout = 5000;
                socket.SendTimeout = 5000;
                socket.Bind(new IPEndPoint(IPAddress.Any, 0));

                byte[] packet = BuildDnsQuery(UdpQueryName);
                EndPoint remote = new IPEndPoint(IPAddress.Parse(UdpTargetIp), UdpTargetPort);

                Write("[TARGET] Protocol=UDP");
                Write("[TARGET] RemoteIP=" + UdpTargetIp);
                Write("[TARGET] RemotePort=" + UdpTargetPort);
                Write("[TARGET] Payload=DNS-A-Query");
                Write("[TARGET] QueryName=" + UdpQueryName);

                int sent = socket.SendTo(packet, remote);
                byte[] buffer = new byte[4096];
                EndPoint responseFrom = new IPEndPoint(IPAddress.Any, 0);
                int received = socket.ReceiveFrom(buffer, ref responseFrom);

                if (sent <= 0 || received <= 0) throw new IOException("UDP send/receive did not transfer data.");
                Write("[TARGET] LocalEndpoint=" + socket.LocalEndPoint);
                Write("[TARGET] ResponseFrom=" + responseFrom);
                Write("[TARGET] BytesSent=" + sent);
                Write("[TARGET] BytesReceived=" + received);
                return 0;
            }
            finally
            {
                if (socket != null) socket.Close();
            }
        }

        private static int RunUrl()
        {
            IntPtr session = IntPtr.Zero;
            IntPtr request = IntPtr.Zero;
            try
            {
                Write("[TARGET] URL=" + UrlTarget);
                Write("[TARGET] Method=GET");

                session = InternetOpen("EDR-Telemetry-NetworkActivityTest/1.0", INTERNET_OPEN_TYPE_DIRECT, null, null, 0);
                if (session == IntPtr.Zero) throw Win32Failure("InternetOpen");

                uint flags = INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE;
                request = InternetOpenUrl(session, UrlTarget, null, 0, flags, IntPtr.Zero);
                if (request == IntPtr.Zero) throw Win32Failure("InternetOpenUrl");

                byte[] buffer = new byte[4096];
                long totalRead = 0;
                while (true)
                {
                    uint bytesRead;
                    if (!InternetReadFile(request, buffer, (uint)buffer.Length, out bytesRead))
                        throw Win32Failure("InternetReadFile");
                    if (bytesRead == 0) break;
                    totalRead += bytesRead;
                }

                if (totalRead <= 0) throw new IOException("No URL response data received.");
                Write("[TARGET] ResponseBytes=" + totalRead);
                return 0;
            }
            finally
            {
                if (request != IntPtr.Zero) InternetCloseHandle(request);
                if (session != IntPtr.Zero) InternetCloseHandle(session);
            }
        }

        private static int RunDns()
        {
            IntPtr results = IntPtr.Zero;
            try
            {
                Write("[TARGET] QueryName=" + DnsQueryName);
                Write("[TARGET] QueryType=A");
                Write("[TARGET] Options=DNS_QUERY_BYPASS_CACHE");

                int status = DnsQuery_W(DnsQueryName, DNS_TYPE_A, DNS_QUERY_BYPASS_CACHE, IntPtr.Zero, out results, IntPtr.Zero);
                Write("[TARGET] DnsStatus=" + status);
                if (status != 0) throw new IOException("DnsQuery_W failed with status " + status + ".");
                if (results == IntPtr.Zero) throw new IOException("DNS query returned no records.");
                return 0;
            }
            finally
            {
                if (results != IntPtr.Zero) DnsRecordListFree(results, DNS_FREE_TYPE.DnsFreeRecordList);
            }
        }

        private static int RunDownload()
        {
            string outputPath = Path.Combine(TestDirectory, DownloadFileName);
            IntPtr session = IntPtr.Zero;
            IntPtr connection = IntPtr.Zero;
            IntPtr request = IntPtr.Zero;

            try
            {
                if (!Directory.Exists(TestDirectory)) throw new PreconditionException(TestDirectory + " does not exist.");
                if (File.Exists(outputPath)) throw new PreconditionException("Download target already exists: " + outputPath);

                string url = "https://" + DownloadHost + DownloadResourcePath;
                Write("[TARGET] URL=" + url);
                Write("[TARGET] Host=" + DownloadHost);
                Write("[TARGET] RemotePort=" + HttpsPort);
                Write("[TARGET] OutputPath=" + outputPath);

                session = WinHttpOpen("EDR-Telemetry-NetworkActivityTest/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, null, null, 0);
                if (session == IntPtr.Zero) throw Win32Failure("WinHttpOpen");

                connection = WinHttpConnect(session, DownloadHost, HttpsPort, 0);
                if (connection == IntPtr.Zero) throw Win32Failure("WinHttpConnect");

                request = WinHttpOpenRequest(connection, "GET", DownloadResourcePath, null, null, IntPtr.Zero, WINHTTP_FLAG_SECURE);
                if (request == IntPtr.Zero) throw Win32Failure("WinHttpOpenRequest");

                if (!WinHttpSendRequest(request, null, 0, IntPtr.Zero, 0, 0, UIntPtr.Zero))
                    throw Win32Failure("WinHttpSendRequest");
                if (!WinHttpReceiveResponse(request, IntPtr.Zero))
                    throw Win32Failure("WinHttpReceiveResponse");

                long totalBytes = 0;
                byte[] buffer = new byte[8192];
                using (FileStream fs = new FileStream(outputPath, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
                {
                    while (true)
                    {
                        uint bytesRead;
                        if (!WinHttpReadData(request, buffer, (uint)buffer.Length, out bytesRead))
                            throw Win32Failure("WinHttpReadData");
                        if (bytesRead == 0) break;
                        fs.Write(buffer, 0, (int)bytesRead);
                        totalBytes += bytesRead;
                    }
                    fs.Flush(true);
                }

                if (!File.Exists(outputPath)) throw new IOException("Downloaded file does not exist.");
                long fileSize = new FileInfo(outputPath).Length;
                if (totalBytes <= 0 || fileSize != totalBytes) throw new IOException("Download size verification failed.");

                Write("[TARGET] BytesDownloaded=" + totalBytes);
                Write("[TARGET] SHA256=" + GetSha256(outputPath));
                Write("[TARGET] Md5=" + GetMd5(outputPath));
                return 0;
            }
            finally
            {
                if (request != IntPtr.Zero) WinHttpCloseHandle(request);
                if (connection != IntPtr.Zero) WinHttpCloseHandle(connection);
                if (session != IntPtr.Zero) WinHttpCloseHandle(session);
            }
        }

        private static byte[] BuildDnsQuery(string domain)
        {
            List<byte> packet = new List<byte>();
            ushort transactionId = (ushort)new Random().Next(1, ushort.MaxValue);
            packet.Add((byte)(transactionId >> 8));
            packet.Add((byte)(transactionId & 0xFF));
            packet.Add(0x01); packet.Add(0x00);
            packet.Add(0x00); packet.Add(0x01);
            packet.Add(0x00); packet.Add(0x00);
            packet.Add(0x00); packet.Add(0x00);
            packet.Add(0x00); packet.Add(0x00);
            string[] labels = domain.Split('.');
            foreach (string label in labels)
            {
                byte[] bytes = Encoding.ASCII.GetBytes(label);
                packet.Add((byte)bytes.Length);
                packet.AddRange(bytes);
            }
            packet.Add(0x00);
            packet.Add(0x00); packet.Add(0x01);
            packet.Add(0x00); packet.Add(0x01);
            return packet.ToArray();
        }

        private static Exception Win32Failure(string functionName)
        {
            int error = Marshal.GetLastWin32Error();
            return new InvalidOperationException(functionName + " failed. Win32Error=" + error);
        }

        private static string GetSha256(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream fs = File.OpenRead(path))
            {
                byte[] hash = sha.ComputeHash(fs);
                return BitConverter.ToString(hash).Replace("-", "");
            }
        }

        private static string GetMd5(string path)
        {
            using (MD5 md5 = MD5.Create())
            using (FileStream fs = File.OpenRead(path))
            {
                byte[] hash = md5.ComputeHash(fs);
                return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
        }

        private static string UtcNow()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'");
        }

        private static void Write(string line)
        {
            Console.WriteLine(line);
            Console.Out.Flush();
        }

        private static string Safe(string value)
        {
            if (string.IsNullOrEmpty(value)) return "Unknown error";
            return value.Replace("\r", " ").Replace("\n", " ");
        }

        private sealed class PreconditionException : Exception
        {
            public PreconditionException(string message) : base(message) { }
        }
    }
}
