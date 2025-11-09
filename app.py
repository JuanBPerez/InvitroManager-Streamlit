import streamlit as st
import psycopg2 
import pandas as pd
from psycopg2.extras import RealDictCursor 

# --- Función para obtener la conexión a la base de datos (CORREGIDA) ---
# Se elimina @st.cache_resource para asegurar que cada función obtenga una conexión
# nueva y no interfiera con otras cerrando la conexión antes de tiempo.
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
            # SOLUCIÓN SSL: Neon lo requiere
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
def insertar_medio_cultivo(nombre, ingrediente, concentracion, unidad):
    conn = None 
    cur = None
    try:
        conn = get_db_connection() # Obtiene una conexión NUEVA
        cur = conn.cursor()
        
        sql = """
        INSERT INTO medios_cultivo (nombre_medio, ingrediente, concentracion, unidad) 
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (nombre, ingrediente, float(concentracion), unidad))
        
        conn.commit()
        st.success(f"¡Ingrediente '{ingrediente}' guardado para el medio '{nombre}'!")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error al guardar en la base de datos: {e}")
        return False
        
    finally:
        if cur:
            cur.close()
        # Se cierra la conexión específica de esta función
        if conn:
            conn.close() 

# --- Función para seleccionar y obtener todos los registros ---
def obtener_medios_cultivo():
    conn = None
    cur = None
    try:
        conn = get_db_connection() # Obtiene una conexión NUEVA
        # Usamos RealDictCursor para obtener los resultados como diccionarios.
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        sql = "SELECT id, nombre_medio, ingrediente, concentracion, unidad FROM medios_cultivo ORDER BY nombre_medio, ingrediente;"
        cur.execute(sql)
        
        registros = cur.fetchall()
        return registros
        
    except psycopg2.Error as e:
        st.error(f"Error al leer la base de datos: {e}")
        return []
        
    finally:
        if cur:
            cur.close()
        # Se cierra la conexión específica de esta función
        if conn:
            conn.close()

# --- Función para eliminar un registro por ID ---
def eliminar_medio_cultivo(registro_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Consulta SQL para eliminar la fila específica
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

# --- Aquí están get_db_connection, insertar_medio_cultivo, obtener_medios_cultivo...

# --- Función para actualizar un registro por ID (Debe empezar en la línea 121) ---
def actualizar_medio_cultivo(registro_id, nombre, ingrediente, concentracion, unidad):
    conn = None
    cur = None
    try: # <--- ESTA LÍNEA DEBE TENER INDENTACIÓN
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Consulta SQL para actualizar los campos basándose en el ID
        sql = """
        UPDATE medios_cultivo 
        SET nombre_medio = %s, ingrediente = %s, concentracion = %s, unidad = %s
        WHERE id = %s;
        """
        # Ejecutar con los nuevos valores y el ID al final
        cur.execute(sql, (nombre, ingrediente, float(concentracion), unidad, registro_id))
        
        conn.commit()
        st.success(f"Registro ID {registro_id} actualizado exitosamente a: {nombre} - {ingrediente}")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error al actualizar la base de datos: {e}")
        return False
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
# La siguiente línea (st.title) debe ir SIN indentación.

# --- AQUÍ COMIENZA LA INTERFAZ DE USUARIO ---
st.title("🌱 InvitroManager...")
# ...

# --- Interfaz de Usuario de Streamlit ---

st.title("🌱 InvitroManager: Gestión de Medios de Cultivo")

# Lógica de verificación de conexión (solo para mostrar el mensaje de éxito)
try:
    conn = get_db_connection()
    st.sidebar.success("✅ Conexión a la base de datos establecida.")
    conn.close() # Cierra la conexión de prueba inmediatamente
except Exception:
    # Si get_db_connection falla, ya habrá emitido un error, no es necesario hacer nada más aquí
    pass


# TABS
tab1, tab2 = st.tabs(["➕ Registrar Ingrediente", "📋 Ver Fórmulas Guardadas"])

with tab1:
    with st.form("form_nuevo_medio"):
        st.subheader("Registrar Ingrediente de Fórmula")

        # Campos de Entrada
        nombre_medio = st.text_input("Nombre de la Fórmula (ej: MS Estándar)", max_chars=100, key="nombre_input")
        ingrediente = st.text_input("Ingrediente (ej: Sacarosa)", max_chars=100, key="ingrediente_input")
        concentracion = st.number_input("Concentración (valor numérico)", min_value=0.0, format="%.4f", key="concentracion_input")
        unidad = st.selectbox("Unidad de Medida", ["mg/L", "g/L", "mM"], key="unidad_input")

        submitted = st.form_submit_button("Guardar Ingrediente en la DB")
        
        if submitted:
            if nombre_medio and ingrediente:
                insertar_medio_cultivo(nombre_medio, ingrediente, concentracion, unidad)
            else:
                st.warning("El Nombre de la Fórmula y el Ingrediente son obligatorios.")

# Inicializa una variable de estado para saber qué ID se está editando
if 'edit_id' not in st.session_state:
    st.session_state.edit_id = None

with tab2:
    st.subheader("Fórmulas Registradas en la Base de Datos")
    
    datos_medios = obtener_medios_cultivo()
    
    if datos_medios:
        df = pd.DataFrame(datos_medios)
        
        # --- Lógica de Edición ---
        if st.session_state.edit_id is not None:
            # Buscar el registro que se va a editar
            registro_a_editar = df[df['id'] == st.session_state.edit_id].iloc[0]
            
            st.warning(f"Editando: {registro_a_editar['nombre_medio']} - {registro_a_editar['ingrediente']}")
            
            with st.form(key="form_editar_medio", clear_on_submit=False):
                # Campos precargados con los valores actuales del registro
                nombre_medio_edit = st.text_input("Nombre de la Fórmula", value=registro_a_editar['nombre_medio'], key="edit_nombre")
                ingrediente_edit = st.text_input("Ingrediente", value=registro_a_editar['ingrediente'], key="edit_ingrediente")
                concentracion_edit = st.number_input("Concentración", value=float(registro_a_editar['concentracion']), format="%.4f", min_value=0.0, key="edit_concentracion")
                unidad_edit = st.selectbox("Unidad de Medida", ["mg/L", "g/L", "mM"], index=["mg/L", "g/L", "mM"].index(registro_a_editar['unidad']), key="edit_unidad")

                col_update, col_cancel = st.columns(2)

                # Botón de Guardar
                with col_update:
                    if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                        actualizar_medio_cultivo(
                            st.session_state.edit_id, 
                            nombre_medio_edit, 
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


        # --- Visualización de Registros y Botones ---
        for index, row in df.iterrows():
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15]) # Espacio para datos, Editar, Eliminar
            
            # Columna 1: Información del registro
            col1.write(
                f"**{row['nombre_medio']}** — {row['ingrediente']} "
                f"({row['concentracion']:.4f} {row['unidad']})"
            )
            
            # Columna 2: Botón de Editar
            with col2:
                # Función auxiliar para manejar el clic en editar
                def set_edit_mode(record_id):
                    st.session_state.edit_id = record_id

                st.button(
                    "✏️ Editar", 
                    key=f"edit_btn_{row['id']}", 
                    on_click=set_edit_mode, 
                    args=(row['id'],)
                )

            # Columna 3: Botón de Eliminar (reutiliza la lógica anterior)
            with col3:
                # El key del formulario y del botón es crucial
                with st.form(key=f"delete_form_{row['id']}", clear_on_submit=False):
                    st.form_submit_button(
                        "🗑️ Eliminar", 
                        type="primary", 
                        on_click=eliminar_medio_cultivo, 
                        args=(row['id'],) 
                    )

        st.caption("Estructura de la base de datos (Referencia):")
        st.dataframe(df.drop(columns=['id']), use_container_width=True)

    else:
        st.info("Aún no hay medios de cultivo registrados en la base de datos.")