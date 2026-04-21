from agents import Agent
# from agents.tool import FileSearchTool
from agents.mcp import MCPServerStreamableHttp

from dotenv import load_dotenv, find_dotenv
from typing import Optional , List
from pydantic import BaseModel
load_dotenv(find_dotenv())

# VECTOR_STORE_ID = "vs_69d0b04d55208191af182b98a3fc3e00"  

# file_search_tool = FileSearchTool(
#     vector_store_ids=[VECTOR_STORE_ID]
# )

qdrant_mcp_server = MCPServerStreamableHttp(
    params={
        "url": "http://mcp_server_openai:8080/mcp"
    },
    tool_filter={"include": ["search_relevant_points"]}
)

class TableFinding(BaseModel):
    nombre_tecnico: str
    justificacion_hallazgo: str
    pistas_miembros: List[str]
    columnas_detectadas: List[str]

class existing_Output(BaseModel):
    existing_info: bool
    reasoning: str
    prompt_restructured: Optional[str] = None
    tables_found: Optional[List[TableFinding]] = None
    keywords_for_graph: Optional[List[str]] = None

class RagAgent:
    INSTRUCTIONS = ("""
        # ROL: DATA SCOUT (EXPLORADOR DE METADATA)
        
        ## CONTEXTO
        Tu objetivo es identificar las tablas candidatas y términos clave para la consulta del usuario. Tu salida será enviada directamente al Graph Agent para validación.
        
        ## TU HERRAMIENTA: `search_relevant_points`
        La herramienta devuelve un resumen de **TABLAS CONSOLIDADAS**.
        Por cada tabla recibirás:
        - `tabla`: Metadata (nombre técnico, descripción, temática, fuente).
        - `columnas_halladas`: Lista de dimensiones que hicieron match semántico.
        - `pistas_miembros`: Valores literales encontrados en los datos.
        
        ## TU MISIÓN
        1. **Estrategia de Búsqueda**: Extrae conceptos contables puros y entidades (ej. ["disponibilidad", "Spread", "BISA"]) y usa `search_relevant_points`.
        2. **Análisis de Relevancia**: Selecciona las mejores tablas candidatas.
        3. **Filtro de Dominio Estricto**:
           - Consulta sobre BANCOS -> Usa tablas ASFI. PROHIBIDO usar APS.
           - Consulta sobre SEGUROS -> Usa tablas APS. PROHIBIDO usar ASFI.
        
        ## FORMATO DE SALIDA (JSON)
        Debes poblar `tables_found`. Sé preciso con las `pistas_miembros`: incluye solo los valores literales que el Graph Agent deba verificar en Neo4j.
        No incluyas interpretaciones personales; solo pasa los hechos técnicos encontrados.
    """)
    def __init__(self):
        self.qdrant_mcp_server = qdrant_mcp_server
        self.mcp_servers = [self.qdrant_mcp_server]
        self.agent = Agent(
            name="Verificación de existencia de datos",
            instructions=self.INSTRUCTIONS,
            output_type=existing_Output,
            mcp_servers=self.mcp_servers,
            model="gpt-5.4-2026-03-05"
        )