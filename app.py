if st.form_submit_button("Crear Administrador Inicial", type="primary"):
    if add_user_to_db(st.session_state["admin_user_setup"], st.session_state["admin_password_setup"], is_admin=True):
        
        # 1. Mensaje de éxito visible
        st.success("Administrador creado con éxito. ¡Reiniciando la aplicación para iniciar sesión!")
        
        # 2. Limpieza de caché y forzar RERUN
        # Esto rompe el bucle de "admin no encontrado"
        st.cache_data.clear()
        st.cache_resource.clear()
        
        # Usamos st.stop() para detener la ejecución y luego pedimos a Streamlit que reinicie.
        # Es la forma más agresiva y segura de garantizar que se lea la DB de nuevo.
        st.experimental_rerun()
