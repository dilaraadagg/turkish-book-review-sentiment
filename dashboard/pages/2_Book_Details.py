import pandas as pd
import streamlit as st
from pathlib import Path
import plotly.express as px

st.set_page_config(page_title="Book Details", page_icon="🔎", layout="wide")

CSV_PRED = Path(__file__).resolve().parents[2] / "data" / "processed" / "predictions.csv"
df = pd.read_csv(CSV_PRED) if CSV_PRED.exists() else pd.DataFrame()
if df.empty:
    st.error("predictions.csv bulunamadı ya da boş. Önce ana sayfadan yeniden hesaplayın.")
    st.stop()

st.title("🔎 Kitap Detayı")
books = sorted(df["KitapAdi"].unique())
kitap = st.selectbox("Kitap seç", books, index=0)

sub = df[df["KitapAdi"] == kitap].copy()
st.caption(f"ISBN: **{sub['ISBN'].iloc[0]}** • Yorum sayısı: **{len(sub)}**")

# Üst metrikler
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Pozitif %", (sub["DuyguEtiketi"].eq("pozitif").mean()*100).round(2))
with c2:
    st.metric("Negatif %", (sub["DuyguEtiketi"].eq("negatif").mean()*100).round(2))
with c3:
    st.metric("Ortalama Kullanıcı Puanı", round(sub["KullaniciPuani"].astype(float).mean(), 2))

# Yatay bar (daha okunur)
counts = sub["DuyguEtiketi"].value_counts().reindex(["pozitif","notr","negatif"], fill_value=0).reset_index()
counts.columns = ["Etiket","Adet"]
color_map = {"pozitif":"#22c55e","notr":"#9ca3af","negatif":"#ef4444"}
fig = px.bar(counts, y="Etiket", x="Adet", orientation="h", color="Etiket", color_discrete_map=color_map)
fig.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Filtreler
st.subheader("🗂️ Yorumlar")
left, right = st.columns([1,1])
with left:
    etiket = st.multiselect("Etiket filtrele", ["pozitif","notr","negatif"], default=["pozitif","notr","negatif"])
with right:
    conf_min = st.slider("Min. güven (confidence)", 0.0, 1.0, 0.0, step=0.05)

filtered = sub[sub["DuyguEtiketi"].isin(etiket)]
filtered = filtered[filtered["Conf"] >= conf_min]

def color_sentiment(val):
    if val == "pozitif": return "background-color:#eaf6f0"
    if val == "negatif": return "background-color:#fdeaea"
    return "background-color:#f7f7f7"

show = filtered[["KullaniciPuani","DuyguEtiketi","Conf","YorumIcerigi"]].copy()
show["Conf"] = show["Conf"].round(3)

st.dataframe(
    show.style.map(color_sentiment, subset=["DuyguEtiketi"]),
    use_container_width=True, hide_index=True, height=420
)
