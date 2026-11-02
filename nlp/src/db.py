import os
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, text

# >>> .env'i yükle
from pathlib import Path
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / "config" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)  # config/.env içindeki DB_* değişkenlerini yükle
except Exception:
    pass

def _build_conn_str() -> str:
    driver   = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server   = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_DATABASE", "")
    user     = os.getenv("DB_USER", "").strip()
    pwd      = os.getenv("DB_PASSWORD", "").strip()
    encrypt  = os.getenv("DB_ENCRYPT", "yes")
    trust    = os.getenv("DB_TRUST_SERVER_CERT", "yes")

    # SQL Login verilmişse onu kullan, yoksa Windows Auth
    if user and pwd:
        odbc = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"ENCRYPT={encrypt};TrustServerCertificate={trust};UID={user};PWD={pwd};"
        )
    else:
        odbc = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"ENCRYPT={encrypt};TrustServerCertificate={trust};Trusted_Connection=Yes;"
        )

    # SQLAlchemy URL
    return "mssql+pyodbc:///?odbc_connect=" + _url_encode(odbc)

def _url_encode(s: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(s)

def fetch_reviews_from_sql(limit: Optional[int] = None) -> pd.DataFrame:
    """
    SQL'den yorumları çeker ve kolon isimlerini pipeline'a uygun döndürür.
    Beklenen kolonlar: ISBN, KitapAdi, KullaniciPuani, YorumIcerigi, KaynakSite
    """
    conn_str = _build_conn_str()
    engine = create_engine(conn_str, fast_executemany=True)

    # Tablo/kolon adlarını kendi şemana göre uyarlayabilirsin.
    # Aşağıdaki SELECT, alias vererek pipeline isimlerine eşitliyor.
    top = f"TOP ({int(limit)}) " if limit and int(limit) > 0 else ""
    sql = f"""
    SELECT {top}
        CAST(ISBN AS varchar(32))     AS ISBN,
        CAST(BookTitle AS nvarchar(256)) AS KitapAdi,
        CAST(UserRating AS float)     AS KullaniciPuani,
        CAST(UserReview AS nvarchar(max)) AS YorumIcerigi,
        CAST(SourceWebsite AS nvarchar(64)) AS KaynakSite
    FROM dbo.Reviews
    """

    with engine.begin() as conn:
        df = pd.read_sql(text(sql), conn)

    # Temel temizlik
    if "YorumIcerigi" in df.columns:
        df["YorumIcerigi"] = df["YorumIcerigi"].astype(str)

    return df
