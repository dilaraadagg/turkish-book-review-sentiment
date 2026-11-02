import pandas as pd
import streamlit as st
from pathlib import Path
import plotly.express as px

st.set_page_config(page_title="Overview", layout="wide")

CSV_PRED = Path(__file__).resolve().parents[2] / "data" / "processed" / "predictions.csv"
if not CSV_PRED.exists():
    st.error("predictions.csv yok. `python -m src.infer` çalıştır.")
    st.stop()

df = pd.read_csv(CSV_PRED)
df["is_pos"] = (df["DuyguEtiketi"]=="pozitif").astype(int)
agg = df.groupby(["ISBN","KitapAdi"], as_index=False).agg(PozitifOran=("is_pos","mean"), YorumSayisi=("is_pos","size"))
agg["PozitifOran"] = (agg["PozitifOran"]*100).round(2)

st.title("📊 Overview")

colf1, colf2 = st.columns([2,1])
with colf1:
    q = st.text_input("Ara (kitap adı / ISBN):", "")
with colf2:
    min_reviews = st.slider("Min. yorum", 0, int(agg["YorumSayisi"].max()), 10, step=5)

filt = agg.query("YorumSayisi >= @min_reviews").copy()
if q.strip():
    s = q.lower()
    filt["match"] = filt["KitapAdi"].str.lower().str.contains(s) | filt["ISBN"].astype(str).str.contains(s)
    filt = filt.sort_values(["match","PozitifOran","YorumSayisi"], ascending=[False, False, False]).drop(columns="match")

fig = px.bar(
    filt.sort_values(["PozitifOran","YorumSayisi"], ascending=[False, False]).head(20),
    x="KitapAdi", y="PozitifOran",
    labels={"PozitifOran":"Pozitif (%)","KitapAdi":"Kitap"}
)
fig.update_traces(marker_color="#22c55e")
fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig, use_container_width=True)

st.dataframe(filt, use_container_width=True, hide_index=True)
