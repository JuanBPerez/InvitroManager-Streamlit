import streamlit as st
import psycopg2 
import pandas as pd
from psycopg2.extras import RealDictCursor 
import io
import xlsxwriter 
import bcrypt # Necesita 'pip install bcrypt'

# ====================================================================
#              ⚙️ CONFIGURACIÓN Y FUNCIONES DE SEGURIDAD ⚙️
# ====================================================================

# --- CONFIGURACIÓN DE NOMBRES ---
FASE_COLUMNA = 'nombre_medio' 
ESPECIE_COLUMNA = 'especie_planta' 

# Inicializar estado de sesión para autenticación
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False

# --- Hashing y Verificación con bcrypt ---
def get_hashed_password(password):
    """Genera un hash seguro para la contraseña."""
    # El password debe ser una cadena de bytes para bcrypt
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed

def check_hashed_password(password, hashed_password):
    """Verifica la contraseña ingresada contra el hash guardado."""
    # Ambas entradas deben ser bytes. password se codifica, hashed_password ya es bytes (de la DB)
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

# --- Funciones de Gestión de Usuarios en BD ---

def get_db_connection():
    """Establece y devuelve una conexión NUEVA a la base de datos."""
    try:
        conn = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            port=st.secrets["postgres"]["port"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            connect_timeout=5,
            sslmode=st.secrets["postgres"]["sslmode"] 
        )
        return conn
    except KeyError as e:
        st.error(f"Error de configuración: Falta la clave {e} en secrets.toml.")
        st.stop()
    except psycopg2.OperationalError as e:
        st.error(f"Error de conexión a la BD: {e}")
        st.warning("Verifica la conexión a PostgreSQL.")
        st.stop()
    except Exception as e:
        st.error(f"Error inesperado al conectar a la BD: {e}")
        st.stop()

def get_user_from_db(username):
    """Busca un usuario por nombre y devuelve su hash (como bytes) y estado de admin."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # La columna hashed_password debe ser de tipo BYTEA en PostgreSQL
        sql = "SELECT hashed_password, is_admin FROM users WHERE username = %s;"
        cur.execute(sql, (username,))
        result = cur.fetchone()
        
        if result:
            hashed_from_db = result[0]
            
            # --- FIX CRÍTICO ---
            # Aseguramos que el hash devuelto sea un objeto `bytes`, ya que psycopg2 
            # a veces lo devuelve como string codificado (ej: latin1 o ascii)
            if isinstance(hashed_from_db, str):
                # Intentamos decodificar el hex o asumimos latin1 si no es hex
                try:
                    hashed_from_db = bytes.fromhex(hashed_from_db)
                except ValueError:
                    hashed_from_db = hashed_from_db.encode('latin1')
            # --- FIN FIX CRÍTICO ---
            
            return {'hashed_password': hashed_from_db, 'is_admin': result[1]}
        return None
    finally:
        if cur: cur.close()
        if conn: conn.close()

def check_for_any_user_in_db():
    """Verifica rápidamente si existe al menos un usuario en la tabla."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = "SELECT 1 FROM users LIMIT 1;"
        cur.execute(sql)
        return cur.fetchone() is not None
    except psycopg2.Error as e:
        # Si falla la consulta, asumimos que no hay usuarios o hay un problema de permisos
        st.error(f"Error al verificar la existencia de usuarios: {e}")
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close()

def add_user_to_db(username, password, is_admin=False):
    """Inserta un nuevo usuario en la tabla 'users'."""
    conn = None
    cur = None
    if not username or not password:
        st.error("Usuario y contraseña no pueden estar vacíos.")
        return False
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Hashear la contraseña
        hashed_password = get_hashed_password(password)
        
        # 2. Insertar en la BD
        # hashed_password ya es bytes, lo insertamos directamente en la columna BYTEA
        sql = "INSERT INTO users (username, hashed_password, is_admin) VALUES (%s, %s, %s);"
        cur.execute(sql, (username, hashed_password, is_admin))
        conn.commit()
        
        st.success(f"Usuario '{username}' creado exitosamente (Admin: {is_admin}).")
        return True
        
    except psycopg2.errors.UniqueViolation:
        st.error(f"El usuario '{username}' ya existe.")
        return False
    except psycopg2.Error as e:
        st.error(f"Error al guardar el usuario en la BD: {e}")
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Lógica Principal de Autenticación ---

def check_password():
    """
    Controla el acceso de los usuarios consultando la base de datos.
    Muestra la interfaz de login o el setup inicial.
    Retorna True si el usuario está autenticado, False en caso contrario.
    """
    def password_entered():
        """Verifica la contraseña introducida contra el hash en la BD."""
        username = st.session_state["username_input"].strip()
        password = st.session_state["password_input"]
        
        user_data = get_user_from_db(username)
        
        if user_data:
            # El hash ya viene en formato bytes gracias al FIX en get_user_from_db
            hashed_from_db = user_data['hashed_password']
            
            if check_hashed_password(password, hashed_from_db):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["is_admin"] = user_data['is_admin']
                return True

        st.session_state["authenticated"] = False
        return False

    # 1. Si NO está autenticado, muestra el formulario de Login o Setup
    if not st.session_state.authenticated:
        
        # Utilizamos la nueva función para verificar si existe CUALQUIER usuario
        users_exist = check_for_any_user_in_db()

        # --- Check para inicializar el primer usuario si la tabla está vacía ---
        if not users_exist: 
            st.warning("⚠️ No hay usuarios registrados. Crea el primer usuario administrador.")
            with st.form("Initial_Admin_Setup"):
                admin_user = st.text_input("Usuario Administrador:", key="admin_user_setup").strip()
                admin_password = st.text_input("Contraseña:", type="password", key="admin_password_setup").strip()
                
                if st.form_submit_button("Crear Administrador Inicial", type="primary"):
                    if admin_user and admin_password:
                        if add_user_to_db(admin_user, admin_password, is_admin=True):
                            # Si la creación fue exitosa, pre-rellenamos el login para facilitar
                            st.session_state["username_input"] = admin_user
                            st.session_state["password_input"] = admin_password
                            st.experimental_rerun() 
                    else:
                        st.error("Rellena ambos campos.")

        # --- Formulario de Login ---
        st.title("🔐 Acceso al Gestor de Medios")
        with st.form("Login"):
            st.text_input("Usuario:", key="username_input")
            st.text_input("Contraseña:", type="password", key="password_input")
            
            st.form_submit_button("Entrar", on_click=password_entered, type="primary")
            
            # Muestra el error de login si la verificación falló en el último submit
            # Solo si el usuario intentó un submit que resultó en autenticación fallida
            if st.session_state.authenticated == False and 'username_input' in st.session_state and st.session_state["username_input"]:
                st.error("Usuario o contraseña incorrectos.")
        
        st.stop() # Detiene la ejecución para no mostrar la UI principal
        return False 
    
    # 2. Si está autenticado
    return True 

# ====================================================================
#              FUNCIONES DE DATOS Y CONVERSIÓN (sin cambios)
# ====================================================================

# --- Función para insertar un nuevo registro ---
def insertar_medio_cultivo(especie, fase, ingrediente, concentracion, unidad):
    conn = None 
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = f"""
        INSERT INTO medios_cultivo ({ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente, concentracion, unidad) 
        VALUES (%s, %s, %s, %s, %s);
        """
        cur.execute(sql, (especie, fase, ingrediente, float(concentracion), unidad))
        conn.commit()
        st.success(f"¡Ingrediente '{ingrediente}' guardado para **{especie}** / **{fase}**!")
        return True
    except psycopg2.Error as e:
        st.error(f"Error al guardar en la base de datos: {e}")
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close() 

# --- Función para obtener todos los registros ---
def obtener_medios_cultivo():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = f"SELECT id, {ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente, concentracion, unidad FROM medios_cultivo ORDER BY {ESPECIE_COLUMNA}, {FASE_COLUMNA}, ingrediente;"
        cur.execute(sql)
        registros = cur.fetchall()
        return registros
    except psycopg2.Error as e:
        st.error(f"Error al leer la base de datos: {e}")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Función para obtener todos los nombres de ESPECIES únicos ---
def obtener_nombres_especies():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT DISTINCT {ESPECIE_COLUMNA} FROM medios_cultivo WHERE {ESPECIE_COLUMNA} IS NOT NULL AND {ESPECIE_COLUMNA} != '' ORDER BY {ESPECIE_COLUMNA};")
        return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Error al obtener nombres de especies: {e}")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Función para obtener todas las FASES de cultivo únicas ---
def obtener_nombres_fases():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT DISTINCT {FASE_COLUMNA} FROM medios_cultivo WHERE {FASE_COLUMNA} IS NOT NULL AND {FASE_COLUMNA} != '' ORDER BY {FASE_COLUMNA};")
        return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Error al obtener nombres de fases: {e}")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()

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
        # Forzar un rerun para actualizar la lista
        st.experimental_rerun()
        return True
    except psycopg2.Error as e:
        st.error(f"Error al eliminar de la base de datos: {e}")
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close()

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
        if cur: cur.close()
        if conn: conn.close()

# ====================================================================
#              INTERFAZ DE USUARIO PRINCIPAL (app_ui) (sin cambios)
# ====================================================================

def app_ui():
    """Contiene toda la lógica de la UI que requiere autenticación."""
    
    # 1. Botón de Cerrar Sesión en la barra lateral
    def logout():
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["is_admin"] = False
        st.experimental_rerun()
    
    status_text = f"Conectado como **{st.session_state['username']}**"
    if st.session_state['is_admin']:
        status_text += " (ADMIN)"
    
    st.sidebar.markdown(status_text)
    st.sidebar.button("🚪 Cerrar Sesión", on_click=logout)
    
    # 2. Título y Check de Conexión
    st.title("🌱 Gestor de Medios de Cultivo In Vitro")

    try:
        conn = get_db_connection()
        st.sidebar.caption("Conexión a BD: OK")
        conn.close() 
    except Exception:
        # El error ya se maneja en get_db_connection con st.stop(), pero por si acaso.
        pass

    # 3. Opciones Globales
    nombres_especies_existentes = obtener_nombres_especies()
    nombres_fases_existentes = obtener_nombres_fases()

    # --- CONFIGURACIÓN DE SELECTBOXES ---

    # 1. Especie
    opciones_especie_select = ["Nueva Especie"] + sorted(list(set(nombres_especies_existentes)))

    if nombres_especies_existentes:
        opciones_especie_select = ["-- Seleccionar Especie --"] + opciones_especie_select
        default_index_especie = 0
    else:
        default_index_especie = 0

    # 2. Fase
    opciones_fase = ["-- Seleccionar Fase --", "Nueva Fase"] + sorted(list(set(nombres_fases_existentes)))
    if nombres_fases_existentes:
        default_index_fase = 0
    else:
        default_index_fase = 1


    # 4. TABS
    tabs_list = ["➕ Registrar Ingrediente", "📋 Catálogo / Edición", "🧪 Medios de Cultivo por Especie"]
    if st.session_state.is_admin:
        tabs_list.append("🛠️ Admin Usuarios")
        
    tab_objects = st.tabs(tabs_list)

    tab1 = tab_objects[0]
    tab2 = tab_objects[1]
    tab3 = tab_objects[2]
    # Se añade la comprobación para evitar IndexError si no es admin
    tab4 = tab_objects[3] if st.session_state.is_admin else None 

    # ----------------- TAB 1: REGISTRAR INGREDIENTE -----------------
    with tab1:
        st.subheader("➕ Registrar Nuevo Ingrediente por Especie/Fase")
        
        with st.form(key="form_registrar_medio"):
            
            # --- 1. INPUT ESPECIE ---
            especie_seleccionada = st.selectbox(
                "1. Especie de Planta:", 
                options=opciones_especie_select,
                index=default_index_especie,
                key="select_especie"
            )

            especie = None
            is_new_especie = especie_seleccionada == "Nueva Especie" or (not nombres_especies_existentes and especie_seleccionada != "-- Seleccionar Especie --")

            if is_new_especie:
                especie_input = st.text_input("Escribe el nombre de la **Nueva Especie**:", key="nuevo_nombre_especie").strip()
                if especie_input:
                    especie = especie_input
            else:
                if especie_seleccionada != "-- Seleccionar Especie --":
                    especie = especie_seleccionada

            # --- 2. INPUT FASE DE CULTIVO ---
            fase_seleccionada = st.selectbox(
                "2. Fase de Cultivo (Medio):", 
                options=opciones_fase,
                index=default_index_fase,
                key="select_fase_cultivo"
            )

            fase_cultivo = None
            is_new_fase = fase_seleccionada == "Nueva Fase"

            if is_new_fase:
                fase_input = st.text_input("Escribe el nombre de la **Nueva Fase de Cultivo**:", key="nuevo_fase_cultivo").strip()
                if fase_input:
                    fase_cultivo = fase_input
            else:
                if fase_seleccionada != "-- Seleccionar Fase --":
                    fase_cultivo = fase_seleccionada
            
            st.markdown("---")
            
            # El resto de tus campos:
            ingrediente = st.text_input("3. Ingrediente (ej: Sacarosa)", key="input_ingrediente").strip()
            concentracion = st.number_input("4. Concentración", min_value=0.0, format="%.4f", key="input_concentracion")
            unidad = st.selectbox("5. Unidad de Medida", ["mg/L", "g/L", "mM"], key="input_unidad")

            submit_button = st.form_submit_button(label='💾 Guardar Ingrediente', type="primary", key='submit_button')

            # 3. Lógica de inserción de datos
            if submit_button:
                if especie and fase_cultivo and ingrediente and concentracion is not None:
                    insertar_medio_cultivo(especie, fase_cultivo, ingrediente, concentracion, unidad)
                    st.experimental_rerun() # Forzar rerun para actualizar selectboxes
                else:
                    st.error("Todos los campos (Especie, Fase, Ingrediente, Concentración) son obligatorios. Por favor, revisa.")

    # Inicializa una variable de estado para saber qué ID se está editando
    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None

    # ----------------- TAB 2: CATÁLOGO / EDICIÓN -----------------
    with tab2:
        st.subheader("🔍 Catálogo, Filtro y Herramientas de Edición")
        
        datos_medios = obtener_medios_cultivo()
        
        if datos_medios:
            df = pd.DataFrame(datos_medios)
            
            # --- LÓGICA DE FILTRADO POR ESPECIE ---
            nombres_especies_filtrado = obtener_nombres_especies()
            opciones_filtro_especie = ["Mostrar todos"] + nombres_especies_filtrado

            filtro_seleccionado_especie = st.selectbox(
                "Filtrar por Especie de Planta:",
                options=opciones_filtro_especie,
                index=0
            )
            
            if filtro_seleccionado_especie != "Mostrar todos":
                df_filtrado = df[df[ESPECIE_COLUMNA] == filtro_seleccionado_especie]
                st.info(f"Mostrando solo ingredientes para la especie: **{filtro_seleccionado_especie}**")
            else:
                df_filtrado = df 
                st.info("Mostrando todos los ingredientes en el catálogo.")

            # --- BOTONES DE DESCARGA ---
            if not df_filtrado.empty:
                df_descarga = df_filtrado.drop(columns=['id'])
                col_csv, col_excel = st.columns(2)
                
                with col_csv:
                    st.download_button(
                        label="⬇️ Descargar como CSV", data=convertir_a_csv(df_descarga), 
                        file_name='catalogo_invitro.csv', mime='text/csv', type="secondary"
                    )
                
                with col_excel:
                    st.download_button(
                        label="⬇️ Descargar como Excel (XLSX)", data=convertir_a_excel(df_descarga),
                        file_name='catalogo_invitro.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', type="secondary"
                    )

            st.markdown("---") 
            
            # --- LÓGICA DE EDICIÓN (MODAL) ---
            if st.session_state.edit_id is not None:
                registro_a_editar = df[df['id'] == st.session_state.edit_id].iloc[0]
                
                st.warning(f"Editando: {registro_a_editar[ESPECIE_COLUMNA]} / {registro_a_editar[FASE_COLUMNA]} - {registro_a_editar['ingrediente']}")
                
                with st.form(key="form_editar_medio", clear_on_submit=False):
                    especie_edit = st.text_input("Especie de Planta", value=registro_a_editar[ESPECIE_COLUMNA], key="edit_especie")
                    fase_cultivo_edit = st.text_input("Fase de Cultivo", value=registro_a_editar[FASE_COLUMNA], key="edit_fase_cultivo")

                    ingrediente_edit = st.text_input("Ingrediente", value=registro_a_editar['ingrediente'], key="edit_ingrediente")
                    concentracion_edit = st.number_input("Concentración", value=float(registro_a_editar['concentracion']), format="%.4f", min_value=0.0, key="edit_concentracion")
                    
                    opciones_unidad = ["mg/L", "g/L", "mM"]
                    try: unidad_index = opciones_unidad.index(registro_a_editar['unidad'])
                    except ValueError: unidad_index = 0
                    
                    unidad_edit = st.selectbox("Unidad de Medida", opciones_unidad, index=unidad_index, key="edit_unidad")

                    col_update, col_cancel = st.columns(2)

                    with col_update:
                        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                            if actualizar_medio_cultivo(st.session_state.edit_id, especie_edit, fase_cultivo_edit, ingrediente_edit, concentracion_edit, unidad_edit):
                                st.session_state.edit_id = None 
                                st.experimental_rerun()
                    
                    with col_cancel:
                        if st.form_submit_button("🚫 Cancelar"):
                            st.session_state.edit_id = None
                            st.experimental_rerun()
                st.markdown("---")

            # --- Visualización de Registros Filtrados y Botones ---
            for index, row in df_filtrado.iterrows(): 
                col1, col2, col3 = st.columns([0.7, 0.15, 0.15]) 
                
                col1.write(f"**{row[ESPECIE_COLUMNA]}** / **{row[FASE_COLUMNA]}** — {row['ingrediente']} ({row['concentracion']:.4f} {row['unidad']})")
                
                # Función auxiliar para editar
                def set_edit_mode(record_id): st.session_state.edit_id = record_id
                
                with col2:
                    st.button("✏️", key=f"edit_btn_{row['id']}", on_click=set_edit_mode, args=(row['id'],))

                with col3:
                    # Usamos un botón para eliminar. La función eliminar_medio_cultivo llama a st.experimental_rerun()
                    st.button("🗑️", key=f"delete_btn_{row['id']}", type="secondary", on_click=eliminar_medio_cultivo, args=(row['id'],))
            
            st.markdown("---")

            st.caption("Estructura de la base de datos (Referencia):")
            df_display = df_filtrado.drop(columns=['id']).rename(columns={FASE_COLUMNA: 'Fase de Cultivo', ESPECIE_COLUMNA: 'Especie'})
            st.dataframe(df_display, use_container_width=True)

        else: 
            st.info("Aún no hay medios de cultivo registrados en la base de datos.")
        
    # ----------------- TAB 3: AGRUPACIÓN -----------------
    with tab3:
        st.subheader("🧪 Composición Detallada por Especie y Fase")

        nombres_especies = obtener_nombres_especies()
        
        if not nombres_especies:
            st.info("Aún no hay especies ni medios de cultivo registrados para mostrar.")
        else:
            st.markdown(f"**Total de Especies con Medios Registrados:** **{len(nombres_especies)}**")
            st.markdown("---")
            
            datos_medios = obtener_medios_cultivo()
            if not datos_medios:
                st.info("No hay datos de ingredientes para agrupar.")
            else:
                df_completo = pd.DataFrame(datos_medios)
                
                for especie in nombres_especies:
                    st.header(f"🌿 Especie: {especie}")
                    
                    df_especie = df_completo[df_completo[ESPECIE_COLUMNA] == especie]
                    fases_especie = df_especie[FASE_COLUMNA].unique()
                    
                    for fase in fases_especie:
                        
                        with st.expander(f"🧬 Fase de Cultivo: **{fase}**"):
                            df_fase = df_especie[df_especie[FASE_COLUMNA] == fase]
                            
                            df_display_fase = df_fase[['ingrediente', 'concentracion', 'unidad']].copy()
                            df_display_fase.columns = ['Ingrediente', 'Concentración', 'Unidad']
                            df_display_fase['Concentración'] = df_display_fase['Concentración'].apply(lambda x: f"{x:.4f}")
                            
                            st.dataframe(df_display_fase, hide_index=True, use_container_width=True)

                    st.markdown("---")

    # ----------------- TAB 4: ADMIN (solo si es administrador) -----------------
    if tab4:
        with tab4:
            st.subheader("🛠️ Gestión de Usuarios (Administrador)")
            
            # --- Formulario de Registro de Nuevo Usuario ---
            st.markdown("### Registrar Nuevo Usuario")
            with st.form("form_add_user"):
                new_username = st.text_input("Nombre de Usuario", key="new_username_input").strip()
                new_password = st.text_input("Contraseña", type="password", key="new_password_input").strip()
                is_admin_check = st.checkbox("¿Es Administrador?", key="new_is_admin_check", value=False)
                
                if st.form_submit_button("Crear Usuario", type="primary"):
                    if new_username and new_password:
                        add_user_to_db(new_username, new_password, is_admin_check)
                        # Opcional: forzar rerun para ver el resultado inmediatamente
                        st.experimental_rerun()
                    else:
                        st.error("Rellena el usuario y la contraseña.")
            
            st.markdown("---")
            
            st.info("La gestión completa (edición/eliminación de usuarios existentes) se recomienda hacer directamente en tu herramienta de base de datos (Neon/pSQL) por seguridad.")

# ====================================================================
#              PUNTO DE ENTRADA DE LA APLICACIÓN
# ====================================================================

# Llama a la función de autenticación. Si el login es exitoso (retorna True),
# el código continúa y ejecuta app_ui().
if check_password():
    app_ui()
