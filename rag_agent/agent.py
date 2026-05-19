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
        1. **Descomposición del Prompt**: Lee cuidadosamente el prompt del usuario y divídelo obligatoriamente en múltiples frases, conceptos y **palabras clave atómicas**. Debes incluir tanto la **frase completa** como sus **componentes individuales** más significativos para maximizar el match semántico (ej. si el usuario busca "activo disponible", incluye ["activo disponible", "activo", "disponible"]). Escríbelas en el `prompt_restructured`.
        2. **Estrategia de Búsqueda**: Usa obligatoriamente estas frases y palabras extraídas para invocar `search_relevant_points`.
        3. **Análisis de Relevancia y Selección**: De todas las tablas que te devuelva la herramienta, evalúa cuáles son relevantes para responder de forma completa a la consulta. **Es obligatorio que te bases fundamentalmente en la descripción detallada de la tabla** (campo `descripcion` del objeto `tabla` devuelto por `search_relevant_points`) para verificar si su alcance de negocio, granularidad e intención se alinean con la consulta del usuario. Si la pregunta permite comparar diferentes perspectivas, cruzar datos, o si existen datasets con distintos enfoques (ej: saldos mensuales vs ratios o tasas), **debes incluir todas las tablas complementarias o alternativas viables**. No te limites a elegir una única tabla por defecto. Si existen tablas con puntuaciones de relevancia altas (> 0.45) que aporten al contexto, inclúyelas para que el SQL Agent tenga la libertad de decidir la mejor estrategia de consulta (o hacer JOINs si corresponde).
        4. **Extracción Exacta de Miembros**: Asegúrate de que las `pistas_miembros` capturadas sean EXTREMADAMENTE precisas, ya que el Graph Agent las usará para validar la estructura. **REGLA CRÍTICA**: Debes extraer y copiar los valores de `pistas_miembros` EXACTAMENTE como aparecen en la respuesta de la herramienta. No combines palabras, no inventes valores y no alucines. Si el usuario pide "BISA seguros" pero la herramienta solo devuelve "BISA", debes colocar estrictamente "BISA".
        
        ## FORMATO DE SALIDA (JSON)
        Debes poblar `tables_found`.
        No incluyas interpretaciones personales; solo pasa los hechos técnicos encontrados y las pistas de miembros vitales.
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