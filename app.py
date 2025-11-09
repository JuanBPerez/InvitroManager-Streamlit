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
