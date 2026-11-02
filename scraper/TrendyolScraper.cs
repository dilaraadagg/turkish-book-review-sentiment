using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;
using OpenQA.Selenium.Support.UI;
using SeleniumExtras.WaitHelpers;
using System;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;

namespace BookReviewScraper
{
    public class TrendyolScraper
    {
        private readonly string connectionString;
        public TrendyolScraper(string connStr) => connectionString = connStr;

        public async Task RunAsync(IProgress<string> log, CancellationToken token, int threadCount = 1)
        {
            log?.Report("Trendyol → başladı.");

            var chromeOpts = new ChromeOptions();
            chromeOpts.AddArgument("--start-maximized");
            // chromeOpts.AddArgument("--headless=new");

            using IWebDriver driver = new ChromeDriver(chromeOpts);
            using var _quit = token.Register(() => SafeQuit(driver));

            token.ThrowIfCancellationRequested();
            driver.Navigate().GoToUrl("https://www.trendyol.com/");

            var wait = new WebDriverWait(driver, TimeSpan.FromSeconds(12));

            // Çerez onayı
            TryClick(wait, By.XPath("//button[contains(@class,'onetrust-accept-btn-handler') or contains(.,'Kabul')]"));

            // Kategori (gerekirse selectorları güncelle)
            TryHover(driver, wait, By.CssSelector("nav .i-navigation-menu"));
            TryHover(driver, wait, By.XPath("//div[contains(@class,'i-navigation-menu')]//div[contains(text(),'Kitap')]"));
            TryClick(wait, By.XPath("//div[contains(@class,'i-navigation-menu')]//div[contains(text(),'Kitap')]"));

            string originalWindow = driver.CurrentWindowHandle;

            int scrolled = 0;
            int maxScroll = 15;
            int productIndexStart = 2;
            int productCountToOpen = 30;

            while (scrolled < maxScroll && !token.IsCancellationRequested)
            {
                new OpenQA.Selenium.Interactions.Actions(driver).ScrollByAmount(0, 600).Perform();
                await Task.Delay(250, token);
                scrolled++;

                for (int j = productIndexStart; j < productIndexStart + productCountToOpen; j++)
                {
                    if (token.IsCancellationRequested) break;

                    var productSel = By.XPath($"(//div[contains(@class,'p-card')]/a)[{j}]");
                    if (!Exists(driver, productSel)) continue;

                    try
                    {
                        driver.FindElement(productSel).Click();

                        ReadOnlyCollection<string> handles = null;
                        wait.Until(d => (handles = driver.WindowHandles).Count > 1);
                        string newHandle = SwitchToNewTab(driver, originalWindow);

                        string kitapAdi = SafeText(driver, By.CssSelector("h1.pr-new-br span"));
                        if (string.IsNullOrWhiteSpace(kitapAdi))
                            kitapAdi = SafeText(driver, By.CssSelector("h1.pr-new-br"));

                        string urunPuani = SafeText(driver, By.CssSelector("div.rating-line div.value"));
                        if (string.IsNullOrWhiteSpace(urunPuani))
                            urunPuani = SafeText(driver, By.CssSelector("div.pr-rnr-sm"));

                        // Yorumlar
                        TryClick(wait, By.CssSelector("[data-testid='review'], .rvw-cnt-tx"));

                        int loaded = 0;
                        for (int k = 1; k <= 120; k++)
                        {
                            if (token.IsCancellationRequested) break;

                            var reviewSel = By.XPath($"(//div[@data-test-id='review-container']//div[contains(@class,'comment')] | //div[contains(@class,'review-container')]//div[contains(@class,'comment')])[{k}]");
                            if (!Exists(driver, reviewSel))
                            {
                                new OpenQA.Selenium.Interactions.Actions(driver).ScrollByAmount(0, 800).Perform();
                                await Task.Delay(150, token);
                                continue;
                            }

                            string yorum = SafeText(driver, reviewSel);
                            if (string.IsNullOrWhiteSpace(yorum)) continue;

                            double userRating = TryReadStarRating(driver, k);
                            string isbn = ""; // Trendyol çoğu üründe ISBN göstermiyor

                            await InsertReviewAsync(isbn, kitapAdi, userRating, yorum, "Trendyol", log, token);

                            loaded++;
                            if (loaded % 4 == 0)
                            {
                                new OpenQA.Selenium.Interactions.Actions(driver).ScrollByAmount(0, 600).Perform();
                                await Task.Delay(120, token);
                            }
                        }

                        SafeCloseCurrentTab(driver);
                        driver.SwitchTo().Window(originalWindow);
                        await Task.Delay(100, token);
                    }
                    catch (WebDriverTimeoutException)
                    {
                        TrySwitch(driver, originalWindow);
                    }
                    catch (NoSuchElementException)
                    {
                        TrySwitch(driver, originalWindow);
                        continue;
                    }
                    catch (Exception ex)
                    {
                        log?.Report("Hata: " + ex.Message);
                        TrySwitch(driver, originalWindow);
                    }
                }
            }

            log?.Report("Trendyol → tamamlandı.");
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
            cmd.Parameters.AddWithValue("@SourceWebsite", source ?? "Trendyol");

            try { await cmd.ExecuteNonQueryAsync(token); }
            catch (SqlException ex) when (ex.Number == 2627 || ex.Number == 2601)
            { log?.Report("⏩ Mevcut kayıt atlandı (unique)."); }
        }

        // ---------- Helpers ----------
        private static void SafeQuit(IWebDriver d) { try { d.Quit(); } catch { } }
        private static bool Exists(IWebDriver driver, By by) { try { driver.FindElement(by); return true; } catch { return false; } }
        private static void TryClick(WebDriverWait wait, By by) { try { var el = wait.Until(ExpectedConditions.ElementToBeClickable(by)); el.Click(); } catch { } }
        private static void TryHover(IWebDriver driver, WebDriverWait wait, By by)
        { try { var el = wait.Until(ExpectedConditions.ElementIsVisible(by)); new OpenQA.Selenium.Interactions.Actions(driver).MoveToElement(el).Perform(); } catch { } }
        private static string SafeText(IWebDriver driver, By by) { try { return driver.FindElement(by).Text?.Trim() ?? ""; } catch { return ""; } }
        private static string SwitchToNewTab(IWebDriver driver, string originalHandle)
        { foreach (var h in driver.WindowHandles) if (h != originalHandle) { driver.SwitchTo().Window(h); return h; } return originalHandle; }
        private static void SafeCloseCurrentTab(IWebDriver driver) { try { driver.Close(); } catch { } }
        private static void TrySwitch(IWebDriver driver, string originalHandle) { try { driver.SwitchTo().Window(originalHandle); } catch { } }

        private static double TryReadStarRating(IWebDriver driver, int index)
        {
            try
            {
                var el = driver.FindElement(By.XPath($"(//div[contains(@class,'rating-star') or contains(@class,'star-w')])[{index}]"));
                var widthStyle = el.GetAttribute("style"); // width: 80%;
                var m = Regex.Match(widthStyle ?? "", @"(\d+)\s*%");
                if (m.Success && int.TryParse(m.Groups[1].Value, out int pct))
                {
                    if (pct >= 90) return 5;
                    if (pct >= 70) return 4;
                    if (pct >= 50) return 3;
                    if (pct >= 30) return 2;
                    if (pct >= 10) return 1;
                    return 0;
                }
            }
            catch { }

            try
            {
                var container = driver.FindElement(By.XPath($"(//div[contains(@class,'review-container') or @data-test-id='review-container'])[{index}]"));
                var fullStars = container.FindElements(By.CssSelector(".full, .fa-star.filled, [style*='width: 100%']"));
                int n = fullStars?.Count ?? 0;
                if (n >= 1 && n <= 5) return n;
            }
            catch { }

            return 0;
        }
    }
}
