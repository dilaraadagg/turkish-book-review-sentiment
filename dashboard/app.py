from pathlib import Path

CSV_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
CSV_EVAL = CSV_DIR / "eval_metrics.csv"
CSV_CM   = CSV_DIR / "confusion_matrix.csv"

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Book Sentiment Dashboard", page_icon="📚", layout="wide")

# ------------ Theme / CSS ------------
CUSTOM_CSS = """
<style>
.main .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1250px;}
h1, h2, h3 { letter-spacing: .3px; }
.small-muted { color: #8C8C8C; font-size: 0.9rem; }
.kpi {background: linear-gradient(135deg,#0ea5e9, #6366f1);
 color: white; padding: 18px 18px; border-radius: 16px; box-shadow: 0 10px 30px rgba(99,102,241,.25);}
.kpi .label {opacity: .9; font-size: .95rem;}
.kpi .value {font-size: 1.8rem; font-weight: 700; margin-top: 2px}
section[data-testid="stSidebar"] {width: 320px;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------ Data ------------
CSV_PRED = Path(__file__).resolve().parents[1] / "data" / "processed" / "predictions.csv"
st.caption(f"Veri dosyası: `{CSV_PRED}`")

if not CSV_PRED.exists():
    st.error("`predictions.csv` bulunamadı. Önce Admin Recompute veya `python -m src.infer` çalıştır.")
    st.stop()

df = pd.read_csv(CSV_PRED)
if df.empty:
    st.warning("predictions.csv boş görünüyor.")
    st.stop()

df["is_pos"] = (df["DuyguEtiketi"] == "pozitif").astype(int)

agg = (
    df.groupby(["ISBN","KitapAdi"], as_index=False)
      .agg(PozitifOran=("is_pos","mean"), YorumSayisi=("is_pos","size"))
)
agg["PozitifOran"] = (agg["PozitifOran"]*100).round(2)

# ------------ Sidebar filters ------------
st.sidebar.header("🔎 Filtreler")
min_reviews = st.sidebar.slider("Min. yorum sayısı", 0, int(agg["YorumSayisi"].max()), 10, step=5)
search = st.sidebar.text_input("Kitap adı/ISBN ara", "")
topk = st.sidebar.slider("Top N (Sıralama grafiği)", 5, 30, 10)

filt = agg.query("YorumSayisi >= @min_reviews").copy()
if search.strip():
    s = search.lower()
    # arananı en üste taşı
    filt["match"] = filt["KitapAdi"].str.lower().str.contains(s) | filt["ISBN"].astype(str).str.contains(s)
    filt = filt.sort_values(["match","PozitifOran","YorumSayisi"], ascending=[False, False, False]).drop(columns="match")

# ------------ Header & KPIs ------------
st.title("📚 Book Sentiment Dashboard")
st.write("<span class='small-muted'>Türkçe BERT ile duygu analizi • CSV modu</span>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='kpi'><div class='label'>Toplam Yorum</div><div class='value'>{df.shape[0]:,}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='kpi'><div class='label'>Toplam Kitap</div><div class='value'>{agg.shape[0]:,}</div></div>", unsafe_allow_html=True)
with c3:
    avg_pos = (df['is_pos'].mean()*100).round(2)
    st.markdown(f"<div class='kpi'><div class='label'>Genel Pozitif %</div><div class='value'>{avg_pos}%</div></div>", unsafe_allow_html=True)

st.markdown("")

if CSV_EVAL.exists() and CSV_CM.exists():
    st.subheader("🧪 Evaluation (Ratings vs. Model)")
    eval_df = pd.read_csv(CSV_EVAL, index_col=0)
    acc = eval_df.loc["accuracy","precision"] if "accuracy" in eval_df.index else None
    if acc is not None:
        st.metric("Accuracy", f"{acc*100:.2f}%")
    cm_df = pd.read_csv(CSV_CM, index_col=0)
    st.dataframe(cm_df, use_container_width=True)
else:
    st.info("Evaluation dosyaları yok. Admin Recompute çalıştırdıktan sonra görünür.")


# ------------ Charts row ------------
cc1, cc2 = st.columns([1.3, 1])
with cc1:
    st.subheader("🏆 En İyi Kitaplar (Pozitif %)")
    top = filt.sort_values(["PozitifOran","YorumSayisi"], ascending=[False, False]).head(topk)
    if not top.empty:
        fig = px.bar(
            top, x="KitapAdi", y="PozitifOran",
            hover_data=["ISBN","YorumSayisi"],
            labels={"PozitifOran":"Pozitif (%)","KitapAdi":"Kitap"},
        )
        fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
        fig.update_traces(marker_line_width=0, marker_color="#22c55e")  # yeşil: pozitif
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Filtrelere uyan kayıt bulunamadı.")

with cc2:
    st.subheader("📈 Pozitif/Notr/Negatif")
    pie = df["DuyguEtiketi"].value_counts().rename_axis("Etiket").reset_index(name="Adet")
    color_map = {"pozitif":"#22c55e","notr":"#9ca3af","negatif":"#ef4444"}  # yeşil, gri, kırmızı
    fig2 = px.pie(pie, names="Etiket", values="Adet", hole=.45, color="Etiket", color_discrete_map=color_map)
    fig2.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ------------ Table ------------
st.subheader("📋 Kitap Listesi")
st.dataframe(
    filt.sort_values(["PozitifOran","YorumSayisi"], ascending=[False, False]),
    use_container_width=True,
    hide_index=True
)
