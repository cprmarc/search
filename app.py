# app.py
import streamlit as st
import openai
import urllib.parse
import os

# 🔐 OpenAI API kulcs beállítása (biztonságosabban)
# Használd a Streamlit secrets-et vagy környezeti változót
try:
    # Próbáld meg a secrets-ből
    openai.api_key = st.secrets["OPENAI_API_KEY"]
except:
    # Ha nincs secrets, akkor környezeti változóból
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
# Ellenőrzés, hogy van-e API kulcs
if not openai.api_key:
    st.error("⚠️ Hiányzik az OpenAI API kulcs! Állítsd be a OPENAI_API_KEY környezeti változót vagy a Streamlit secrets-ben.")
    st.stop()

# 📌 OpenAI alapú értelmezés hibakezeléssel
def interpret_input(question: str):
    prompt = f"""A felhasználó ingatlanhirdetést keres. Emeld ki a magyarországi helyszíneket (települések, kerületek), az ingatlan típusát (pl. ház, lakás), és a hozzávetőleges alapterületet (m2).
Válaszolj egyetlen Python szótár formájában az alábbi kulcsokkal: "locations" (lista), "type" (sztring), "size" (szám, m2).
Példa:
Kérdés: "Budapesten és Érden keresek egy legalább 100 négyzetméteres házat"
Válasz: {{ "locations": ["Budapest", "Érd"], "type": "ház", "size": 100 }}
Kérdés: "{question}"
Válasz:"""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Biztonságosabb eval helyett ast.literal_eval használata
        import ast
        result = ast.literal_eval(content)
        return result
    except openai.AuthenticationError:
        st.error("❌ OpenAI API hitelesítési hiba. Ellenőrizd az API kulcsot!")
        return {"locations": [], "type": "", "size": None}
    except openai.RateLimitError:
        st.error("⏳ API limit túllépve. Próbáld újra később!")
        return {"locations": [], "type": "", "size": None}
    except Exception as e:
        st.error(f"❌ Hiba történt: {str(e)}")
        return {"locations": [], "type": "", "size": None}

# 🌐 URL generálás
def build_url(data):
    base_url = "https://zenga.hu/elado/ingatlan/"
    path_parts = []
    
    for loc in data["locations"]:
        path_parts.append(loc.replace(" ", "-").lower())
    
    if data["type"]:
        path_parts.append(data["type"].lower())
    
    if data["size"]:
        path_parts.append(f"{int(data['size'])}m2")
    
    path = "/".join(path_parts)
    full_url = base_url + path
    return full_url, path_parts

# 🖼️ Streamlit UI
st.set_page_config(page_title="Ingatlan Kereső AI", layout="centered")
st.title("Ingatlan kereső AI 🏡")

# API kulcs státusz megjelenítése
if openai.api_key:
    st.success("✅ OpenAI API kapcsolat rendben")
else:
    st.error("❌ OpenAI API kulcs hiányzik")

user_input = st.text_input(
    "Írd ide, milyen ingatlant keresel", 
    placeholder="pl. Budapesten és Érden keresek egy 100 négyzetméteres házat"
)

if user_input and openai.api_key:
    with st.spinner("Értelmezem a keresésed..."):
        parsed = interpret_input(user_input)
        
    if parsed and parsed["locations"]:
        url, visible_parts = build_url(parsed)
        preview = ", ".join(visible_parts)
        
        # Eredmény megjelenítése
        st.success(f"🎯 Találat: {preview}")
        st.markdown(f"🔗 [Keresés indítása]({url})")
        
        # Debug információ (opcionális)
        with st.expander("🔍 Értelmezett adatok"):
            st.json(parsed)
    else:
        st.warning("❓ Nem sikerült értelmezni a keresést. Próbáld meg konkrétabban megfogalmazni!")

# Használati útmutató
with st.expander("📖 Használati útmutató"):
    st.markdown("""
    **Példák helyes használatra:**
    - "Budapesten keresek lakást"
    - "Debrecenben 80 négyzetméteres házat szeretnék"
    - "Budapest 13. kerületben vagy Szentendrén keresek ingatlant"
    - "Minimum 120 m2-es családi ház Szegeden"
    
    **API kulcs beállítása:**
    1. Streamlit Cloud-on: secrets.toml fájlban add meg: `OPENAI_API_KEY = "sk-..."`
    2. Lokálisan: állítsd be a `OPENAI_API_KEY` környezeti változót
    """)
