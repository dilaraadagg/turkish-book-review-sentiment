import streamlit as st
from pathlib import Path
import subprocess, sys, os

st.set_page_config(page_title="Admin Recompute", layout="centered")
st.title("♻️ Yeniden Hesapla (BERT)")

# Yol bilgileri
project_root = Path(__file__).resolve().parents[2]
nlp_dir = project_root / "nlp"
python_exe = sys.executable

st.write(f"Proje klasörü: `{project_root}`")
st.write(f"NLP klasörü: `{nlp_dir}`")

if not nlp_dir.exists():
    st.error("`nlp` klasörü bulunamadı. Yol hatası.")
    st.stop()

# --- Kullanıcı seçimleri ---
st.subheader("⚙️ Ayarlar")
mode = st.radio("Veri kaynağı", ["csv", "sql"], horizontal=True, index=0)
limit = st.number_input("SQL limit (opsiyonel)", min_value=0, value=0, step=100)

if st.button("🚀 BERT ile yeniden tahmin al"):
    with st.spinner("Çalıştırılıyor..."):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["KMP_WARNINGS"] = "0"
        env["OMP_NUM_THREADS"] = "1"

        # Seçimleri ortam değişkenine gönder
        env["DATA_MODE"] = mode
        if limit and limit > 0:
            env["SQL_LIMIT"] = str(int(limit))

        result = subprocess.run(
            [python_exe, "-m", "src.infer"],
            cwd=str(nlp_dir),
            capture_output=True,
            text=True,
            env=env
        )

    # --- Sonuç mesajları ---
    if result.returncode == 0:
        st.success("✅ Tamamlandı. Overview sayfasını yenileyin.")
        with st.expander("İşlem detayları (göster/gizle)"):
            st.code(result.stdout or "(çıktı yok)")
    else:
        st.error("❌ İşlem başarısız oldu.")
        if result.stderr:
            with st.expander("Hata ayrıntıları"):
                st.code(result.stderr)
        if result.stdout:
            with st.expander("Komut çıktısı"):
                st.code(result.stdout)
