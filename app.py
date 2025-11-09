with tab3:
    st.subheader("🧪 Composición Detallada de Medios de Cultivo")

    nombres_formulas = obtener_nombres_formulas()

    if not nombres_formulas:
        st.info("Aún no hay fórmulas registradas para mostrar.")
    else:
        st.markdown(f"**Total de Fórmulas Únicas Registradas:** **{len(nombres_formulas)}**")
        st.markdown("---")
        
        # 1. Iterar sobre cada nombre de fórmula único
        for nombre in nombres_formulas:
            
            # 2. Obtener todos los ingredientes para esta fórmula específica
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                # Consulta SQL para obtener solo los ingredientes de la fórmula actual
                sql = "SELECT ingrediente, concentracion, unidad FROM medios_cultivo WHERE nombre_medio = %s ORDER BY ingrediente;"
                cur.execute(sql, (nombre,))
                ingredientes = cur.fetchall()
            
                # 3. Presentar los datos
                if ingredientes:
                    
                    # Título de la Fórmula
                    st.header(f"🧬 {nombre}")
                    
                    # Convertir a DataFrame y formatear la concentración
                    df_formula = pd.DataFrame(ingredientes, columns=['Ingrediente', 'Concentración', 'Unidad'])
                    
                    # Formatear la concentración para que se vea más limpio (opcional)
                    df_formula['Concentración'] = df_formula['Concentración'].apply(lambda x: f"{x:.4f}")
                    
                    # Mostrar la tabla
                    st.dataframe(df_formula, hide_index=True, use_container_width=True)
                    st.markdown("---")
                    
            except psycopg2.Error as e:
                st.error(f"Error al cargar la fórmula {nombre}: {e}")
                
            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()
