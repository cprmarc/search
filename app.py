# app.py
import streamlit as st
import openai
import urllib.parse
import os
import re

# 🔐 OpenAI API kulcs beállítása
try:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
except:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
if not openai.api_key:
    st.error("⚠️ Hiányzik az OpenAI API kulcs! Állítsd be a OPENAI_API_KEY környezeti változót vagy a Streamlit secrets-ben.")
    st.stop()

# 📊 Zenga.hu adatbázis szótárak a CSV-ből
INGATLAN_TIPUSOK = {
    "lakás": ["lakas", "teglalakas", "panellakas", "tarsashazi-lakas", "apartman-garzon", "egyeb-lakas"],
    "ház": ["haz", "csaladi-haz", "ikerhaz", "sorhaz", "kuria", "villa-kastely", "hazresz", "egyeb-haz"],
    "családi ház": ["csaladi-haz"],
    "családiház": ["csaladi-haz"],
    "ikerház": ["ikerhaz"],
    "sorház": ["sorhaz"],
    "villa": ["villa-kastely"],
    "telek": ["telek", "epitesi-telek", "ipari-telek", "udulotelek", "egyeb-telek"],
    "garázs": ["garazs", "egyedi-garazs", "teremgarazs", "udvari-beallo", "egyeb-garazs"]
}

ALLAPOT_TIPUSOK = {
    "új": ["uj-epitesu"],
    "újszerű": ["ujszeru"], 
    "felújított": ["felujitott"],
    "jó állapotú": ["jo-allapotu"],
    "átlagos": ["atlagos"]
}

FUTES_TIPUSOK = {
    "gáz": ["gaz-cirko", "gaz-konvektor", "gaz-hera"],
    "távfűtés": ["tavfutes", "tavfutes-egyedi-meressel"],
    "elektromos": ["elektromos"],
    "központi": ["kozponti-futes", "hazkozponti", "hazkozponti-futes-egyedi-meressel"]
}

# 📌 OpenAI alapú értelmezés (bővített)
def interpret_input(question: str):
    prompt = f"""A felhasználó magyarországi ingatlanhirdetést keres. Elemezd ki a következő információkat:

1. HELYSZÍNEK: Magyar városok, kerületek (pl. Budapest III. kerület, Debrecen, Pécs)
2. INGATLAN TÍPUS: lakás, ház, családi ház, ikerház, sorház, villa, telek, garázs
3. ALAPTERÜLET: négyzetméter (m2)
4. SZOBASZÁM: hány szobás
5. ÁR: forint összeg (millió Ft-ban)
6. ÁLLAPOT: új, újszerű, felújított, jó állapotú, átlagos
7. FŰTÉS: gáz, távfűtés, elektromos, központi

Válaszolj JSON formátumban:
{{
  "locations": ["város1", "város2"],
  "type": "ingatlan típus",
  "size_min": szám vagy null,
  "size_max": szám vagy null,
  "rooms_min": szám vagy null,
  "rooms_max": szám vagy null,
  "price_min": szám millióban vagy null,
  "price_max": szám millióban vagy null,
  "condition": "állapot" vagy null,
  "heating": "fűtés típus" vagy null
}}

Példa:
"Budapesten és Debrecenben keresek egy 80-120 m2-es, 2-3 szobás családi házat maximum 50 millió forintért"
Válasz: {{"locations": ["Budapest", "Debrecen"], "type": "családi ház", "size_min": 80, "size_max": 120, "rooms_min": 2, "rooms_max": 3, "price_min": null, "price_max": 50, "condition": null, "heating": null}}

Kérdés: "{question}"
Válasz:"""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        import ast
        result = ast.literal_eval(content)
        return result
    except Exception as e:
        st.error(f"❌ Hiba az értelmezés során: {str(e)}")
        return None

# 🔗 Zenga.hu URL építő
def build_zenga_url(data):
    if not data or not data.get("locations"):
        return None, []
        
    base_url = "https://www.zenga.hu/"
    url_parts = []
    
    # 1. Helyszínek hozzáadása
    for location in data["locations"]:
        # Budapest kerületek speciális kezelése
        if "budapest" in location.lower():
            if "kerület" in location.lower() or "." in location:
                # Budapest III. kerület -> budapest-iii-kerulet
                clean_loc = location.lower().replace(" ", "-").replace(".", "")
                url_parts.append(clean_loc)
            else:
                url_parts.append("budapest")
        else:
            # Egyéb városok
            clean_loc = location.lower().replace(" ", "-")
            url_parts.append(clean_loc)
    
    # 2. Eladó/kiadó (alapértelmezett: eladó)
    url_parts.append("elado")
    
    # 3. Ingatlan típus
    if data.get("type"):
        ingatlan_tipus = data["type"].lower()
        if ingatlan_tipus in INGATLAN_TIPUSOK:
            url_parts.extend(INGATLAN_TIPUSOK[ingatlan_tipus])
    
    # 4. Állapot
    if data.get("condition"):
        allapot = data["condition"].lower()
        if allapot in ALLAPOT_TIPUSOK:
            url_parts.extend(ALLAPOT_TIPUSOK[allapot])
    
    # 5. Fűtés
    if data.get("heating"):
        futes = data["heating"].lower()
        if futes in FUTES_TIPUSOK:
            url_parts.extend(FUTES_TIPUSOK[futes])
    
    # 6. Ár tartomány
    if data.get("price_min") or data.get("price_max"):
        price_min = data.get("price_min", 1)
        price_max = data.get("price_max", 500)
        # Millió Ft -> Ft konverzió
        price_min_ft = int(price_min * 1000000)
        price_max_ft = int(price_max * 1000000)
        url_parts.append(f"ar-{price_min_ft}-{price_max_ft}")
    
    # 7. Szobaszám
    if data.get("rooms_min") or data.get("rooms_max"):
        rooms_min = data.get("rooms_min", 1)
        rooms_max = data.get("rooms_max", 10)
        url_parts.append(f"szoba-{rooms_min}-{rooms_max}")
    
    # 8. Alapterület
    if data.get("size_min") or data.get("size_max"):
        size_min = data.get("size_min", 20)
        size_max = data.get("size_max", 500)
        url_parts.append(f"alapterulet-{size_min}-{size_max}")
    
    # URL összeállítása
    full_url = base_url + "+".join(url_parts)
    
    return full_url, url_parts

# 🖼️ Streamlit UI
st.set_page_config(page_title="Zenga.hu Ingatlan Kereső AI", layout="centered")
st.title("🏡 Zenga.hu Ingatlan Kereső AI")

if openai.api_key:
    st.success("✅ OpenAI API kapcsolat rendben")

user_input = st.text_input(
    "Írd le, milyen ingatlant keresel:",
    placeholder="pl. Budapesten és Debrecenben keresek egy 80-120 m2-es családi házat maximum 50 millió forintért"
)

if user_input and openai.api_key:
    with st.spinner("🔍 Értelmezem a keresésed..."):
        parsed = interpret_input(user_input)
        
    if parsed and parsed.get("locations"):
        url, url_parts = build_zenga_url(parsed)
        
        if url:
            # Eredmény megjelenítése
            st.success("🎯 Keresés sikeresen értelmezve!")
            
            # Összefoglaló
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📍 Helyszínek:**")
                for loc in parsed["locations"]:
                    st.write(f"• {loc}")
                    
                if parsed.get("type"):
                    st.markdown(f"**🏠 Típus:** {parsed['type']}")
                    
            with col2:
                if parsed.get("size_min") or parsed.get("size_max"):
                    size_text = ""
                    if parsed.get("size_min") and parsed.get("size_max"):
                        size_text = f"{parsed['size_min']}-{parsed['size_max']} m²"
                    elif parsed.get("size_min"):
                        size_text = f"min. {parsed['size_min']} m²"
                    elif parsed.get("size_max"):
                        size_text = f"max. {parsed['size_max']} m²"
                    st.markdown(f"**📐 Alapterület:** {size_text}")
                
                if parsed.get("price_min") or parsed.get("price_max"):
                    price_text = ""
                    if parsed.get("price_min") and parsed.get("price_max"):
                        price_text = f"{parsed['price_min']}-{parsed['price_max']} M Ft"
                    elif parsed.get("price_min"):
                        price_text = f"min. {parsed['price_min']} M Ft"
                    elif parsed.get("price_max"):
                        price_text = f"max. {parsed['price_max']} M Ft"
                    st.markdown(f"**💰 Ár:** {price_text}")
            
            # Keresés indítása gomb
            st.markdown("---")
            st.markdown(f"🔗 **[📋 Keresés indítása a Zenga.hu-n]({url})**")
            
            # Debug információ
            with st.expander("🔧 Technikai részletek"):
                st.json(parsed)
                st.markdown("**URL részek:**")
                st.code(" + ".join(url_parts))
                st.markdown("**Teljes URL:**")
                st.code(url)
        else:
            st.error("❌ Nem sikerült URL-t generálni")
    else:
        st.warning("❓ Nem sikerült értelmezni a keresést. Próbáld konkrétabban megfogalmazni!")

# Használati útmutató
with st.expander("📖 Használati útmutató és példák"):
    st.markdown("""
    **✅ Jó példák:**
    - "Budapesten keresek lakást"
    - "Debrecenben 80-120 négyzetméteres családi házat szeretnék maximum 40 millió forintért"
    - "Budapest III. kerületben vagy Szentendrén 2-3 szobás házat keresek"
    - "Pécsett új építésű lakást keresek 60 négyzetmétertől"
    - "Szegeden gázfűtéses ikerházat keresek"
    
    **📋 Mit tud felismerni a rendszer:**
    - **Helyszínek:** Magyar városok, Budapest kerületek
    - **Típusok:** lakás, ház, családi ház, ikerház, sorház, villa, telek, garázs
    - **Méret:** alapterület m²-ben
    - **Ár:** millió forintban
    - **Szobák:** szobaszám
    - **Állapot:** új, újszerű, felújított, jó állapotú, átlagos
    - **Fűtés:** gáz, távfűtés, elektromos, központi
    
    **⚙️ API kulcs beállítása:**
    - Streamlit Cloud: `secrets.toml` → `OPENAI_API_KEY = "sk-..."`
    - Lokálisan: `export OPENAI_API_KEY="sk-..."`
    """)
