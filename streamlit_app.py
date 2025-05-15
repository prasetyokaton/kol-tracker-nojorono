import streamlit as st
import pandas as pd
import re
import requests
from collections import Counter
from io import BytesIO

# --- CONFIG ---
FILE_ID = "1FKIw9tpwiZs2VlIx4xjwPp0u_8BbxFRYF5uY8Jf_ozg"
SHEET_NAME = "List KOL Nojorono"

# --- DOWNLOAD REF FILE FROM GOOGLE DRIVE ---
@st.cache_data(show_spinner=False, ttl=0)  # always refresh
def load_reference_data(file_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    response = requests.get(url)
    if response.status_code == 200:
        return pd.read_excel(BytesIO(response.content), sheet_name=sheet_name)
    else:
        st.error(f"Gagal mengunduh file referensi. Status: {response.status_code}")
        return None


# --- EXTRACT TIKTOK USERNAMES ---
def extract_tiktok_username_raw(url):
    match = re.search(r"tiktok\.com/@([^/?\s]+)", url)
    return match.group(1).strip() if match else None

def extract_tiktok_username_ref(url):
    url = str(url).strip()

    if "tiktok.com/@":
        # Rule 1: tiktok.com/@user?
        match = re.search(r"tiktok\.com/@([^/?\s]+)\?", url)
        if match:
            return match.group(1).strip()

        # Rule 2: tiktok.com/@user/
        match = re.search(r"tiktok\.com/@([^/?\s]+)/", url)
        if match:
            return match.group(1).strip()

        # Rule 3: tiktok.com/@user (tanpa / atau ?)
        match = re.search(r"tiktok\.com/@([^/?\s]+)$", url)
        if match:
            return match.group(1).strip()

    elif "tiktok.com/":
        # Rule 4: tiktok.com/user/
        match = re.search(r"tiktok\.com/([^@/?\s]+)/", url)
        if match:
            return match.group(1).strip()

        # Rule 5: tiktok.com/user
        match = re.search(r"tiktok\.com/([^@/?\s]+)$", url)
        if match:
            return match.group(1).strip()

        # Rule 6: tiktok.com/user?
        match = re.search(r"tiktok\.com/([^@/?\s]+)\?", url)
        if match:
            return match.group(1).strip()

    # Rule 7: @user (bukan link)
    elif url.startswith("@"):
        return url[1:].strip()

    # Tidak cocok
    return None



# --- UI ---
st.title("🎯 Creator Type Classifier (Google Drive Ref)")

uploaded_file = st.file_uploader("Upload Raw Excel File", type=["xlsx"])

if uploaded_file:
    st.info("🔁 Mengunduh referensi dari Google Drive...")
    ref_df = load_reference_data(FILE_ID, SHEET_NAME)

    if ref_df is None:
        st.stop()

    # ✅ Cek apakah file benar-benar terbaca
    #st.write("📄 Jumlah baris referensi terbaca:", len(ref_df))


    # --- Clean Reference ---
    instagram_refs = ref_df["Author Name Instagram"].dropna().astype(str).apply(lambda x: x.rstrip())
    tiktok_links = ref_df["Link Tiktok"].dropna().astype(str)

    ref_usernames_series = tiktok_links.apply(extract_tiktok_username_ref).dropna()
    #st.write("📋 Semua username referensi:", ref_usernames_series.unique())

    raw_df = pd.read_excel(uploaded_file)
    df = raw_df.copy()

    if 'Author' not in df.columns:
        st.error("❌ Kolom 'Author' tidak ditemukan.")
        st.stop()

    author_idx = df.columns.get_loc("Author")
    df.insert(author_idx, "Creator Type", "")

    instagram_kols = []
    tiktok_kols = []

    for i, row in df.iterrows():
        channel = row.get("Channel", "")
        author = str(row.get("Author", "")).rstrip()
        link = str(row.get("Link URL", "")).strip()
        creator_type = ""

        if channel == "Instagram":
            if author and author.strip():
                if author in instagram_refs.values:
                    creator_type = "KOL"
                    match = ref_df[ref_df["Author Name Instagram"] == author]
                    link_url = match["Link Tiktok"].values[0] if not match.empty else "-"
                    instagram_kols.append((author, link_url))
                else:
                    creator_type = "Organic"
            else:
                continue
        elif channel == "Tiktok":
            raw_username = extract_tiktok_username_raw(link)
            #st.write(f"RAW URL: {link} ➜ Parsed username: {raw_username}")
            ref_usernames = tiktok_links.apply(extract_tiktok_username_ref).dropna().tolist()
            if raw_username and raw_username in ref_usernames_series.values:
                creator_type = "KOL"
                # Buat dataframe baru dari hasil parsing
                ref_usernames_df = pd.DataFrame({
                    "Link Tiktok": tiktok_links,
                    "Parsed Username": tiktok_links.apply(extract_tiktok_username_ref)
                }).dropna()

                # Saat mencocokkan
                match_row = ref_usernames_df[ref_usernames_df["Parsed Username"] == raw_username]
                if not match_row.empty:
                    link_url = match_row["Link Tiktok"].values[0]
                    tiktok_kols.append((author, link_url))


                link_url = match_row["Link Tiktok"].values[0] if not match_row.empty else "-"
                tiktok_kols.append((author, link_url))
            else:
                creator_type = "Organic"
        elif channel in ["Online Media", "Forum", "Blog"]:
            creator_type = ""
        else:
            creator_type = "Organic"

        df.at[i, "Creator Type"] = creator_type

    # --- Summary ---
    kol_count = (df["Creator Type"] == "KOL").sum()
    organic_count = (df["Creator Type"] == "Organic").sum()

    st.success(f"KOL Track: {kol_count} data")
    #st.info(f"Organic: {organic_count} data")

    # --- Instagram Tracking ---
    if instagram_kols:
        st.subheader("📷 Instagram KOL Tracking")
        ig_counter = Counter(instagram_kols)
        ig_df = pd.DataFrame([{"Author": k[0], "Link URL": k[1], "Mention": v} for k, v in ig_counter.items()])
        st.dataframe(ig_df)

    # --- TikTok Tracking ---
    if tiktok_kols:
        st.subheader("🎵 TikTok KOL Tracking")
        tt_counter = Counter(tiktok_kols)
        tt_df = pd.DataFrame([{"Author": k[0], "Link URL": k[1], "Mention": v} for k, v in tt_counter.items()])
        st.dataframe(tt_df)

    # --- Download Output ---
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    st.download_button(
        label="📥 Download Final Excel",
        data=output,
        file_name="classified_creator_type.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("Silakan upload file Excel terlebih dahulu.")
