import streamlit as st
import psycopg2 
import pandas as pd
from psycopg2.extras import RealDictCursor 
import io
import xlsxwriter 

# --- CONFIGURACIÓN DE NOMBRES ---
# 'nombre_medio' de la BD se interpreta como 'fase_cultivo'
FASE_COLUMNA = 'nombre_medio' 
# 'especie_planta' es la nueva columna (debe existir en la BD)
ESPECIE_COLUMNA = 'especie_planta' 


# --- Función para obtener la conexión a la base de datos ---
def get_db_connection():
    """
    Establece y devuelve una conexión NUEVA a la base de datos PostgreSQL.
    """
    try:
        # st.secrets lee automáticamente el archivo .streamlit/secrets.toml
        conn = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            port=st.secrets["postgres"]["port"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            connect_timeout=5,
            sslmode='require' 
        )
        return conn
    
    except KeyError as e:
        st.error(f"Error de configuración: Falta la clave {e} en secrets.toml. Asegúrate de que las claves 'host', 'port', etc., existan bajo [postgres].")
        st.stop()
    
    except psycopg2.OperationalError as e:
        st.error(f"Error de conexión a la BD: {e}")
        st.warning("Verifica que el servicio PostgreSQL esté activo y que el host/puerto en secrets.toml sea correcto.")
        st.stop()


# --- Función para insertar un nuevo registro ---
def insertar_medio_cultivo(especie, fase, ingrediente, concentracion, unidad):
    conn = None 
    cur = None
    try:
        conn = get_db_connection() # Obtiene una conexión NUEVA
        cur = conn.cursor()
        
        # Insertamos especie_planta (el nuevo campo) y nombre_medio (que es la fase)
        sql = f"""
        INSERT INTO medios_cultivo ({ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente, concentracion, unidad) 
        VALUES (%s, %s, %s, %s, %s);
        """
        cur.execute(sql, (especie, fase, ingrediente, float(concentracion), unidad))
        
        conn.commit()
        st.success(f"¡Ingrediente '{ingrediente}' guardado para {especie}/{fase}!")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error al guardar en la base de datos: {e}")
        return False
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close() 

# --- Función para obtener todos los registros ---
def obtener_medios_cultivo():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Seleccionamos todas las columnas, incluyendo la nueva especie
        sql = f"SELECT id, {ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente, concentracion, unidad FROM medios_cultivo ORDER BY {ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente;"
        cur.execute(sql)
        
        registros = cur.fetchall()
        return registros
        
    except psycopg2.Error as e:
        st.error(f"Error al leer la base de datos: {e}")
        return []
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Función para obtener todos los nombres de ESPECIES únicos ---
def obtener_nombres_especies():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Selecciona los nombres únicos de especies
        cur.execute(f"SELECT DISTINCT {ESPECIE_COLUMNA} FROM medios_cultivo WHERE {ESPECIE_COLUMNA} IS NOT NULL AND {ESPECIE_COLUMNA} != '' ORDER BY {ESPECIE_COLUMNA};")
        return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Error al obtener nombres de especies: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Función para obtener todas las FASES de cultivo únicas ---
def obtener_nombres_fases():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Selecciona los nombres únicos de fases (antes fórmulas)
        cur.execute(f"SELECT DISTINCT {FASE_COLUMNA} FROM medios_cultivo WHERE {FASE_COLUMNA} IS NOT NULL AND {FASE_COLUMNA} != '' ORDER BY {FASE_COLUMNA};")
        return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Error al obtener nombres de fases: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# --- Función para eliminar un registro por ID ---
def eliminar_medio_cultivo(registro_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = "DELETE FROM medios_cultivo WHERE id = %s;"
        cur.execute(sql, (registro_id,))
        
        conn.commit()
        st.success(f"Registro ID {registro_id} eliminado de la base de datos.")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error al eliminar de la base de datos: {e}")
        return False
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Funciones Auxiliares para la Descarga ---
def convertir_a_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def convertir_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Medios_de_Cultivo')
    return output.getvalue()

# --- Función para actualizar un registro por ID ---
def actualizar_medio_cultivo(registro_id, especie, fase, ingrediente, concentracion, unidad):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Actualizamos la nueva columna 'especie_planta' y 'nombre_medio' (la fase)
        sql = f"""
        UPDATE medios_cultivo 
        SET {ESPECIE_COLUMNA} = %s, {FASE_COLUMNA} = %s, ingrediente = %s, concentracion = %s, unidad = %s
        WHERE id = %s;
        """
        cur.execute(sql, (especie, fase, ingrediente, float(concentracion), unidad, registro_id))
        
        conn.commit()
        st.success(f"Registro ID {registro_id} actualizado exitosamente a: {especie} / {fase} - {ingrediente}")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error al actualizar la base de datos: {e}")
        return False
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- AQUÍ COMIENZA LA INTERFAZ DE USUARIO ---
st.title("🌱 Gestión de Medios de Cultivo (Especies y Fases)")

# Lógica de verificación de conexión 
try:
    conn = get_db_connection()
    st.sidebar.success("✅ Conexión a la base de datos establecida.")
    conn.close() 
except Exception:
    pass

# --- OBTENER OPCIONES GLOBALES PARA REGISTRO Y FILTRO ---
nombres_especies_existentes = obtener_nombres_especies()
nombres_fases_existentes = obtener_nombres_fases()

# Opciones de Especie para el formulario de registro (tab1)
opciones_especie = ["-- Seleccionar Especie --", "Nueva Especie"] + nombres_especies_existentes
opciones_especie = list(set(opciones_especie))
opciones_especie.sort()

# Opciones de Fase para el formulario de registro (tab1)
opciones_fase = ["-- Seleccionar Fase --", "Nueva Fase"] + nombres_fases_existentes
opciones_fase = list(set(opciones_fase))
opciones_fase.sort()

# TABS
tab1, tab2, tab3 = st.tabs(["➕ Registrar Ingrediente", "📋 Catálogo / Edición", "🧪 Medios de Cultivo por Especie"])

with tab1:
    st.subheader("➕ Registrar Nuevo Ingrediente por Especie/Fase")
    
    with st.form(key="form_registrar_medio"):
        
        # --- INPUT ESPECIE (NUEVO) ---
        especie = st.selectbox(
            "1. Especie de Planta:", 
            options=opciones_especie,
            key="input_especie"
        )
        if especie == "Nueva Especie":
            especie = st.text_input("Escribe el nombre de la Nueva Especie:", key="nuevo_nombre_especie").strip()
            if not especie:
                especie = None

        # --- INPUT FASE DE CULTIVO (Antes, Nombre de Medio) ---
        fase_cultivo = st.selectbox(
            "2. Fase de Cultivo (Medio):", 
            options=opciones_fase,
            key="input_fase_cultivo"
        )
        if fase_cultivo == "Nueva Fase":
            fase_cultivo = st.text_input("Escribe el nombre de la Nueva Fase de Cultivo:", key="nuevo_fase_cultivo").strip()
            if not fase_cultivo:
                fase_cultivo = None

        st.markdown("---")
        
        # El resto de tus campos:
        ingrediente = st.text_input("3. Ingrediente (ej: Sacarosa)", key="input_ingrediente").strip()
        concentracion = st.number_input("4. Concentración", min_value=0.0, format="%.4f", key="input_concentracion")
        unidad = st.selectbox("5. Unidad de Medida", ["mg/L", "g/L", "mM"], key="input_unidad")

        submit_button = st.form_submit_button(label='💾 Guardar Ingrediente', type="primary")

        # 3. Lógica de inserción de datos
        if submit_button:
            if especie and fase_cultivo and ingrediente and concentracion is not None:
                insertar_medio_cultivo(especie, fase_cultivo, ingrediente, concentracion, unidad)
            else:
                st.error("Todos los campos (Especie, Fase, Ingrediente, Concentración) son obligatorios. Por favor, revisa.")

# Inicializa una variable de estado para saber qué ID se está editando
if 'edit_id' not in st.session_state:
    st.session_state.edit_id = None

with tab2:
    st.subheader("🔍 Catálogo, Filtro y Herramientas de Edición")
    
    # 1. OBTENER DATOS ORIGINALES
    datos_medios = obtener_medios_cultivo()
    
    if datos_medios:
        df = pd.DataFrame(datos_medios)
        
        # --- LÓGICA DE FILTRADO POR ESPECIE ---
        nombres_especies_filtrado = obtener_nombres_especies()
        
        opciones_filtro_especie = ["Mostrar todos"] + nombres_especies_filtrado

        # Crea el SelectBox para elegir la Especie
        filtro_seleccionado_especie = st.selectbox(
            "Filtrar por Especie de Planta:",
            options=opciones_filtro_especie,
            index=0
        )
        
        # Aplicar el filtro de Especie
        if filtro_seleccionado_especie != "Mostrar todos":
            df_filtrado = df[df[ESPECIE_COLUMNA] == filtro_seleccionado_especie]
            st.info(f"Mostrando solo ingredientes para la especie: **{filtro_seleccionado_especie}**")
        else:
            df_filtrado = df 
            st.info("Mostrando todos los ingredientes en el catálogo.")

        # --- BOTONES DE DESCARGA ---
        if not df_filtrado.empty:
            
            # Quitar la columna 'id' que es interna de la base de datos antes de descargar
            df_descarga = df_filtrado.drop(columns=['id'])
            
            col_csv, col_excel = st.columns(2)
            
            # Botón de Descarga CSV
            with col_csv:
                st.download_button(
                    label="⬇️ Descargar como CSV",
                    data=convertir_a_csv(df_descarga),
                    file_name='catalogo_invitro.csv',
                    mime='text/csv',
                    type="secondary"
                )
            
            # Botón de Descarga Excel
            with col_excel:
                st.download_button(
                    label="⬇️ Descargar como Excel (XLSX)",
                    data=convertir_a_excel(df_descarga),
                    file_name='catalogo_invitro.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="secondary"
                )

        st.markdown("---") 
        
        # --- LÓGICA DE EDICIÓN ---
        if st.session_state.edit_id is not None:
            registro_a_editar = df[df['id'] == st.session_state.edit_id].iloc[0]
            
            st.warning(f"Editando: {registro_a_editar[ESPECIE_COLUMNA]} / {registro_a_editar[FASE_COLUMNA]} - {registro_a_editar['ingrediente']}")
            
            with st.form(key="form_editar_medio", clear_on_submit=False):
                
                # Campos precargados con los valores actuales del registro
                # CAMPO ESPECIE A EDITAR
                especie_edit = st.text_input("Especie de Planta", value=registro_a_editar[ESPECIE_COLUMNA], key="edit_especie")
                # CAMPO FASE A EDITAR
                fase_cultivo_edit = st.text_input("Fase de Cultivo", value=registro_a_editar[FASE_COLUMNA], key="edit_fase_cultivo")

                ingrediente_edit = st.text_input("Ingrediente", value=registro_a_editar['ingrediente'], key="edit_ingrediente")
                concentracion_edit = st.number_input("Concentración", value=float(registro_a_editar['concentracion']), format="%.4f", min_value=0.0, key="edit_concentracion")
                
                # Usamos los nombres de las fases existentes para el selectbox de edición
                opciones_unidad = ["mg/L", "g/L", "mM"]
                try:
                    unidad_index = opciones_unidad.index(registro_a_editar['unidad'])
                except ValueError:
                    unidad_index = 0 # Default si no se encuentra
                
                unidad_edit = st.selectbox("Unidad de Medida", opciones_unidad, index=unidad_index, key="edit_unidad")


                col_update, col_cancel = st.columns(2)

                # Botón de Guardar
                with col_update:
                    if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                        actualizar_medio_cultivo(
                            st.session_state.edit_id, 
                            especie_edit, 
                            fase_cultivo_edit, 
                            ingrediente_edit, 
                            concentracion_edit, 
                            unidad_edit
                        )
                        st.session_state.edit_id = None # Sale del modo edición
                        st.rerun() # Fuerza la actualización
                
                # Botón de Cancelar
                with col_cancel:
                    if st.form_submit_button("🚫 Cancelar"):
                        st.session_state.edit_id = None # Sale del modo edición
                        st.rerun()
            st.markdown("---")

        # --- Visualización de Registros Filtrados y Botones ---
        # Itera sobre el DataFrame FILTRADO
        for index, row in df_filtrado.iterrows(): 
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15]) 
            
            # Muestra Especie / Fase
            col1.write(
                f"**{row[ESPECIE_COLUMNA]}** / **{row[FASE_COLUMNA]}** — {row['ingrediente']} "
                f"({row['concentracion']:.4f} {row['unidad']})"
            )
            
            # Columna 2: Botón de Editar
            with col2:
                def set_edit_mode(record_id):
                    st.session_state.edit_id = record_id

                st.button(
                    "✏️", 
                    key=f"edit_btn_{row['id']}", 
                    on_click=set_edit_mode, 
                    args=(row['id'],)
                )

            # Columna 3: Botón de Eliminar
            with col3:
                with st.form(key=f"delete_form_{row['id']}", clear_on_submit=False):
                    st.form_submit_button(
                        "🗑️", 
                        type="primary", 
                        on_click=eliminar_medio_cultivo, 
                        args=(row['id'],) 
                    )

        st.caption("Estructura de la base de datos (Referencia):")
        # Mostrar la tabla filtrada incluyendo el nuevo campo 'especie_planta'
        df_display = df_filtrado.drop(columns=['id']).rename(columns={FASE_COLUMNA: 'Fase de Cultivo', ESPECIE_COLUMNA: 'Especie'})
        st.dataframe(df_display, use_container_width=True)

    else: 
        st.info("Aún no hay medios de cultivo registrados en la base de datos.")
        with tab3:
    st.subheader("🧪 Composición Detallada por Especie y Fase")

    # Obtenemos TODAS las especies registradas
    nombres_especies = obtener_nombres_especies()
    
    if not nombres_especies:
        st.info("Aún no hay especies ni medios de cultivo registrados para mostrar.")
    else:
        st.markdown(f"**Total de Especies con Medios Registrados:** **{len(nombres_especies)}**")
        st.markdown("---")
        
        datos_medios = obtener_medios_cultivo()
        if not datos_medios:
            st.info("No hay datos de ingredientes para agrupar.")
            pass
        else:
            df_completo = pd.DataFrame(datos_medios)
            
            # 1. Iterar sobre cada especie única
            for especie in nombres_especies:
                st.header(f"🌿 Especie: {especie}")
                
                # Filtrar el DF por la especie actual
                df_especie = df_completo[df_completo[ESPECIE_COLUMNA] == especie]
                
                # Obtener las fases (nombre_medio) únicas para esta especie
                fases_especie = df_especie[FASE_COLUMNA].unique()
                
                # 2. Iterar sobre cada fase de cultivo dentro de la especie
                for fase in fases_especie:
                    
                    with st.expander(f"🧬 Fase de Cultivo: **{fase}**"):
                        
                        # Filtrar los ingredientes específicos para esta Especie y Fase
                        df_fase = df_especie[df_especie[FASE_COLUMNA] == fase]
                        
                        # Seleccionar solo las columnas necesarias y renombrar
                        df_display_fase = df_fase[['ingrediente', 'concentracion', 'unidad']].copy()
                        df_display_fase.columns = ['Ingrediente', 'Concentración', 'Unidad']

                        # Formatear la concentración
                        df_display_fase['Concentración'] = df_display_fase['Concentración'].apply(lambda x: f"{x:.4f}")
                        
                        # Mostrar la tabla
                        st.dataframe(df_display_fase, hide_index=True, use_container_width=True)

                st.markdown("---")
                
