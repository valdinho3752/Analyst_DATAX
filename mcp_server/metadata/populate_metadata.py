import asyncio
import json
import os
from sqlalchemy import text
from db_connection import Session, SessionBulk

# Rutas de archivos (usando rutas relativas ya que el script estará en mcp_server/metadata)
INPUT_JSON = "metadata_structure2.json"
OUTPUT_JSON = "metadata_2_filled.json"

async def populate_metadata():
    try:
        print("-> Iniciando proceso de población de metadata...")
        
        # 1. Obtener todas las tablas de Docker (Session usa factory_rag)
        tablas_docker = []
        async with Session() as session_docker:
            result = await session_docker.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            tablas_docker = [row[0] for row in result.fetchall()]
        
        print(f"-> Se encontraron {len(tablas_docker)} tablas en Docker.")
        
        # 2. Cargar el JSON original
        if not os.path.exists(INPUT_JSON):
            print(f"Error: No se encontró el archivo {INPUT_JSON} en el directorio actual.")
            return
            
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        updated_count = 0
        
        # 3. Iterar tablas y buscar información en el catálogo local (SessionBulk usa factory_bulk)
        async with SessionBulk() as session_local:
            for tabla in tablas_docker:
                # Buscamos en el catálogo usando el nombre de la tabla (codigointerno)
                query = text("""
                    SELECT "internalcode" AS "codigointerno", 
                    "name" As "nombrebd", 
                    "source" AS "fuente", 
                    "acronym" AS "sigla", 
                    "originallanguage" AS "idiomaoriginal", 
                    "longdescription" AS "descripcionlarga", 
                    "datafrequency" AS "frecuenciadatos", 
                    "topics" 
                    FROM public.catalogproduc
                    WHERE "internalcode" = :tabla
                """)
                
                result_local = await session_local.execute(query, {"tabla": tabla})
                row = result_local.fetchone()
                
                if row:
                    cod_interno, nombrebd, fuente, sigla, idioma, desc_larga, frecuencia, topics = row
                    
                    topics_list = [t.strip() for t in topics.split(';')] if topics else []

                    tematica_str = ""
                    if len(topics_list) > 0:
                        query_topic = text("""
                            SELECT "temaprincipal", "subtema" FROM "topic" 
                            WHERE "codigosubt" = ANY(:topics)
                            GROUP BY "temaprincipal", "subtema";
                        """)
                        # Usamos tuple(topics_list) para asegurar compatibilidad con la cláusula IN
                        result_topic = await session_local.execute(query_topic, {"topics": tuple(topics_list)})
                        row_topic = result_topic.fetchall()
                        
                        # Formatear: "temaprincipal;subtema / temaprincipal;subtema"
                        tematica_str = " / ".join([f"{r[0]};{r[1]}" for r in row_topic])

                    # Identificamos la clave en el JSON
                    key = tabla
                    
                    if key in metadata:
                        print(f"   - Actualizando metadata para: {key}")
                        
                        # Tematica -> tematica_str
                        metadata[key]["Tematica"] = tematica_str
                        
                        # Nombre dataset -> nombrebd
                        metadata[key]["Nombre dataset"] = nombrebd if nombrebd else ""
                        
                        # Fuente -> fuente + (sigla)
                        if fuente and sigla:
                            metadata[key]["Fuente"] = f"{fuente} ({sigla})"
                        elif fuente:
                            metadata[key]["Fuente"] = fuente
                        else:
                            metadata[key]["Fuente"] = sigla if sigla else ""
                        
                        # Idioma -> idiomaoriginal
                        metadata[key]["Idioma"] = idioma if idioma else ""
                        
                        # Descripcion tabla -> descripcionlarga
                        metadata[key]["Descripcion tabla"] = desc_larga if desc_larga else ""
                        
                        # Granularidad -> frecuenciadatos
                        metadata[key]["Granularidad"] = frecuencia if frecuencia else ""
                        
                        updated_count += 1
                    else:
                        print(f"   [!] Tabla {tabla} encontrada en catálogo pero no en el archivo JSON.")
                else:
                    print(f"   [?] Tabla {tabla} no encontrada en public.cubecatalog.")
                
        # 4. Guardar el nuevo JSON
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
            
        print(f"\n¡Proceso terminado! Se actualizaron {updated_count} entradas.")
        print(f"Archivo guardado en: {os.path.abspath(OUTPUT_JSON)}")
        
    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    asyncio.run(populate_metadata())
