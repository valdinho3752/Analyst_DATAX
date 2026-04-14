import asyncio
import logging
import os
from openai import OpenAI
from fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv

# Cargar variables de entorno del .env de la raíz
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ================= CONFIGURACIÓN =================
# Debe coincidir exactamente con tu script de ingesta (ingest_openai.py)
COLLECTION_NAME = "rag_metadata_demo_openia"
VECTOR_NAME = "openai-embedding"
MODEL_NAME = "text-embedding-3-small"

# URL de Qdrant (ajustada para el entorno local o Docker)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# --- Inicialización de OpenAI ---
client_openai = OpenAI()

# --- Inicialización de Qdrant ---
qdrant_client = QdrantClient(url=QDRANT_URL)

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
def get_table_schema(table_name: str) -> dict:
    """
    Busca en Qdrant el esquema técnico (payload) de una tabla específica.
    """
    logger.info(f"--- 🔍 Buscando esquema para la tabla: {table_name} ---")
    
    try:
        # El método scroll devuelve una tupla (List[Record], Optional[Offset])
        records, next_page_offset = qdrant_client.scroll(
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
                    
            return schema
        else:
            logger.warning(f"⚠️ No se encontró la tabla '{table_name}'")
            return {"error": "Tabla no encontrada"}

    except Exception as e:
        logger.error(f"❌ Error al consultar Qdrant: {e}")
        return {"error": str(e)}


@mcp.tool()
def search_relevant_points(queries: list[str], limit_per_query: int = 15) -> dict:
    """
    Busca puntos relevantes basadas en una lista de palabras/frases clave.
    Devuelve un diccionario de elementos deduplicados indicando por qué consultas hicieron match.
    """
    logger.info(f"--- 🧠 Buscando puntos relevantes para {len(queries)} consultas ---")

    # Mecanismo de seguridad de Tokens
    max_queries = 10
    if len(queries) > max_queries:
        logger.warning(f"⚠️ El agente solicitó {len(queries)} consultas. Truncando a {max_queries} por seguridad de tokens.")
        queries = queries[:max_queries]

    try:
        # 1. Vectorizar las consultas en lote (Batch Embedding)
        # OpenAI SDK soporta enviar un array directamente, acelerando la petición
        response = client_openai.embeddings.create(
            input=queries,
            model=MODEL_NAME
        )
        query_vectors = [data.embedding for data in response.data]

        # 2. Buscar en Qdrant sin excluir miembros y unificar (Map/Reduce)
        # Usamos dict para deduplicar usando un hash del contenido
        deduplicated_results = {}
        
        for q_index, q_vector in enumerate(query_vectors):
            q_text = queries[q_index]
            
            points = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=q_vector,
                using=VECTOR_NAME,
                limit=limit_per_query,
                with_payload=True
            ).points

            for point in points:
                if point.payload:
                    cleaned_payload = dict(point.payload)
                    tipo = cleaned_payload.get("tipo")
                    
                    # Reglas de limpieza para ahorrar iteraciones
                    if tipo == "tabla_maestra":
                        cleaned_payload.pop("Dimensiones", None)
                        cleaned_payload.pop("Hechos", None)
                    elif tipo == "dimension":
                        cleaned_payload.pop("Miembros", None)
                    elif tipo == "miembro_dimension":
                        # Minimizar extremadamente el objeto
                        cleaned_payload = {
                            "tipo": "miembro_dimension",
                            "valor_miembro": cleaned_payload.get("valor_miembro"),
                            "nombre_columna": cleaned_payload.get("nombre_columna"),
                            "tabla_origen": cleaned_payload.get("tabla_origen")
                        }
                    
                    # Generar ID única del resultado para deduplicar
                    # (Si 3 queries encuentran el "Spread", solo guardamos "Spread" 1 vez y sumamos los matched_queries)
                    str_payload = str(cleaned_payload)
                    
                    if str_payload not in deduplicated_results:
                        deduplicated_results[str_payload] = {
                            "score_maximo": point.score,
                            "coincide_con_consultas": [q_text],
                            "info": cleaned_payload
                        }
                    else:
                        # Si ya existía por otra consulta, añadimos la consulta a la lista y evaluamos el score mayor
                        if q_text not in deduplicated_results[str_payload]["coincide_con_consultas"]:
                            deduplicated_results[str_payload]["coincide_con_consultas"].append(q_text)
                            deduplicated_results[str_payload]["score_maximo"] = max(deduplicated_results[str_payload]["score_maximo"], point.score)

        limpios = list(deduplicated_results.values())
        
        # Ordenar por cuantas consultas pegaron, y luego por score
        limpios.sort(key=lambda x: (len(x["coincide_con_consultas"]), x["score_maximo"]), reverse=True)
            
        logger.info(f"✅ Encontrados {len(limpios)} puntos deduplicados en total.")
        return {"resultados": limpios}

    except Exception as e:
        logger.error(f"❌ Error en búsqueda semántica (batch): {e}")
        return {"error": str(e)}


@mcp.tool()
def search_exact_members(query: str, table_name: str, limit: int = 25) -> list[str]:
    """
    Busca de forma semántica los valores/miembros categóricos exactos 
    para utilizar en una cláusula WHERE, basados en lenguaje natural.
    """
    logger.info(f"--- 🔍 Buscando miembros en la tabla '{table_name}' para: '{query}' ---")
    try:
        query_vector = get_single_embedding(query)
        points = qdrant_client.query_points(
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
        ).points
        
        results = []
        for p in points:
            columna = p.payload.get("nombre_columna", "Desconocida")
            valor = p.payload.get("valor_miembro", "Desconocido")
            results.append(f"Columna '{columna}': Valor literal exacto '{valor}' (Score de similitud: {p.score:.3f})")
            
        logger.info(f"✅ Encontrados {len(results)} miembros sugeridos")
        return results

    except Exception as e:
        logger.error(f"❌ Error en búsqueda de miembros exactos: {e}")
        return [f"Error: {str(e)}"]


if __name__ == "__main__":
    from ingest_openai import main as ingest_main
    
    try:
        qdrant_client.get_collection(COLLECTION_NAME)
        logger.info(f"✅ Colección '{COLLECTION_NAME}' encontrada, saltando ingesta.")
    except Exception:
        logger.info(f"⏳ Colección '{COLLECTION_NAME}' no existe. Iniciando ingesta en Qdrant por primera vez...")
        ingest_main()

    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 MCP server started on port {port}")
    asyncio.run(
        mcp.run_async(
            transport="http",
            host="0.0.0.0",
            port=port,
        )
    )
