using System;
using System.Threading;
using System.Threading.Tasks;

namespace BookReviewScraper
{
    internal static class Program
    {
        // Bağlantı dizesi BOOKSENT_DB_CONN ortam değişkeninden okunur; yoksa yerel SQL Server'a
        // Windows kimliğiyle bağlanılır. Şifre içeren bağlantı dizelerini koda yazmayın.
        private static readonly string ConnStr =
            Environment.GetEnvironmentVariable("BOOKSENT_DB_CONN")
            ?? "Server=127.0.0.1,1433;Database=KitapVeritabani;Encrypt=True;Integrated Security=True;TrustServerCertificate=True;";

        private static void Main(string[] args)
        {
            SetConsoleTitleSafe("Book Scrapers (Trendyol + KitapSec)");
            Console.WriteLine(">> Argümanlar: both | kitapsec | trendyol");
            Console.WriteLine(">> Çıkmak için Ctrl+C\n");

            using var cts = new CancellationTokenSource();
            Console.CancelKeyPress += (s, e) =>
            {
                e.Cancel = true;
                cts.Cancel();
                Console.WriteLine("\n!! İptal istendi. Kapanıyor...");
            };

            var log = new Progress<string>(m => Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {m}"));
            string mode = (args != null && args.Length > 0 ? args[0] : "both").ToLowerInvariant();

            int exit = 0;
            try
            {
                switch (mode)
                {
                    case "kitapsec":
                        RunSafely(() => new KitapSecScraper(ConnStr).RunAsync(log, cts.Token));
                        break;

                    case "trendyol":
                        RunSafely(() => new TrendyolScraper(ConnStr).RunAsync(log, cts.Token));
                        break;

                    case "both":
                    default:
                        RunSafely(() => new KitapSecScraper(ConnStr).RunAsync(log, cts.Token));
                        if (!cts.IsCancellationRequested)
                            RunSafely(() => new TrendyolScraper(ConnStr).RunAsync(log, cts.Token));
                        break;
                }

                Console.WriteLine("\n>> Tamamlandı.");
            }
            catch (OperationCanceledException)
            {
                Console.WriteLine(">> İptal edildi.");
                exit = 1;
            }
            catch (Exception ex)
            {
                Console.WriteLine(">> HATA: " + ex);
                exit = 2;
            }

            // Konsol bağlı değilse ReadKey patlamasın
            PauseSafe();
            Environment.Exit(exit);
        }

        private static void RunSafely(Func<Task> action)
        {
            action().GetAwaiter().GetResult();
        }

        private static void SetConsoleTitleSafe(string title)
        {
            try
            {
                // Çıktı yönlendirilmişse veya konsol yoksa Title set etmek IOException fırlatabilir
                if (!Console.IsOutputRedirected)
                    Console.Title = title;
            }
            catch { /* yoksay */ }
        }

        private static void PauseSafe()
        {
            try
            {
                if (!Console.IsInputRedirected)
                {
                    Console.WriteLine("\nKapatmak için bir tuşa basın...");
                    Console.ReadKey(true);
                }
            }
            catch { /* yoksay */ }
        }
    }
}
