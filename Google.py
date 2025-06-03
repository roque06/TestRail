import streamlit as st
import requests
import time
import datetime
import csv
import io
import pandas as pd

# ======================
# 🔐 CONFIG
# ======================
API_KEY = "AIzaSyB7OnatWAP9vPcOYK5I6YSPKztd6575MLE"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + API_KEY
HEADERS = {
    "Content-Type": "application/json"
}

# ======================
# 🔁 API CALL
# ======================
def llamar_api(body, reintentos=3):
    for intento in range(reintentos):
        try:
            response = requests.post(API_URL, headers=HEADERS, json=body)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait_time = 2 ** intento
                st.warning(f"⏳ Límite alcanzado. Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                st.error(f"❌ Error HTTP: {e}")
                break
        except Exception as e:
            st.error(f"❌ Error inesperado: {e}")
            break
    return None

# ======================
# 🤖 PROMPTS
# ======================
def prompt_refinado(texto):
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Eres un analista QA experto.\nExtrae todas las condiciones QA del siguiente requerimiento. Usa redacción técnica. Un punto por línea.\n\nTexto:\n{texto}"
                    }
                ]
            }
        ]
    }

def prompt_csv(texto):
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"""Eres un generador experto de escenarios QA para TestRail.
Genera un CSV con columnas:
"Title","Preconditions","Steps","Expected Result","Type","Priority"

Instrucciones:
- Usa pasos numerados (1., 2., 3.) con saltos de línea reales (\\n).
- Los pasos deben estar redactados en infinitivo (por ejemplo, "Ingresar la cédula del cliente").
- Cada campo del CSV debe estar siempre entre comillas dobles.
- No uses "N/A" en precondiciones.
- No agregues explicaciones ni encabezados extra, solo el CSV directamente.
- Usa correctamente tildes, ñ y otros caracteres especiales.
- Si algún campo tiene saltos de línea (por ejemplo en Steps), mantenlos dentro del mismo campo con comillas.

Descripción funcional:
{texto}"""
                    }
                ]
            }
        ]
    }


# ======================
# 📋 FUNCIONES ADICIONALES
# ======================
def limpiar_csv_mejorado(texto):
    texto = texto.replace("```csv", "").replace("```", "").strip()
    texto = texto.replace('\\n', '\n').replace('\r\n', '\n')

    entrada = io.StringIO(texto)
    salida = io.StringIO()
    lector = csv.reader(entrada)

    escritor = csv.writer(salida, quoting=csv.QUOTE_ALL, delimiter=',', lineterminator='\r\n')

    for fila in lector:
        fila_limpia = [c.replace('"', '""').strip() for c in fila]
        escritor.writerow(fila_limpia)

    return salida.getvalue()

def csv_a_dataframe(texto_csv):
    try:
        texto_limpio = texto_csv.replace("```csv", "").replace("```", "").strip()
        entrada = io.StringIO(texto_limpio)

        df = pd.read_csv(
            entrada,
            delimiter=',',
            quoting=csv.QUOTE_ALL,
            engine='python',
            on_bad_lines='skip'
        )

        columnas_esperadas = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]
        df = df[[col for col in columnas_esperadas if col in df.columns]]
        return df
    except Exception as e:
        st.error(f"❌ Error al leer CSV como DataFrame: {e}")
        return None

# ======================
# 📋 INTERFAZ
# ======================
st.set_page_config("Generador QA", layout="wide")
st.title("🧪 Generador de Escenarios QA")

if "historial" not in st.session_state:
    st.session_state.historial = []

if "ultimo_csv" not in st.session_state:
    st.session_state.ultimo_csv = None
if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = None

texto = st.text_area("🔎 Ingresa la descripción funcional", height=250)

if st.button("Generar Casos de Prueba"):
    if not texto.strip():
        st.warning("❗ Ingresa una descripción.")
    else:
        st.info("⏳ Refinando descripción...")
        descripcion_refinada = llamar_api(prompt_refinado(texto))

        if descripcion_refinada:
            st.text_area("📄 Descripción Refinada", descripcion_refinada, height=250)
            st.info("🧪 Generando CSV...")

            resultado_csv = llamar_api(prompt_csv(descripcion_refinada))

            if resultado_csv:
                limpio = limpiar_csv_mejorado(resultado_csv)
                df = csv_a_dataframe(limpio)

                if df is not None:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                    st.text_area("📋 Resultado CSV", limpio, height=300)

                    st.session_state.historial.append({
                        "csv": limpio,
                        "ts": timestamp
                    })

                    st.session_state.ultimo_csv = limpio
                    st.session_state.ultimo_timestamp = timestamp

                    st.success("✅ Casos de prueba generados correctamente.")
                else:
                    st.error("❌ No se pudo convertir el CSV en tabla.")
            else:
                st.error("❌ Fallo en generación del CSV.")
        else:
            st.error("❌ Fallo en refinamiento.")

# ======================
# 📥 Descarga última versión
# ======================
st.markdown("---")
st.subheader("📥 Descargas")

if st.session_state.ultimo_csv:
    st.download_button(
        label="⬇️ Descargar último CSV generado",
        data='\ufeff' + st.session_state.ultimo_csv,
        file_name=f"casos_qa_{st.session_state.ultimo_timestamp}.csv",
        mime="text/csv",
        key="btn_descarga_csv"
    )
else:
    st.download_button("⬇️ Descargar último CSV generado", data="", file_name="casos_qa.csv", mime="text/csv", disabled=True)

# ======================
# 📂 Historial lateral
# ======================
st.sidebar.title("📁 Historial")
for i, item in enumerate(reversed(st.session_state.historial)):
    st.sidebar.download_button(
        label=f"CSV #{len(st.session_state.historial) - i} ({item['ts']})",
        data='\ufeff' + item["csv"],
        file_name=f"casos_qa_{item['ts']}.csv",
        mime="text/csv"
    )
