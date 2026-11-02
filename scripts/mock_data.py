"""Panel ve pipeline'ı denemek için SENTETİK yorum verisi üretir (gerçek veri değildir)."""
import random
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_reviews.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

books = [
    ("9786051111111", "Suç ve Ceza"),
    ("9786052222222", "Kürk Mantolu Madonna"),
    ("9786053333333", "Simyacı"),
    ("9786054444444", "Sefiller"),
    ("9786055555555", "Tutunamayanlar"),
]

pos = [
    "Çok beğendim, dili akıcı ve etkileyici.",
    "Harika bir eser, herkese tavsiye ederim.",
    "Yazarın anlatımı muazzam, tekrar okuyacağım.",
]
neg = [
    "Beklentimi karşılamadı, çok sıkıcıydı.",
    "Kurgu zayıf, zaman kaybı oldu.",
    "Dili ağır ve anlaşılmaz.",
]
neu = [
    "Fena değil, bazı bölümler güzel bazıları sıradan.",
    "Orta karar bir kitap.",
    "Ne çok iyi ne çok kötü."
]

rows = []
rid = 1
for isbn, title in books:
    for _ in range(60):
        bucket = random.choices(["pos","neg","neu"], weights=[0.5,0.3,0.2])[0]
        if bucket=="pos":
            text = random.choice(pos); rating = random.choice([4,5])
        elif bucket=="neg":
            text = random.choice(neg); rating = random.choice([1,2])
        else:
            text = random.choice(neu); rating = 3
        rows.append({
            "Id": rid, "ISBN": isbn, "KitapAdi": title,
            "KullaniciPuani": rating, "YorumIcerigi": text,
            "KaynakSite": random.choice(["Trendyol","KitapSeç"])
        })
        rid += 1

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print("✅ Yazıldı:", OUT, "| Satır:", len(df))
