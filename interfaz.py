import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from datetime import datetime
import base64

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="CERCA", page_icon="favicon-32x32.png", layout="wide")

# --- CREDENCIALES Y CONEXIÓN ---
S_URL = "https://lyjavndjjsnmvzttoakr.supabase.co"
S_KEY = "sb_publishable_eMfGlf95NEYvF0vasqB4ew_pRpZTM2U"

@st.cache_resource
def init_connection():
    return create_client(S_URL, S_KEY)

supabase = init_connection()

# --- PERSONALIZACIÓN ESTÉTICA (CSS) ---
st.markdown("""
    <style>
    section[data-testid="stFileUploadDropzone"] div div::before { content: "Arrastra tu archivo TXT aquí"; font-weight: bold; color: #003366; }
    section[data-testid="stFileUploadDropzone"] div div span { display: none; }
    section[data-testid="stFileUploadDropzone"] button::before { content: "Buscar en mi PC"; }
    section[data-testid="stFileUploadDropzone"] button span { display: none; }
    
    .stApp { background-color: #f8fafc; }
    .stButton>button { background-color: #003366; color: white; border-radius: 10px; font-weight: bold; width: 100%; height: 3em; }
    [data-testid="stMetricValue"] { color: #003366; }

    .top-info-bar {
        background-color: #ffffff; padding: 10px; border-radius: 10px;
        border: 1px solid #003366; margin-bottom: 20px; text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }

    .float-wa {
        position:fixed; width:60px; height:60px; bottom:40px; right:40px;
        background-color:#25d366; color:#FFF; border-radius:50px; text-align:center;
        font-size:30px; box-shadow: 2px 2px 3px #999; z-index:100;
    }
    </style>
    
    <a href="https://wa.me/5493875904935?text=Hola%20Alfredo" class="float-wa" target="_blank">
    <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" width="60">
    </a>
    """, unsafe_allow_html=True)

# --- FUNCIONES ---
def registrar_usuario(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            supabase.table("control_licencias").insert({
                "user_id": res.user.id, "email": email, "nombre_usuario": email.split('@')[0],
                "consultas": 100, "tipo_pago": "PRUEBA", "activo": True
            }).execute()
            st.session_state.user = res.user
            return True, "✅ ¡Cuenta creada!"
        return False, "Error"
    except Exception as e: return False, str(e)

def login_usuario(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            # Seteamos la sesión
            st.session_state.user = res.user
            # En lugar de rerun aquí, devolvemos True
            return True
        return False
    except Exception: 
        return False

def obtener_usuario(user_id):
    try:
        res = supabase.table("control_licencias").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except: return None

def actualizar_perfil(datos, user_id):
    try:
        supabase.table("control_licencias").update(datos).eq("user_id", user_id).execute()
        return True
    except: return False

def obtener_novedades():
    try:
        res = supabase.table("novedades").select("*").order("prioridad", desc=True).execute()
        return res.data
    except: return []
def obtener_texto_marquee():
    try:
        # Traemos las novedades de la nueva tabla 'merquee'
        res = supabase.table("marquee").select("texto").eq("activo", True).execute()
        if res.data:
            return " | ".join([item['texto'] for item in res.data])
        return "CERCA Intelligence - Análisis de Riesgo en Tiempo Real"
    except:
        return "Bienvenido a CERCA"
def obtener_pagos_vinc(user_id):
    try:
        res = supabase.table("historial_pagos").select("*").eq("user_id", user_id).execute()
        return res.data
    except: return []

def actualizar_consultas(nuevo_saldo, user_id):
    supabase.table("control_licencias").update({"consultas": nuevo_saldo}).eq("user_id", user_id).execute()

def procesar_con_motor_fastapi(archivo, params):
    # IMPORTANTE: Usamos .getvalue() para obtener el contenido real del archivo
    files = {"file": (archivo.name, archivo.getvalue(), archivo.type)}
    try:
        r = requests.post("https://cerca-motor.onrender.com/procesar", files=files, params=params, timeout=60)
        return r.json()
    except Exception as e:
        print(f"Error detallado: {e}") # Esto te ayuda a ver qué pasa en la consola
        return None

def consultar_individual_api(cuil):
    try:
        r = requests.get(f"https://cerca-motor.onrender.com/consulta/{cuil}", timeout=20)
        return r.json() if r.status_code == 200 else None
    except: return None

def format_periodo(p_str):
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    try:
        anio = p_str[:4]
        mes_idx = int(p_str[4:]) - 1
        return f"{meses[mes_idx]} {anio[2:]}"
    except: return p_str
# --- BUSCÁ LA LÍNEA 120 APROX Y PEGÁ ESTO ---
def color_situacion(val):
    if val == "-": return 'color: #999'
    color = ""
    if val == 1: color = "background-color: #28a745; color: white" # Verde
    elif val == 2: color = "background-color: #ffc107; color: black" # Amarillo
    elif val == 3: color = "background-color: #6f42c1; color: white" # Lila
    elif val == 4: color = "background-color: #dc3545; color: white" # Rojo
    elif val >= 5: color = "background-color: #800000; color: white" # Bordó
    return color
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df[df['Dictamen'] == 'APROBADO'].to_excel(writer, sheet_name='Aprobados', index=False)
        df[df['Dictamen'] == 'RECHAZADO'].to_excel(writer, sheet_name='Rechazados', index=False)
    return output.getvalue()


# --- MANEJO DE SESIÓN ---
if "user" not in st.session_state: 
    st.session_state.user = None

# --- FUNCIÓN PARA EL FONDO (CORREGIDA) ---
def aplicar_fondo(ruta_imagen):
    try:
        with open(ruta_imagen, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{encoded_string}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except Exception:
        # Si falla la imagen, no hacemos nada para que no quede en blanco
        pass

# --- LÓGICA DE CONTROL DE PANTALLA ---
if st.session_state.user is None:
    # 1. PANTALLA DE LOGIN
    aplicar_fondo("fondo.png") # Cambia por tu nombre de archivo real
    
    st.title("📊 CERCA")
    
    col_l, col_r = st.columns([1, 1]) # Para centrar un poco el login
    with col_l:
        tab1, tab2 = st.tabs(["Ingresar", "Registrarse"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Contraseña", type="password")
                
                # El botón tiene que estar un nivel más ADENTRO (con Tab)
                submit = st.form_submit_button("Entrar")
            
            # Ahora la lógica del botón va afuera del with pero usando la variable
            if submit:
                if login_usuario(email, password):
                    st.success("✅ ¡Ingresando!")
                    st.rerun() 
                else:
                    st.error("❌ Credenciales inválidas o cuenta inexistente.")
                    
        with tab2:
            with st.form("register_form"):
                new_email = st.text_input("Nuevo Email")
                new_pass = st.text_input("Nueva Contraseña", type="password")
                if st.form_submit_button("Crear Cuenta"):
                    success, msg = registrar_usuario(new_email, new_pass)
                    if success: st.success(msg)
                    else: st.error(msg)
else:
    # --- 2. PANTALLA DE LA APLICACIÓN (POST-LOGIN) ---
    user_data = obtener_usuario(st.session_state.user.id)
    
    if user_data:
        # 1. Traemos las novedades de la tabla 'merquee'
        def obtener_marquee_dinamico():
            try:
                res = supabase.table("marquee").select("texto").eq("activo", True).execute()
                if res.data:
                    return " | ".join([item['texto'] for item in res.data])
                return "Bienvenido a CERCA Intelligence"
            except:
                return "CERCA - Análisis de Riesgo Bancario"

        texto_marquee = obtener_marquee_dinamico()

        # 2. Layout de Cabecera
        header_col1, header_col2 = st.columns([1, 5])
        with header_col1:
            st.image("icono.png", width=100)

        with header_col2:
            st.markdown(f"""
                <div style="background-color: #ffffff; border: 1px solid #003366; border-radius: 8px; padding: 3px; margin-top: 5px;">
                    <marquee scrollamount="6" style="color: #003366; font-weight: bold; font-family: Arial; font-size: 14px;">
                        {texto_marquee}
                    </marquee>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown(f"""
                <div style="text-align: right; padding-right: 5px;">
                    <span style='color:#28a745; font-weight:bold; font-size: 13px;'> 
                        💰 CRÉDITOS: {user_data.get('consultas', 0)}
                    </span>
                </div>
                """, unsafe_allow_html=True)

        # 3. Menú de Navegación
        menu = option_menu(None, ["Inicio", "Cartera Masiva", "Consulta Individual", "Pagos", "Mi Perfil"], 
            icons=['house', 'cloud-upload', 'person-search', 'credit-card', 'person-circle'], 
            default_index=0, orientation="horizontal")
    else:
        # Este else está alineado con "if user_data:"
        st.error("No se pudo cargar la información del perfil. Contacte a soporte.")
        if st.button("Salir"):
            st.session_state.user = None
            st.rerun()

    # --- PANTALLAS ---
    if menu == "Inicio":
        st.title(f"👋 ¡Bienvenido, {user_data.get('nombre_usuario')}!")
        novedades = obtener_novedades()
        if novedades:
            cols = st.columns(3)
            for i, nov in enumerate(novedades):
                with cols[i % 3]: st.info(f"**{nov.get('titulo')}**\n\n{nov.get('contenido')}")
        else: st.write("No hay novedades.")

    elif menu == "Cartera Masiva":
        # Barra lateral solo en Masiva como estaba
        with st.sidebar:
            st.title("CERCA 📊")
            st.success(f"Usuario: {user_data.get('nombre_usuario')}")
            st.markdown("---")
            st.header("⚙️ Filtros Masivos")
            
            # Filtro de Historial y Situación (Siempre activos)
            meses_filtro = st.slider("Historial (Meses)", 1, 24, 12)
            sit_max_filtro = st.number_input("Peor Situación Permitida", 1, 5, 1)
            
            st.markdown("---")
            # Nuevo Checkbox para habilitar/deshabilitar filtro de bancos
            aplicar_filtro_bancos = st.checkbox("Filtrar por Cantidad de Bancos", value=True)
            
            if aplicar_filtro_bancos:
                bancos_max = st.number_input("Máx. Bancos Actuales", 1, 15, 2)
            else:
                bancos_max = -1  # Usamos -1 como señal para "desactivado"
            
            excluir_mv = st.checkbox("Excluir MasVentas del conteo", value=True)
            if st.button("Cerrar Sesión", key="sidebar_logout"):
                supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()

        st.title("📂 CONSULTA MASIVA DE CARTERA")
        archivo_subido = st.file_uploader("Sube tu archivo .txt", type=["txt"])
        
        if archivo_subido and user_data:
            if st.button("EJECUTAR ANÁLISIS"):
                # 1. Validación de saldo previa
                consultas_actuales = user_data.get('consultas', 0)
                if consultas_actuales <= 0:
                    st.error("❌ Sin saldo suficiente para realizar la operación.")
                else:
                    with st.spinner("Analizando con CERCA Engine..."):
                        # Aseguramos que el puntero del archivo esté al inicio
                        archivo_subido.seek(0)
                        
                        # Preparamos parámetros del motor
                        params = {
                            "meses": meses_filtro, 
                            "bancos": bancos_max, 
                            "sit_max": sit_max_filtro
                        }
                        
                        # Llamada al motor FastAPI
                        resp = procesar_con_motor_fastapi(archivo_subido, params)
                        
                        if resp and resp.get("status") == "ok":
                            df = pd.DataFrame(resp["data"])
                            
                            # 2. Descuento de créditos según cantidad de registros procesados
                            nuevo_saldo = consultas_actuales - len(df)
                            actualizar_consultas(nuevo_saldo, st.session_state.user.id)
                            
                            # 3. Guardamos en sesión y forzamos refresco
                            st.session_state.resultado_analisis = df
                            st.rerun()
                        else:
                            st.error("❌ Error de conexión con el motor de análisis.")

        # --- SECCIÓN DE RESULTADOS ---
        if "resultado_analisis" in st.session_state:
            df_m = st.session_state.resultado_analisis
            
            # Métricas rápidas
            aprobados = len(df_m[df_m['Dictamen'] == 'APROBADO'])
            rechazados = len(df_m[df_m['Dictamen'] == 'RECHAZADO'])
            
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Consultados", len(df_m))
            c2.metric("Aprobados ✅", aprobados, delta_color="normal")
            c3.metric("Rechazados ❌", rechazados, delta_color="inverse")
            
            # Vista de tabla con estilo
            st.dataframe(df_m, use_container_width=True, hide_index=True)
            
            # Botón de descarga
            col_down, _ = st.columns([1, 2])
            with col_down:
                st.download_button(
                    label="📥 Descargar Reporte Excel",
                    data=to_excel(df_m),
                    file_name=f"CERCA_Masivo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            # Botón opcional para limpiar la vista
            if st.button("Limpiar Resultados"):
                del st.session_state.resultado_analisis
                st.rerun()

    elif menu == "Consulta Individual":
        st.title("🔍 CONSULTA INDIVIDUAL")
        cuil_busqueda = st.text_input("Ingrese CUIL / CUIT (Sin guiones)")
        
        if st.button("Buscar"):
            if user_data.get('consultas', 0) <= 0: st.error("Saldo insuficiente.")
            elif not cuil_busqueda: st.warning("Por favor, ingrese un CUIL.")
            else:
                with st.spinner("Consultando BCRA y analizando perfil..."):
                    # 0. Datos del ente (Billeteras/Retail) desde Supabase - USANDO TUS COLUMNAS
                    entes_nb = supabase.table("entes_no_bancarios").select("nombre_entidad, tipo").execute()
                    
                    # Creamos un diccionario para cruzar nombre (limpio) con su tipo
                    diccionario_nb = {
                        str(item['nombre_entidad']).upper().replace(".", "").strip(): item['tipo']
                        for item in entes_nb.data
                    } if entes_nb.data else {}
                    
                    lista_nb_limpia = list(diccionario_nb.keys())
                    
                    res_api = consultar_individual_api(cuil_busqueda)
                    
                    if res_api and "results" in res_api:
                        data = res_api["results"]
                        periodos = data.get("periodos", [])
                        
                        if periodos:
                            # 1. PROCESAMIENTO
                            labels, deudas, sits = [], [], []
                            entidades_actuales = []
                            historial_completo = {}
                            meses_labels = [format_periodo(p["periodo"]) for p in reversed(periodos[:24])]
                            
                            peor_sit_historica = 1
                            meses_en_peor_sit = 0
                            cuenta_nb = 0 
                            
                            for i, p in enumerate(reversed(periodos[:24])):
                                m_label = format_periodo(p["periodo"])
                                labels.append(m_label)
                                monto_mes, peor_sit_mes = 0, 1
                                
                                for ent in p.get("entidades", []):
                                    sit = int(ent.get("situacion", 1))
                                    nombre_ent_raw = str(ent['entidad']).upper()
                                    # Limpieza para el match
                                    nombre_ent_clean = nombre_ent_raw.replace(".", "").strip()
                                    
                                    if nombre_ent_raw not in historial_completo:
                                        historial_completo[nombre_ent_raw] = ["-"] * len(meses_labels)
                                    historial_completo[nombre_ent_raw][i] = sit
                                    
                                    if sit > 0:
                                        monto_mes += float(ent.get("monto", 0)) * 1000
                                        peor_sit_mes = max(peor_sit_mes, sit)
                                        if i == len(periodos[:24]) - 1:
                                            # Verificamos si es NB
                                            es_nb = any(nb in nombre_ent_clean for nb in lista_nb_limpia)
                                            # Guardamos el tipo para mostrarlo
                                            tipo_display = ""
                                            if es_nb:
                                                cuenta_nb += 1
                                                # Buscamos el tipo original en nuestro diccionario
                                                for k, v in diccionario_nb.items():
                                                    if k in nombre_ent_clean:
                                                        tipo_display = f" [{v}]"
                                                        break
                                            
                                            ent['tipo_display'] = tipo_display
                                            entidades_actuales.append(ent)
                                
                                deudas.append(monto_mes)
                                sits.append(peor_sit_mes)
                                if peor_sit_mes > peor_sit_historica:
                                    peor_sit_historica, meses_en_peor_sit = peor_sit_mes, 1
                                elif peor_sit_mes == peor_sit_historica and peor_sit_mes > 1:
                                    meses_en_peor_sit += 1

                            # 2. TENDENCIA Y SCORE
                            if len(deudas) >= 3:
                                d1, d2, d3 = deudas[-3], deudas[-2], deudas[-1]
                                if d1 < d2 < d3: tendencia = "Creciente 📈"
                                elif d1 > d2 > d3: tendencia = "Decreciente 📉"
                                else: tendencia = "Estable ↔️"
                            else: tendencia = "Estable ↔️"

                            score = 1000
                            score -= (peor_sit_historica - 1) * 150
                            score -= (meses_en_peor_sit * 20)
                            if len(periodos) < 12: score -= 200
                            if len(entidades_actuales) > 3: score -= 100
                            if cuenta_nb > 0:
                                factor_nb = cuenta_nb / len(entidades_actuales)
                                score -= 150 if factor_nb >= 0.5 else 50
                            score = max(0, min(1000, score))

                            # 3. INTERFAZ: ENCABEZADO Y DOSIER
                            st.markdown(f"### 👤 {data.get('denominacion', 'S/D')} | <span style='color:grey; font-size:18px;'>CUIT: {cuil_busqueda}</span>", unsafe_allow_html=True)
                            
                            sit_actual = sits[-1]
                            if score > 750 and sit_actual == 1 and cuenta_nb == 0:
                                color_bg, color_txt, status = "#d4edda", "#155724", "POTABLE"
                            elif score < 450 or sit_actual > 2:
                                color_bg, color_txt, status = "#f8d7da", "#721c24", "ALTO RIESGO / RECHAZADO"
                            else:
                                color_bg, color_txt, status = "#fff3cd", "#856404", "OBSERVADO"

                            dosier_html = f"""
                            <div style="background-color:{color_bg}; padding:25px; border-radius:15px; color:{color_txt}; border: 2px solid {color_txt}33; margin-bottom:25px;">
                                <h3 style="margin:0; font-size:20px;">📋 RESUMEN: {status}</h3>
                                <hr style="border: 0.5px solid {color_txt}33; margin: 10px 0;">
                                <p style="font-size:16px; line-height:1.6;">
                                    Analizado el perfil de <b>{data.get('denominacion')}</b>, se observa un comportamiento con tendencia <b>{tendencia}</b>. <br>
                                    La deuda total consolidada asciende a <b>${deudas[-1]:,.0f}</b> distribuida en <b>{len(entidades_actuales)}</b> entidades. <br>
                                    Situación actual en BCRA: <b>{sit_actual}</b> | Peor situación histórica: <b>{peor_sit_historica}</b>.
                                </p>
                                {"<p style='margin:5px 0; color:#856404;'>⚠️ <b>ALERTA DE SEGMENTO:</b> El cliente opera con tarjetas o billeteras no bancarias (Fintech/Retail).</p>" if cuenta_nb > 0 else ""}
                                {"<p style='margin:5px 0; color:#721c24;'>⚠️ <b>ALERTA DE DATOS:</b> Historial en BCRA inferior a 12 meses. Proceder con cautela.</p>" if len(periodos) < 12 else ""}
                            </div>
                            """
                            st.markdown(dosier_html, unsafe_allow_html=True)

                            # 4. GRÁFICOS Y MÉTRICAS
                            col_m, col_g = st.columns([1, 2])
                            with col_m:
                                st.metric("SCORE", f"{score} pts")
                                st.metric("DEUDA TOTAL", f"${deudas[-1]:,.0f}")
                                st.write("**Detalle de Entidades:**")
                                for ent in entidades_actuales:
                                    icono = " 💳" if ent.get('tipo_display') else ""
                                    st.write(f"- {ent['entidad']}{icono}{ent.get('tipo_display', '')} (Sit. {ent['situacion']})")
                            
                            with col_g:
                                fig = make_subplots(specs=[[{"secondary_y": True}]])
                                fig.add_trace(go.Bar(x=labels, y=deudas, name="Deuda ($)", marker_color="#AED6F1"), secondary_y=True)
                                fig.add_trace(go.Scatter(x=labels, y=sits, name="Situación", line=dict(color="#2E86C1", width=3)), secondary_y=False)
                                fig.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02))
                                st.plotly_chart(fig, use_container_width=True)

                            # 5. TABLA NOSIS
                            st.markdown("### 📊 HISTORIAL DE COMPORTAMIENTO")
                            df_nosis = pd.DataFrame.from_dict(historial_completo, orient='index', columns=meses_labels)
                            st.dataframe(df_nosis.style.map(color_situacion), use_container_width=True)
                            
                            actualizar_consultas(user_data['consultas'] - 1, st.session_state.user.id)
                        else:
                            st.info("Sin registros para este CUIL en el Banco Central.")

    elif menu == "Pagos":
        st.title("💳 Mis Pagos")
        pagos_data = obtener_pagos_vinc(st.session_state.user.id)
        if pagos_data:
            df_p = pd.DataFrame(pagos_data)
            st.table(df_p[['fecha', 'pago', 'estado']])
        else: st.info("Sin registros.")

    elif menu == "Mi Perfil":
        st.title("👤 Mi Perfil")
        if user_data:
            if not user_data.get('activo'): st.error("ESTADO: CUENTA SUSPENDIDA")
            else: st.success("ESTADO: CUENTA ACTIVA")
                
            with st.form("edit_perfil"):
                c1, c2 = st.columns(2)
                with c1:
                    n_nom = st.text_input("Nombre de Usuario", value=user_data.get('nombre_usuario', ''))
                    n_mail = st.text_input("Email de contacto", value=user_data.get('email', ''), disabled=True)
                with c2:
                    n_tel = st.text_input("Celular", value=user_data.get('telefono', ''))
                    st.caption("El email solo puede cambiarse desde soporte.")
                
                if st.form_submit_button("Guardar Cambios"):
                    actualizar_perfil({"nombre_usuario": n_nom, "telefono": n_tel}, st.session_state.user.id)
                    st.success("Perfil actualizado.")
                    st.rerun()
            
            if st.button("Cerrar Sesión"):
                supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()