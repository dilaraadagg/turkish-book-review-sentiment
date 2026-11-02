import os
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ---- Ayarlar
# Önceden eğitilmiş (fine-tune edilmemiş) Türkçe duygu modeli — Hugging Face
MODEL_NAME = os.getenv("MODEL_NAME", "savasy/bert-base-turkish-sentiment-cased")
MAX_LEN = int(os.getenv("MAX_LEN", "256"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
DATA_MODE = os.getenv("DATA_MODE", "csv").lower()  # csv | sql
SQL_LIMIT = os.getenv("SQL_LIMIT", "").strip()

# CSV yolları
CSV_IN  = Path(__file__).resolve().parents[2] / "data" / "raw" / "sample_reviews.csv"
CSV_OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "predictions.csv"
CSV_EVAL = CSV_OUT.parent / "eval_metrics.csv"
CSV_CM   = CSV_OUT.parent / "confusion_matrix.csv"
CSV_OUT.parent.mkdir(parents=True, exist_ok=True)

def load_reviews() -> pd.DataFrame:
    if DATA_MODE == "sql":
        from . import db
        limit = int(SQL_LIMIT) if SQL_LIMIT.isdigit() else None
        print(f"Kaynak: SQL (limit={limit})")
        df = db.fetch_reviews_from_sql(limit=limit)
    else:
        print("Kaynak: CSV")
        if not CSV_IN.exists():
            raise FileNotFoundError(f"Girdi CSV yok: {CSV_IN}")
        df = pd.read_csv(CSV_IN)

    # Boş yorumları ve scraper'ın yorumsuz kitaplar için yazdığı "Yorum Yok" satırlarını at
    text = df["YorumIcerigi"].fillna("").astype(str).str.strip()
    df = df[(text != "") & (text.str.lower() != "yorum yok")].copy()

    # Güvenlik: metinleri string yap ve kes
    df["YorumIcerigi"] = df["YorumIcerigi"].astype(str).str.slice(0, MAX_LEN * 2)
    # Eksik kolonları kontrol (pipeline minimum alanları)
    needed = ["ISBN","KitapAdi","KullaniciPuani","YorumIcerigi"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Eksik kolon(lar): {missing}")
    return df

def to_tr(lbl: str) -> str:
    lbl = (lbl or "").lower()
    if "pos" in lbl:
        return "pozitif"
    if "neg" in lbl:
        return "negatif"
    return "notr"

def write_evaluation(df: pd.DataFrame) -> None:
    """Kullanıcı puanından türetilen etiketlerle modeli karşılaştırır.

    Model yalnızca pozitif/negatif üretir; bu yüzden metrikler 3 puanlı (nötr)
    yorumlar hariç tutularak hesaplanır. Nötr yorumların dağılımı karışıklık
    matrisinde ayrıca görünür.
    """
    from sklearn.metrics import classification_report

    binary = df[df["TrueLabel"].isin(["pozitif", "negatif"])]
    if binary.empty:
        print("Uyarı: değerlendirme için pozitif/negatif etiketli satır yok.")
        return
    report = classification_report(
        binary["TrueLabel"], binary["DuyguEtiketi"], output_dict=True, zero_division=0
    )
    pd.DataFrame(report).T.to_csv(CSV_EVAL, encoding="utf-8-sig")
    pd.crosstab(df["TrueLabel"], df["DuyguEtiketi"]).to_csv(CSV_CM, encoding="utf-8-sig")
    print(f"Değerlendirme yazıldı: {CSV_EVAL.name}, {CSV_CM.name} | accuracy={report['accuracy']:.4f}")


def predict_batch(texts, tokenizer, model, device):
    enc = tokenizer(
        texts, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits
        probs = torch.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).cpu().numpy()
        conf = probs.max(dim=1).values.cpu().numpy()
    return pred_idx, conf

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)

    print("Yorumlar yükleniyor...")
    df = load_reviews()
    print("Satır sayısı:", len(df))

    print("Model yükleniyor...", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(device)
    id2label = model.config.id2label

    print("Tahmin hesaplanıyor...")
    preds_all, conf_all = [], []
    texts = df["YorumIcerigi"].tolist()
    for i in range(0, len(texts), BATCH_SIZE):
        p, c = predict_batch(texts[i : i + BATCH_SIZE], tokenizer, model, device)
        preds_all.extend(p); conf_all.extend(c)

    df["pred_idx"] = preds_all
    df["model_label"] = [id2label[int(i)] for i in preds_all]
    df["DuyguEtiketi"] = df["model_label"].map(to_tr)
    df["Conf"] = conf_all

    # --- (Opsiyonel) Rating → TrueLabel ve hızlı evaluation (varsa sklearn kurulu)
    try:
        def rating_to_label(r):
            try:
                r = float(r)
            except Exception:
                return "notr"
            if r <= 2: return "negatif"
            if r >= 4: return "pozitif"
            return "notr"
        df["TrueLabel"] = df["KullaniciPuani"].apply(rating_to_label)
        write_evaluation(df)
    except Exception as e:
        print("Uyarı (evaluation geçildi):", e)

    # Kitap bazlı metrik
    grp = (
        df.assign(is_pos=(df["DuyguEtiketi"] == "pozitif").astype(int))
          .groupby(["ISBN", "KitapAdi"], as_index=False)
          .agg(PozitifOran=("is_pos", "mean"), YorumSayisi=("is_pos", "size"))
    )
    grp["PozitifOran"] = grp["PozitifOran"].round(4)

    df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print(f"predictions.csv yazıldı: {CSV_OUT} | Satır: {len(df)}")

    print("\nEn yüksek pozitif oranlı kitaplar:")
    try:
        print(grp.sort_values("PozitifOran", ascending=False).head(5))
    except Exception:
        print(grp.sort_values("PozitifOran", ascending=False).head(5).to_string(index=False))

if __name__ == "__main__":
    # Gürültüyü azalt
    os.environ.setdefault("KMP_WARNINGS", "0")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
