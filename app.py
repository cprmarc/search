# app.py

import streamlit as st
import openai
import urllib.parse

# 🔐 Állítsd be az OpenAI API kulcsot
openai.api_key = "sk-..."  # <- Cseréld ki a saját kulcsodra

# 📌 OpenAI alapú értelmezés
def interpret_input(question: str):
    prompt = f"""A felhasználó ingatlanhirdetést keres. Emeld ki a magyarországi helyszíneket (települések, kerületek), az ingatlan típusát (pl. ház, lakás), és a hozzávetőleges alapterületet (m2).
Válaszolj egyetlen Python szótár formájában az alábbi kulcsokkal: "locations" (lista), "type" (sztring), "size" (szám, m2).

Példa:
Kérdés: "Budapesten és Érden keresek egy legalább 100 négyzetméteres házat"
Válasz: {{ "locations": ["Budapest", "Érd"], "type": "ház", "size": 100 }}

Kérdés: "{question}"
Válasz:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message["content"].strip()
    try:
        result = eval(content)
        return result
    except:
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

user_input = st.text_input("Írd ide, milyen ingatlant keresel", placeholder="pl. Budapesten és Érden keresek egy 100 négyzetméteres házat")

if user_input:
    with st.spinner("Értelmezem a keresésed..."):
        parsed = interpret_input(user_input)
        url, visible_parts = build_url(parsed)

    if parsed["locations"]:
        preview = ", ".join(visible_parts)
        st.markdown(f"🔗 [Keresés: {preview}](%s)" % urllib.parse.quote(url, safe=':/'), unsafe_allow_html=True)
    else:
        st.warning("Nem sikerült értelmezni a helyszíneket vagy típust. Próbáld újrafogalmazni!")
