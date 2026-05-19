import asyncio
import logging
import os
import json
from openai import OpenAI
from fastmcp import FastMCP
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from neo4j import GraphDatabase, AsyncGraphDatabase

# Cargar variables de entorno del .env de la raíz
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ================= CONFIGURACIÓN =================
# Debe coincidir exactamente con tu script de ingesta (ingest_openai.py)
COLLECTION_NAME = "rag_metadata_demo_openia"
VECTOR_NAME = "openai-embedding"
MODEL_NAME = "text-embedding-3-small"

# URL de Qdrant (ajustada para el entorno local o Docker)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# Neo4j Configuración
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# --- Inicialización de OpenAI ---
client_openai = OpenAI()

# --- Inicialización de Qdrant ---
qdrant_client = AsyncQdrantClient(url=QDRANT_URL)

# --- Inicialización de Neo4j ---
neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

mcp = FastMCP("Rag Agent MCP Server 🧠")

def get_single_embedding(text: str):
    """Helper para obtener un solo vector desde OpenAI"""
    response = client_openai.embeddings.create(
        input=[text],
        model=MODEL_NAME
    )
    return response.data[0].embedding

@mcp.tool()
async def get_table_schema(table_name: str) -> dict:
    """
    Busca en Qdrant el esquema técnico (payload) de una tabla específica.
    """
    print(f"\n[MCP TOOL get_table_schema] IN: table_name='{table_name}'\n", flush=True)
    logger.info(f"--- 🔍 Buscando esquema para la tabla: {table_name} ---")
    
    try:
        # El método scroll devuelve una tupla (List[Record], Optional[Offset])
        records, next_page_offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tipo",
                        match=models.MatchValue(value='tabla_maestra')
                    ),
                    models.FieldCondition(
                        key="nombre_tabla",
                        match=models.MatchValue(value=table_name)
                    )
                ],
                must_not=[
                    models.FieldCondition(
                        key="tipo",
                        match=models.MatchValue(value='dimension')
                    ),
                    models.FieldCondition(
                        key="tipo",
                        match=models.MatchValue(value='hecho')
                    )
                ]
            ),
            limit=1
        )

        if records:
            logger.info(f"✅ Esquema encontrado para la tabla '{table_name}'")
            schema = records[0].payload
            
            # --- OPTIMIZACIÓN ---
            # Eliminamos las inmensas listas de miembros de las dimensiones
            if "Dimensiones" in schema:
                for dim_data in schema["Dimensiones"].values():
                    dim_data.pop("Miembros", None)
                    dim_data.pop("Valores ejemplo", None)
                    
            print(f"\n[MCP TOOL get_table_schema] OUT: Esquema encontrado (truncado primeros 200 chars): {str(schema)[:200]}...\n", flush=True)
            return schema
        else:
            logger.warning(f"⚠️ No se encontró la tabla '{table_name}'")
            print(f"\n[MCP TOOL get_table_schema] OUT: {{'error': 'Tabla no encontrada'}}\n", flush=True)
            return {"error": "Tabla no encontrada"}

    except Exception as e:
        logger.error(f"❌ Error al consultar Qdrant: {e}")
        print(f"\n[MCP TOOL get_table_schema] ERROR: {e}\n", flush=True)
        return {"error": str(e)}


@mcp.tool()
async def search_relevant_points(queries: list[str]) -> dict:
    """
    Busca puntos relevantes basadas en una lista de palabras/frases clave.
    Realiza una búsqueda estratificada (Tablas, Dimensiones y Miembros) para garantizar diversidad.
    Devuelve un resumen consolidado por tabla para optimizar el contexto y tokens.
    """
    print(f"\n[MCP TOOL search_relevant_points] IN: queries={queries}\n", flush=True)
    logger.info(f"--- 🧠 Búsqueda Estratificada para {len(queries)} consultas ---")

    # Mecanismo de seguridad de Tokens
    max_queries = 8
    if len(queries) > max_queries:
        queries = queries[:max_queries]

    try:
        # 1. Vectorizar las consultas en lote
        response = client_openai.embeddings.create(input=queries, model=MODEL_NAME)
        query_vectors = [data.embedding for data in response.data]

        # Estructura para consolidar por tabla
        # { "nombre_tabla": { "metadata": {}, "columnas": set(), "miembros": set(), "puntuacion": float } }
        consolidated = {}

        def add_to_consolidated(table_name, tipo, data, score):
            if not table_name: return
            if table_name not in consolidated:
                consolidated[table_name] = {
                    "metadata": {},
                    "columnas_relevantes": set(),
                    "pistas_de_miembros": set(),
                    "score_max": 0.0,
                    "hit_count": 0
                }
            
            consolidated[table_name]["score_max"] = max(consolidated[table_name]["score_max"], score)
            consolidated[table_name]["hit_count"] += 1
            
            if tipo == "tabla_maestra":
                # Guardar metadata básica de la tabla
                consolidated[table_name]["metadata"] = {
                    "nombre": data.get("nombre_tabla"),
                    "descripcion": data.get("Descripcion tabla"),
                    "tematica": data.get("Tematica", data.get("tematica")),
                    "fuente": data.get("Fuente", data.get("fuente"))
                }
            elif tipo == "dimension":
                col = data.get("nombre_columna")
                desc = data.get("descripcion_funcional", "")
                if col:
                    consolidated[table_name]["columnas_relevantes"].add(f"{col} ({desc})")
            elif tipo == "miembro_dimension":
                val = data.get("valor_miembro")
                if val:
                    consolidated[table_name]["pistas_de_miembros"].add(val)

        # 2. Búsqueda por estratos (PARALELIZADA)
        async def fetch_strata(q_vector):
            # Estrato A: Tablas Maestras
            task_tables = qdrant_client.query_points(
                collection_name=COLLECTION_NAME, query=q_vector, using=VECTOR_NAME, limit=15,
                query_filter=models.Filter(must=[models.FieldCondition(key="tipo", match=models.MatchValue(value="tabla_maestra"))])
            )
            
            # Estrato B: Dimensiones AGRUPADAS
            task_dims = qdrant_client.query_points_groups(
                collection_name=COLLECTION_NAME,
                query=q_vector,
                group_by="tabla_origen",
                limit=15,
                group_size=5,
                using=VECTOR_NAME,
                query_filter=models.Filter(must=[models.FieldCondition(key="tipo", match=models.MatchValue(value="dimension"))])
            )
            
            # Estrato C: Miembros AGRUPADOS
            task_members = qdrant_client.query_points_groups(
                collection_name=COLLECTION_NAME,
                query=q_vector,
                group_by="tabla_origen",
                limit=30,
                group_size=30,
                using=VECTOR_NAME,
                query_filter=models.Filter(must=[models.FieldCondition(key="tipo", match=models.MatchValue(value="miembro_dimension"))])
            )
            
            return await asyncio.gather(task_tables, task_dims, task_members)

        # Lanzar todas las búsquedas en paralelo para todos los vectores
        all_search_tasks = [fetch_strata(v) for v in query_vectors]
        all_results = await asyncio.gather(*all_search_tasks)

        # Procesar los resultados consolidados
        for res_tables, res_dims_groups, res_members_groups in all_results:
            # Procesar Tablas
            for p in res_tables.points:
                add_to_consolidated(p.payload.get("nombre_tabla"), "tabla_maestra", p.payload, p.score)

            # Procesar Dimensiones
            for group in res_dims_groups.groups:
                t_name = group.id
                for hit in group.hits:
                    add_to_consolidated(t_name, "dimension", hit.payload, hit.score)

            # Procesar Miembros
            for group in res_members_groups.groups:
                t_name = group.id
                for hit in group.hits:
                    add_to_consolidated(t_name, "miembro_dimension", hit.payload, hit.score)

        # Recuperar metadata faltante para las tablas que solo coincidieron por dimensiones/miembros
        tablas_sin_metadata = [t_name for t_name, info in consolidated.items() if not info["metadata"]]
        if tablas_sin_metadata:
            try:
                records_faltantes, _ = await qdrant_client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="tipo",
                                match=models.MatchValue(value="tabla_maestra")
                            ),
                            models.FieldCondition(
                                key="nombre_tabla",
                                match=models.MatchAny(any=tablas_sin_metadata)
                            )
                        ]
                    ),
                    limit=len(tablas_sin_metadata)
                )
                for p in records_faltantes:
                    t_name = p.payload.get("nombre_tabla")
                    if t_name in consolidated:
                        consolidated[t_name]["metadata"] = {
                            "nombre": t_name,
                            "descripcion": p.payload.get("Descripcion tabla"),
                            "tematica": p.payload.get("Tematica", p.payload.get("tematica")),
                            "fuente": p.payload.get("Fuente", p.payload.get("fuente"))
                        }
            except Exception as e:
                logger.warning(f"⚠️ No se pudo recuperar metadata faltante: {e}")

        # 3. Formatear para salida final (Convertir sets a listas)
        final_results = []
        for t_name, info in consolidated.items():
            # Si aún no encontramos metadata de tabla maestra, al menos ponemos el nombre
            if not info["metadata"]:
                info["metadata"] = {"nombre": t_name, "descripcion": "Sin descripción detallada"}
            
            # Score Final: score máximo + bono de 0.05 por cada coincidencia adicional
            score_final = info["score_max"] + (max(0, info["hit_count"] - 1) * 0.05)
            
            final_results.append({
                "tabla": info["metadata"],
                "columnas_halladas": list(info["columnas_relevantes"]),
                "pistas_miembros": list(info["pistas_de_miembros"]),
                "relevancia_score": round(score_final, 3)
            })

        # Ordenar por score de relevancia
        final_results.sort(key=lambda x: x["relevancia_score"], reverse=True)
        
        # Limitar a las 10 tablas más prometedoras para ahorrar tokens (Aumentado de 6 a 10)
        final_results = final_results[:10]

        logger.info(f"✅ Búsqueda finalizada. Consolidado en {len(final_results)} tablas.")
        print(f"\n[MCP TOOL search_relevant_points] OUT: {len(final_results)} tablas consolidadas:\n", flush=True)
        try:
            print(json.dumps(final_results, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            print(final_results, flush=True)
        print("\n", flush=True)

        return {"tablas_encontradas": final_results}

    except Exception as e:
        logger.error(f"❌ Error en búsqueda estratificada: {e}")
        print(f"\n[MCP TOOL search_relevant_points] ERROR: {e}\n", flush=True)
        return {"error": str(e)}

    except Exception as e:
        logger.error(f"❌ Error en búsqueda semántica (batch): {e}")
        print(f"\n[MCP TOOL search_relevant_points] ERROR: {e}\n", flush=True)
        return {"error": str(e)}


@mcp.tool()
async def search_exact_members(query: str, table_name: str, limit: int = 25) -> list[str]:
    """
    Busca de forma semántica los valores/miembros categóricos exactos 
    para utilizar en una cláusula WHERE, basados en lenguaje natural.
    """
    print(f"\n[MCP TOOL search_exact_members] IN: query='{query}', table_name='{table_name}', limit={limit}\n", flush=True)
    logger.info(f"--- 🔍 Buscando miembros en la tabla '{table_name}' para: '{query}' ---")
    try:
        query_vector = get_single_embedding(query)
        res = await qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            using=VECTOR_NAME,
            limit=limit,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tipo",
                        match=models.MatchValue(value="miembro_dimension")
                    ),
                    models.FieldCondition(
                        key="tabla_origen",
                        match=models.MatchValue(value=table_name)
                    )
                ]
            )
        )
        points = res.points
        
        results = []
        for p in points:
            columna = p.payload.get("nombre_columna", "Desconocida")
            valor = p.payload.get("valor_miembro", "Desconocido")
            results.append(f"Columna '{columna}': Valor literal exacto '{valor}' (Score de similitud: {p.score:.3f})")
            
        logger.info(f"✅ Encontrados {len(results)} miembros sugeridos")
        print(f"\n[MCP TOOL search_exact_members] OUT: {len(results)} miembros sugeridos:\n", flush=True)
        try:
            print(json.dumps(results, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            print(results, flush=True)
        print("\n", flush=True)
        return results

    except Exception as e:
        logger.error(f"❌ Error en búsqueda de miembros exactos: {e}")
        print(f"\n[MCP TOOL search_exact_members] ERROR: {e}\n", flush=True)
        return [f"Error: {str(e)}"]


@mcp.tool()
async def validate_table_semantics(table_name: str, keywords: list[str]) -> dict:
    """
    Valida semánticamente si una tabla contiene los conceptos clave solicitados
    consultando el conocimiento estructurado en el Grafo (Neo4j).
    """
    print(f"\n[MCP TOOL validate_table_semantics] IN: table_name='{table_name}', keywords={keywords}\n", flush=True)
    logger.info(f"--- 🧠 Validando tabla '{table_name}' en el Grafo para {len(keywords)} keywords ---")
    
    if not keywords:
        print(f"\n[MCP TOOL validate_table_semantics] OUT: {{'error': 'Se requiere al menos un keyword para validar'}}\n", flush=True)
        return {"error": "Se requiere al menos un keyword para validar"}

    query = """
    UNWIND $keywords AS keyword
    CALL {
        WITH keyword
        MATCH (node)-[:BELONGS_TO*1..2]->(t:Table {name: $table_name})
        WHERE (ANY(label IN labels(node) WHERE label IN ['Member', 'Dimension', 'Fact']))
          AND node.name =~ ('(?i).*' + keyword + '.*')
        
        WITH keyword, node,
             CASE WHEN toLower(node.name) = toLower(keyword) THEN 0 ELSE 1 END AS exactMatch,
             size(node.name) AS nameLen
        ORDER BY exactMatch ASC, nameLen ASC
        LIMIT 15
        
        OPTIONAL MATCH (node:Member)-[:BELONGS_TO]->(parentDim:Dimension)
        OPTIONAL MATCH path = (node)-[:CHILD_OF*]->(root)
        WHERE NOT (root)-[:CHILD_OF]->()
        
        OPTIONAL MATCH (child:Member)-[:CHILD_OF*1..3]->(node)
        OPTIONAL MATCH (child)-[:BELONGS_TO]->(childDim:Dimension)
        
        RETURN keyword AS Busqueda, 
               COALESCE(parentDim.name, labels(node)[0]) AS Dimension, 
               node.name AS Coincidencia,
               path,
               parentDim,
               node,
               collect(DISTINCT childDim.name) AS childDimensions,
               collect(DISTINCT child.name)[0..20] AS sampleChildren
    }
    RETURN Busqueda, Dimension, Coincidencia,
           CASE WHEN path IS NOT NULL THEN
              reverse([n IN nodes(path) | 
                 [(n)-[:BELONGS_TO]->(d:Dimension) | "[" + d.name + "] -> '" + n.name + "'"][0]
              ])
           ELSE
              CASE WHEN parentDim IS NOT NULL THEN
                 ["[" + parentDim.name + "] -> '" + node.name + "'"]
              ELSE [] END
           END AS Lineage,
           childDimensions AS DimensionesHijas,
           sampleChildren AS MiembrosHijos
    """
    
    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                query,
                keywords=keywords,
                table_name=table_name
            )
            records = await result.data()
        
        resultado = {
            "tabla_analizada": table_name,
            "conceptos_solicitados": len(keywords),
            "hallazgos": {}
        }
        
        # Agrupar hallazgos
        for r in records:
            busqueda = r["Busqueda"]
            dimension = r["Dimension"]
            miembro = r["Coincidencia"]
            linaje = r["Lineage"]
            
            if busqueda not in resultado["hallazgos"]:
                resultado["hallazgos"][busqueda] = []
                
            ruta_sql_parts = []
            for item in linaje:
                try:
                    dim_part, val_part = item.split("] -> '")
                    dim = dim_part[1:]
                    val = val_part[:-1]
                    ruta_sql_parts.append(f"\"{dim}\" = '{val}'")
                except:
                    pass
            ruta_sql = " AND ".join(ruta_sql_parts)
                
            hallazgo = {
                "dimension": dimension,
                "coincidencia": miembro,
                "linaje": linaje,
                "ruta_sql_sugerida": ruta_sql
            }
            
            if r.get("DimensionesHijas"):
                hijas_limpias = [d for d in r["DimensionesHijas"] if d]
                if hijas_limpias:
                    hallazgo["dimensiones_de_desglose"] = hijas_limpias
                    
            if r.get("MiembrosHijos"):
                miembros_limpios = [m for m in r["MiembrosHijos"] if m]
                if miembros_limpios:
                    hallazgo["ejemplos_subniveles"] = miembros_limpios
                    
            resultado["hallazgos"][busqueda].append(hallazgo)
            
        resultado["conceptos_encontrados"] = len(resultado["hallazgos"])
        
        faltantes = [k for k in keywords if k not in resultado["hallazgos"]]
        resultado["faltantes"] = faltantes
        
        if faltantes:
            resultado["estatus"] = "INCUMPLE_FILTROS"
            resultado["razon"] = f"Faltan {len(faltantes)} conceptos conceptuales en la estructura de esta tabla."
        else:
            resultado["estatus"] = "VALIDACION_EXITOSA"
            
        logger.info(f"✅ Validación Completada. Status: {resultado['estatus']}")
        print(f"\n[MCP TOOL validate_table_semantics] OUT: {resultado}\n", flush=True)
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Error al consultar Neo4j: {e}")
        print(f"\n[MCP TOOL validate_table_semantics] ERROR: {e}\n", flush=True)
        return {"error": str(e)}


if __name__ == "__main__":
    from ingest_openai import main as ingest_main
    from ingest_neo4j import main as ingest_neo4j_main
    
    # Verificación Qdrant
    async def verify_qdrant():
        try:
            collection_info = await qdrant_client.get_collection(COLLECTION_NAME)
            if collection_info.points_count == 0:
                logger.info(f"⏳ Colección '{COLLECTION_NAME}' vacía en Qdrant. Iniciando ingesta...")
                ingest_main()
            else:
                logger.info(f"✅ Colección '{COLLECTION_NAME}' encontrada con {collection_info.points_count} puntos, saltando ingesta.")
        except Exception:
            logger.info(f"⏳ Colección '{COLLECTION_NAME}' no existe en Qdrant. Iniciando ingesta...")
            try:
                ingest_main()
            except Exception as e:
                logger.error(f"❌ Error durante la ingesta en Qdrant: {e}")

    # Verificación Neo4j
    async def verify_neo4j():
        try:
            async with neo4j_driver.session(database="neo4j") as session:
                result = await session.run("MATCH (t:Table) RETURN count(t) AS count")
                record = await result.single()
                count = record["count"]
                if count == 0:
                    logger.info("⏳ Grafo Neo4j vacío. Iniciando ingesta en Neo4j por primera vez...")
                    ingest_neo4j_main()
                else:
                    logger.info(f"✅ Se encontraron {count} tablas en Neo4j, saltando ingesta.")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo verificar Neo4j ({e}). Intentando ingesta por si acaso...")
            try:
                ingest_neo4j_main()
            except Exception as e2:
                logger.error(f"❌ Error crítico al intentar ingesta en Neo4j: {e2}")

    async def main_async():
        await verify_qdrant()
        await verify_neo4j()
        
        port = int(os.getenv("PORT", 8080))
        logger.info(f"🚀 MCP server started on port {port}")
        await mcp.run_async(
            transport="http",
            host="0.0.0.0",
            port=port,
        )

    asyncio.run(main_async())
