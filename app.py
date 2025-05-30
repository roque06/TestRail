import streamlit as st 
import requests
import csv
import io
import pandas as pd
import time

# Configuración de la página: debe ir primero
st.set_page_config(page_title="Generador QA TestRail", layout="centered")

API_KEY = st.secrets["OPENROUTER_API_KEY"]

# Mostrar parte del API_KEY (opcional, para debug, después de set_page_config)
st.write(f"API_KEY leído: {API_KEY[:6]}... (oculto por seguridad)")

TIPOS_VALIDOS = {"Functional", "Negative", "Performance", "Security", "Usability"}
PRIORIDADES_VALIDAS = {"High", "Medium", "Low"}

def llamar_api_con_reintentos(body, max_reintentos=3):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    for intento in range(max_reintentos):
        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            contenido = data['choices'][0]['message']['content'].strip()
            if contenido.lower() in ["", "ninguno", "no aplica", "n/a", "no hay información"]:
                st.warning(f"Respuesta inválida del modelo, reintentando... ({intento+1}/{max_reintentos})")
                time.sleep(1)
                continue
            return contenido
        except Exception as e:
            st.error(f"Error en la petición a la API: {e}")
            break
    return None

def refinar_descripcion(texto_original):
    prompt = f"""
Eres un analista QA altamente experimentado. Tu misión es analizar una descripción funcional escrita de forma libre y transformarla en una lista estructurada, clara y exhaustiva de reglas, restricciones, validaciones, condiciones y comportamientos esperados que puedan ser usados para crear escenarios de prueba.

✅ No resumas. ✅ No inventes. ✅ No omitas. ✅ No generes casos de prueba aún.

Tu salida debe ser una lista de puntos estructurados que incluyan:
- Validaciones explícitas o implícitas.
- Reglas de negocio.
- Requisitos funcionales y no funcionales.
- Condiciones lógicas.
- Restricciones.

Texto original:
{texto_original}
"""
    body = {
        "model": "openrouter/openai/gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Eres un experto en QA y análisis funcional."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
    }
    contenido = llamar_api_con_reintentos(body)
    if contenido is None:
        return "Error: No se pudo obtener una descripción refinada válida después de varios intentos."
    return contenido

def generar_escenarios_csv(descripcion):
    prompt = f"""
Eres un ingeniero QA especializado en documentación para TestRail. A partir de la siguiente descripción funcional, genera casos de prueba detallados y profesionales en formato CSV con las siguientes columnas:
"Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"

🔹 Title: Nombre conciso y claro del caso.
🔹 Preconditions: Siempre deben estar presentes. Extrae condiciones necesarias del contexto funcional. Si no son explícitas, deduce condiciones realistas que deben cumplirse antes de ejecutar la prueba. ❌ No uses "Ninguna", "N/A", ni valores vacíos.
🔹 Steps: Instrucciones numeradas, precisas y claras.
🔹 Expected Result: Resultado esperado exacto para el tester.
🔹 Type: Uno de estos: Functional, Negative, Performance, Security, Usability.
🔹 Priority: Uno de estos: High, Medium, Low.

⚠️ Devuelve **solo** el CSV. Sin explicaciones ni código ni texto adicional.

Descripción funcional:
{descripcion}
"""
    body = {
        "model": "openrouter/openai/gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Eres un experto en QA y pruebas de software."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
    }
    contenido = llamar_api_con_reintentos(body)
    if contenido is None:
        st.error("No se pudo generar un CSV válido después de varios intentos.")
        return ""
    return contenido

def limpiar_csv_crudo(csv_crudo, columnas_esperadas=6):
    csv_crudo = (
        csv_crudo.strip()
        .replace("Â", "")
        .replace("Ã³", "ó")
        .replace("Ã¡", "á")
        .replace("Ã©", "é")
        .replace("Ã­", "í")
        .replace("Ãº", "ú")
        .replace("Ã±", "ñ")
    )

    f = io.StringIO(csv_crudo)
    reader = csv.reader(f, delimiter=',', quotechar='"')

    filas_validas = []
    encabezado = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]
    filas_incompletas = []

    for fila in reader:
        fila = [celda.strip() for celda in fila]
        if not fila or all(celda == "" for celda in fila):
