import psycopg2
from psycopg2.extras import execute_values

# Lista de tablas proporcionada (códigos pim)
# lista_tablas = [
#     "S_BOINE_44_000562", "S_BOINE_44_000559", "S_BOINE_44_000570",
#     "S_BOINE_44_000560", "S_BOINE_44_000615", "S_BOINE_44_000568",
#     "S_BOINE_44_000566", "S_BOINE_44_000569", "S_BOINE_44_000565",
#     "S_BOINE_44_000604", "S_BOINE_44_000604_USA", "S_BOINE_44_000567",
#     "S_BOINE_44_000563", "S_BOINE_44_000648", "S_BOINE_44_000564",
#     "S_BOINE_44_000561", "S_BOINE_44_000649", "S_BOINE_44_000596",
#     "S_BOINE_44_000591", "S_BOASF_44_000614", "S_BOASF_44_000644",
#     "S_BOASFI_44_000686", "S_BOASFI_44_000740", "S_BOASFI_44_000762",
#     "S_BOASFI44_000409", "S_BOASFI44_000671", "S_BOASFI44_000721",
#     "S_BOASFI44_000726", "S_BOASFI44_000742", "S_BOASFI66_000500",
#     "S_BOASFI99_000751", "S_BOSBEF44_000339", "S_BOSBEF44_000340",
#     "S_BOSBEF44_000361", "S_BOSBEF44_000392", "SPIM_0003_CCC",
#     "SPIM_0009_ED", "SPIM_0010_FEE", "SPIM_0011_OCCD", "SPIM_5008_B4NV",
#     "SPIM_5010_ER3NV", "SPIM_5012_PASP", "SPIM_5013_IF", "SPIM_5013_IF2",
#     "SPIM_5003_LXFSB", "SPIM_5006_CXSSB", "SPIM_5007_CXTMSB",
#     "S_BOASFI_44_000774", "S_BOASFI_44_000775", "S_BOASFI_66_000364",
#     "S_BOASFI_66_000365", "S_BOASFI66_000727", "S_BOASFI66_000728",
#     "S_BOSBEF66_000474", "SPIM_0004", "SPIM_0005_CCCTG",
#     "SPIM_0006_CCCDEDC", "SPIM_0007_CCCDC", "SPIM_0008_ECMNP",
#     "SPIM_0012_CCCTC", "SPIM_5014_CCCDPDC"
# ]

# Lista de tablas proporcionada (códigos pim)
lista_tablas = ["S_BOINE_44_000563"]

# Configuración de conexiones
# ==========================================
DB_LOCAL_PARAMS = {
    "dbname": "bulkdatax",
    "user": "postgres",
    "password": "1234",
    "host": "localhost",
    "port": 5432,
}

DB_REMOTO_PARAMS = {
    "dbname": "SPIM",
    "user": "alepasante",
    "password": "D.8392025apas",
    "host": "10.0.0.9",
    "port": 5432,
}

DB_DOCKER_PARAMS = {
    "dbname": "rag_db",
    "user": "user_rag",
    "password": "pass_rag",
    "host": "localhost",
    "port": 5434,
}

# ==========================================
# Proceso de extracción y transferencia
# ==========================================
try:
    conn_local = psycopg2.connect(**DB_LOCAL_PARAMS)
    cur_local = conn_local.cursor()
    
    conn_remoto = psycopg2.connect(**DB_REMOTO_PARAMS)
    
    conn_destino = psycopg2.connect(**DB_DOCKER_PARAMS)
    cur_destino = conn_destino.cursor()
    
    for codigo_orig in lista_tablas:
        codigo = codigo_orig 
        print(f"\n--- Procesando tabla: {codigo} ---")
        cur_remoto_cursor = None
        
        try:
            # 1. Obtener la consulta desde la BD local
            cur_local.execute('SELECT "sqlcvs" FROM "cvsscheme" WHERE "codespim" = %s', (codigo_orig,))
            resultado = cur_local.fetchone()
            
            if not resultado or not resultado[0]:
                print(f"-> No se encontró consulta para el código: {codigo_orig}. Saltando...")
                continue
                
            consulta_dinamica = resultado[0].strip()
            
            # 2. Ejecutar la consulta contra la BD remota
            cur_remoto_cursor = conn_remoto.cursor(name=f"cursor_{codigo}")
            cur_remoto_cursor.execute(consulta_dinamica)
            
            batch_size = 10000
            tabla_creada = False
            
            # 3. Procesar resultados por bloques
            while True:
                rows = cur_remoto_cursor.fetchmany(batch_size)
                if not rows:
                    break
                
                if not tabla_creada:
                    # Obtenemos las columnas y sus tipos dinámicamente
                    description = cur_remoto_cursor.description
                    type_oids = [desc[1] for desc in description]
                    
                    # Mapeo de OIDs a nombres de tipos legibles en la BD remota
                    cur_temp = conn_remoto.cursor()
                    cur_temp.execute("SELECT oid, oid::regtype::text FROM pg_type WHERE oid = ANY(%s)", (type_oids,))
                    oid_to_type = dict(cur_temp.fetchall())
                    cur_temp.close()
                    
                    col_defs = []
                    columnas_vistas = set()  # Para rastrear duplicados en esta tabla
                    
                    for desc in description:
                        col_name = desc[0] 
                        col_type_oid = desc[1]
                        col_type_name = oid_to_type.get(col_type_oid, "TEXT").upper()
                        
                        # --- CONTROL DE DUPLICADOS ---
                        # Si la columna ya existe, buscamos un nombre disponible agregando un sufijo
                        if col_name in columnas_vistas:
                            contador = 1
                            nuevo_nombre = f"{col_name}_{contador}"
                            while nuevo_nombre in columnas_vistas:
                                contador += 1
                                nuevo_nombre = f"{col_name}_{contador}"
                            print(f"   [Aviso] Columna duplicada detectada. Renombrando '{col_name}' a '{nuevo_nombre}'")
                            col_name = nuevo_nombre
                        
                        columnas_vistas.add(col_name)
                        # ------------------------------
                        
                        col_defs.append(f'"{col_name}" {col_type_name}')
                    
                    # Creamos la tabla en el contenedor de Docker
                    crear_tabla_query = f'CREATE TABLE IF NOT EXISTS public."{codigo}" (' + ", ".join(col_defs) + ");"
                    cur_destino.execute(crear_tabla_query)
                    conn_destino.commit()
                    tabla_creada = True
                
                # Inserción masiva
                insert_query = f'INSERT INTO public."{codigo}" VALUES %s'
                execute_values(cur_destino, insert_query, rows)
                conn_destino.commit()
                
            cur_remoto_cursor.close()
            print(f"-> Tabla {codigo} insertada con éxito.")
            
        except Exception as e:
            print(f"-> Error procesando la tabla {codigo}: {e}")
            
            try:
                conn_remoto.rollback()
                conn_destino.rollback()
            except Exception:
                pass
                
            if cur_remoto_cursor and not cur_remoto_cursor.closed:
                try:
                    cur_remoto_cursor.close()
                except Exception:
                    pass
                    
    # Cierre de conexiones al finalizar todo
    cur_local.close()
    conn_local.close()
    conn_remoto.close()
    cur_destino.close()
    conn_destino.close()
    print("\n¡Proceso terminado exitosamente!")
    
except Exception as e:
    print(f"Error general de conexión: {e}")