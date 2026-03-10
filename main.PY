import os
import requests
import pandas as pd
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor # Para procesar en paralelo
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Sesión global de requests para mayor velocidad
http_session = requests.Session()
http_session.verify = False 

# Credenciales de Supabase
S_URL = "https://lyjavndjjsnmvzttoakr.supabase.co"
S_KEY = "sb_publishable_eMfGlf95NEYvF0vasqB4ew_pRpZTM2U"
supabase: Client = create_client(S_URL, S_KEY)

# Endpoint Oficial BCRA
API_HIST = "https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/Historicas/"

app = FastAPI(title="CERCA Intelligence Engine")

app = FastAPI(title="CERCA Intelligence Engine")

# --- LÓGICA DE PROCESAMIENTO ---

def consulta_individual_resumen(cuil, params):
    """ Función interna optimizada para uso con sesión y concurrencia """
    l_meses, l_bancos, l_sit = params
    try:
        cuil_clean = str(cuil).strip().replace("-", "")
        # Usamos la sesión global http_session
        r = http_session.get(API_HIST + cuil_clean, timeout=15)
        
        if r.status_code == 200:
            res_json = r.json()
            if not res_json.get("results"):
                return {"CUIL": cuil, "Nombre": "SIN DATOS", "Deuda": 0, "Dictamen": "APROBADO", "Motivo": "Sin historial"}
            
            data = res_json["results"]
            periodos = data.get("periodos", [])
            d_tot, b_cant, peor = 0, 0, 1
            
            if periodos:
                ult_p = periodos[0]
                bancos_vistos = set()
                for e in ult_p.get("entidades", []):
                    m_e = float(e.get("monto", 0)) * 1000
                    sit_e = int(e.get("situacion", 1))
                    entidad_nombre = str(e.get("entidad", "")).upper().strip()
                    d_tot += m_e
                    if "MASVENTAS" not in entidad_nombre:
                        if sit_e >= 1 or m_e > 0:
                            bancos_vistos.add(entidad_nombre)
                
                b_cant = len(bancos_vistos)
                hoy = datetime.now()
                for p in periodos:
                    try:
                        p_anio, p_mes = int(p["periodo"][:4]), int(p["periodo"][4:])
                        f_p = datetime(p_anio, p_mes, 1)
                        m_atras = (hoy.year - f_p.year) * 12 + (hoy.month - f_p.month)
                        
                        if m_atras <= l_meses:
                            for e in p.get("entidades", []):
                                sit_hist = int(e.get("situacion", 1))
                                if sit_hist > peor: peor = sit_hist
                    except: continue
            
            mots = []
            if peor > l_sit: mots.append(f"Sit {peor}")
            if l_bancos != -1 and b_cant > l_bancos: mots.append(f"{b_cant} Bancos")
            
            return {
                "CUIL": cuil, "Nombre": data.get("denominacion","S/D"), 
                "Deuda": d_tot, "Dictamen": "APROBADO" if not mots else "RECHAZADO",
                "Motivo": " | ".join(mots) if mots else "OK"
            }
        return {"CUIL": cuil, "Nombre": "NO REGISTRA", "Deuda": 0, "Dictamen": "APROBADO", "Motivo": "Sin deuda"}
    except Exception as e:
        return {"CUIL": cuil, "Nombre": "ERROR API", "Deuda": 0, "Dictamen": "ERROR", "Motivo": str(e)}
# --- ENDPOINTS ---

@app.get("/consulta/{cuil}")
async def obtener_datos_bcra(cuil: str):
    """ Endpoint para la Consulta Individual en Streamlit (Datos Reales) """
    try:
        # Limpiamos el CUIL de cualquier espacio o guion que llegue por error
        cuil_limpio = str(cuil).strip().replace("-", "")
        
        # Consultamos al BCRA
        r = requests.get(API_HIST + cuil_limpio, verify=False, timeout=15)
        
        if r.status_code == 200:
            return r.json() 
        
        return JSONResponse(
            status_code=r.status_code, 
            content={"error": f"BCRA error: {r.status_code}"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/procesar")
async def procesar_archivo(
    file: UploadFile = File(...), 
    meses: int = 12, 
    bancos: int = 2, 
    sit_max: int = 1
):
    """ Endpoint para Cartera Masiva: Procesa en paralelo para evitar Timeouts """
    content = await file.read()
    lineas = content.decode().splitlines()
    cuils = [l.strip() for l in lineas if l.strip().isdigit()]
    
    # Liberamos memoria del contenido original
    del content
    
    params = (meses, bancos, sit_max)

    # Lanzamos el procesamiento en paralelo (Max 15 trabajadores para no saturar Render)
    with ThreadPoolExecutor(max_workers=15) as executor:
        # Generamos las tareas para cada CUIL
        resultados = list(executor.map(lambda c: consulta_individual_resumen(c, params), cuils))
    
    return {"status": "ok", "data": resultados}

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 1. Primero definimos qué es 'port'
    # Intentamos leer el puerto que nos da Render, si no hay ninguno, usamos el 8000
    port = int(os.environ.get("PORT", 8000))
    
    # 2. Ahora que 'port' existe, ya lo podemos usar aquí
    uvicorn.run(app, host="0.0.0.0", port=port)