using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;
using OpenQA.Selenium.Support.UI;
using SeleniumExtras.WaitHelpers;
using System;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;

namespace BookReviewScraper
{
    public class KitapSecScraper
    {
        private readonly string connectionString;

        public KitapSecScraper(string connStr) => connectionString = connStr;

        public async Task RunAsync(IProgress<string> log, CancellationToken token, int threadCount = 1)
        {
            log?.Report("KitapSeç → başladı.");

            var chromeOpts = new ChromeOptions();
            chromeOpts.AddArgument("--start-maximized");
            // chromeOpts.AddArgument("--headless=new");

            using IWebDriver driver = new ChromeDriver(chromeOpts);
            using var _quit = token.Register(() => SafeQuit(driver));

            token.ThrowIfCancellationRequested();
            driver.Navigate().GoToUrl("https://www.kitapsec.com/");

            WebDriverWait wait = new WebDriverWait(driver, TimeSpan.FromSeconds(10));

            // Navigasyon (mevcut Xpath’lerin çalıştığını varsayıyoruz; kırılırsa güncellersin)
            driver.FindElement(By.XPath("/html/body/div[4]/div/div/table/tbody/tr/td[3]/ul/li/a")).Click();
            driver.FindElement(By.XPath("//*[@id=\"menuKategoriDiv3\"]/table/tbody/tr/td[1]/table/tbody/tr/td[1]/div/a[1]")).Click();
            driver.FindElement(By.XPath("/html/body/div[5]/div[1]/div/div/div/div[1]/div/div[2]/table/tbody/tr/td[4]/a")).Click();

            bool hasNextPage = true;
            int urunSayisi = 50;

            while (hasNextPage && !token.IsCancellationRequested)
            {
                for (int i = 1; i <= urunSayisi; i += 2)
                {
                    for (int k = 1; k <= 4; k++)
                    {
                        if (token.IsCancellationRequested) break;

                        try
                        {
                            IWebElement urun = driver.FindElement(By.XPath($"/html/body/div[5]/div[1]/div/div/div/div[1]/div/div[5]/table[1]/tbody/tr[{i}]/td[{k}]/div"));
                            urun.Click();

                            string kitapAdi = SafeText(driver, By.XPath("/html/body/div[5]/div[1]/div/div/div/div[1]/div[2]/div[1]/div[3]/h1"));
                            string isbn = SafeText(driver, By.XPath("/html/body/div[5]/div[1]/div/div/div/div[1]/div[2]/div[1]/div[3]/div[4]/div/div[3]"));
                            string yorumlarText = SafeText(driver, By.XPath("/html/body/div[5]/div[1]/div/div/div/div[1]/div[1]/div/table/tbody/tr/td[3]/a"));
                            int yorumSayisi = ParseYorumSayisi(yorumlarText);

                            if (yorumSayisi > 0)
                            {
                                driver.FindElement(By.ClassName("tabYorumlarBtn")).Click();
                                var element = wait.Until(ExpectedConditions.ElementToBeClickable(By.XPath("/html/body/div[5]/div[1]/div/div/div/div[1]/div[2]/div[2]/div[3]/div[1]/table/tbody/tr[1]/td/div/table/tbody/tr/td[2]/a")));
                                element.Click();

                                bool next = true;
                                while (next && !token.IsCancellationRequested)
                                {
                                    for (int j = 3; j <= 22; j++)
                                    {
                                        try
                                        {
                                            var yorumEl = driver.FindElement(By.XPath($"/html/body/div[5]/div[1]/div/div/div/div[1]/table/tbody/tr[{j}]/td/table/tbody/tr[2]/td/div"));
                                            string yorum = TemizleYorum(yorumEl.Text);

                                            string ratingDivXPath = $"/html/body/div[5]/div[1]/div/div/div/div[1]/table/tbody/tr[{j}]/td/table/tbody/tr[1]/td/table/tbody/tr/td[3]/div/div";
                                            var ratingEl = driver.FindElement(By.XPath(ratingDivXPath));
                                            string width = ratingEl.GetAttribute("style");
                                            string ratingStr = GetRatingFromWidth(width);
                                            double userRating = SafeDouble(ratingStr);

                                            await InsertReviewAsync(isbn, kitapAdi, userRating, yorum, "KitapSec", log, token);
                                        }
                                        catch (NoSuchElementException) { break; }
                                    }

                                    try
                                    {
                                        var nextBtn = driver.FindElement(By.LinkText("Sonraki »"));
                                        if (nextBtn.Displayed && nextBtn.Enabled)
                                        {
                                            nextBtn.Click();
                                            wait.Until(ExpectedConditions.StalenessOf(nextBtn));
                                        }
                                        else next = false;
                                    }
                                    catch (NoSuchElementException) { next = false; }
                                }

                                driver.Navigate().Back();
                                driver.Navigate().Back();
                            }
                            else
                            {
                                await InsertReviewAsync(isbn, kitapAdi, 0, "Yorum Yok", "KitapSec", log, token);
                                driver.Navigate().Back();
                            }
                        }
                        catch (NoSuchElementException)
                        {
                            continue;
                        }
                    }
                }

                try
                {
                    var nextPageButton = driver.FindElement(By.LinkText("Sonraki »"));
                    if (nextPageButton.Displayed && nextPageButton.Enabled)
                    {
                        nextPageButton.Click();
                        wait.Until(ExpectedConditions.StalenessOf(nextPageButton));
                    }
                    else hasNextPage = false;
                }
                catch (NoSuchElementException) { hasNextPage = false; }
            }

            log?.Report("KitapSeç → tamamlandı.");
        }

        // ---------- DB ----------
        private async Task InsertReviewAsync(string isbn, string bookTitle, double userRating, string userReview, string source, IProgress<string> log, CancellationToken token)
        {
            const string sql = @"
                INSERT INTO dbo.Reviews (ISBN, BookTitle, UserRating, UserReview, SourceWebsite)
                VALUES (@ISBN, @BookTitle, @UserRating, @UserReview, @SourceWebsite);";

            await using var conn = new SqlConnection(connectionString);
            await conn.OpenAsync(token);

            await using var cmd = new SqlCommand(sql, conn);
            cmd.Parameters.AddWithValue("@ISBN", (object?)isbn ?? "");
            cmd.Parameters.AddWithValue("@BookTitle", (object?)bookTitle ?? "");
            if (userRating <= 0) cmd.Parameters.AddWithValue("@UserRating", DBNull.Value);
            else cmd.Parameters.AddWithValue("@UserRating", userRating);
            cmd.Parameters.AddWithValue("@UserReview", string.IsNullOrWhiteSpace(userReview) ? (object)DBNull.Value : userReview);
            cmd.Parameters.AddWithValue("@SourceWebsite", source ?? "KitapSec");

            try { await cmd.ExecuteNonQueryAsync(token); }
            catch (SqlException ex) when (ex.Number == 2627 || ex.Number == 2601)
            { log?.Report("⏩ Mevcut kayıt atlandı (unique)."); }
        }

        // ---------- Helpers ----------
        private static void SafeQuit(IWebDriver d) { try { d.Quit(); } catch { } }
        private static string SafeText(IWebDriver driver, By by) { try { return driver.FindElement(by).Text?.Trim() ?? ""; } catch { return ""; } }
        private static int ParseYorumSayisi(string text) { var m = Regex.Match(text ?? "", @"\((\d+)\)"); return m.Success && int.TryParse(m.Groups[1].Value, out int n) ? n : 0; }
        private static string TemizleYorum(string y) { if (string.IsNullOrWhiteSpace(y)) return ""; int i = y.IndexOf('/'); if (i >= 0) y = y.Substring(0, i); return y.Trim(); }
        private static double SafeDouble(string s) { if (double.TryParse(s, NumberStyles.Any, CultureInfo.InvariantCulture, out var v)) return v; if (double.TryParse(s, out v)) return v; return 0; }
        private static string GetRatingFromWidth(string style)
        {
            var m = Regex.Match(style ?? "", @"width:\s*(\d+)\s*px", RegexOptions.IgnoreCase);
            if (!m.Success) return "0";
            int width = int.TryParse(m.Groups[1].Value, out var w) ? w : 0;
            if (width >= 100) return "5";
            if (width >= 80) return "4";
            if (width >= 60) return "3";
            if (width >= 40) return "2";
            if (width >= 20) return "1";
            return "0";
        }
    }
}
