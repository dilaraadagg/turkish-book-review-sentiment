/* Kitap yorumları veritabanı — SQL Server
   Scraper'lar (scraper/) bu tabloya yazar, NLP pipeline'ı (nlp/src/db.py) buradan okur. */

IF DB_ID(N'KitapVeritabani') IS NULL
    CREATE DATABASE KitapVeritabani;
GO
USE KitapVeritabani;
GO

IF OBJECT_ID(N'dbo.Reviews', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Reviews
    (
        Id            INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ISBN          VARCHAR(32)       NOT NULL DEFAULT '',
        BookTitle     NVARCHAR(256)     NOT NULL,
        UserRating    FLOAT             NULL,          -- 1–5 yıldız; puan yoksa NULL
        UserReview    NVARCHAR(MAX)     NULL,
        SourceWebsite NVARCHAR(64)      NOT NULL,      -- 'KitapSec' | 'Trendyol'
        ScrapedAt     DATETIME2         NOT NULL DEFAULT SYSUTCDATETIME(),

        /* Yorum metninin SHA-256 özeti: aynı yorumun tekrar kaydedilmesini engeller */
        ReviewHash AS CONVERT(VARBINARY(32),
                       HASHBYTES('SHA2_256', ISNULL(UserReview, N''))) PERSISTED
    );

    /* Aynı site + aynı kitap + aynı yorum yalnızca bir kez saklanır.
       Scraper'lar bu ihlali (hata 2601/2627) yakalayıp kaydı atlar. */
    CREATE UNIQUE INDEX IX_Reviews_Unique
        ON dbo.Reviews (SourceWebsite, BookTitle, ReviewHash);
END
GO
