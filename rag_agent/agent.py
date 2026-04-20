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

class existing_Output(BaseModel):
    existing_info: bool
    reasoning: str
    prompt_restructured: Optional[str] = None
    tables : Optional[List[str]] = None
    keywords_for_graph: Optional[List[str]] = None

class RagAgent:
    INSTRUCTIONS = ("""
        # ROL: DATA SCOUT (EXPLORADOR DE METADATA)
        
        ## CONTEXTO
        Tu rol es actuar como un "Data Scout". Tu objetivo es identificar qué tablas, dimensiones y hechos en la base de datos son relevantes para responder a la consulta del usuario.
        
        ## TUS HERRAMIENTAS
        Solo tienes acceso a `search_relevant_points`. Esta herramienta realiza una búsqueda semántica y te devuelve metadatos descriptivos de las tablas, sus columnas (dimensiones), miembros específicos de las dimensiones y sus métricas (hechos).
        
        ## REGLAS DE NEGOCIO PARA EL PAYLOAD
        Recibirás información enriquecida según el tipo de registro:
        1. **Tabla Maestra**: Recibes descripción general, temática y fuente. (No verás el esquema técnico completo aquí).
        2. **Dimensión**: Recibes el nombre de la columna, la tabla a la que pertenece y su descripción funcional.
        3. **Hecho**: Recibes el nombre de la métrica, tabla de origen, descripción detallada, unidades y reglas de agregación.
        
        ## TU MISIÓN
        1. **Identificar**: NO envíes el párrafo completo del usuario a la herramienta de búsqueda. Tu trabajo es extraer y desglosar las métricas, dimensiones o palabras clave (ej. ["costo de los fondos", "spread efectivo"]) y enviar ese ARREGLO de consultas concretas a la herramienta `search_relevant_points`. Ella te devolverá los puntos deduplicados que respondieron a tus múltiples consultas.
        2. **Analizar Hechos**: Si el usuario pide una métrica (ej. "Monto en Bs"), busca el hecho correspondiente y verifica sus `Avertencias` o `Dependencias`.
        3. **Razonar**: Explica técnicamente por qué las tablas seleccionadas son las correctas. Menciona los hechos y dimensiones encontrados que justifican tu elección basándote en la intersección de tus resultados.
        
        ## RESTRICCIONES
        - NO intentes generar código SQL.
        - Si no encuentras información relevante, indícalo claramente en el `reasoning`.
        - **REGLA ESTRICTA DE DOMINIO (VITAL)**: Verifica SIEMPRE la industria de la consulta. Si el usuario pregunta por un "Banco", está ESTRICTAMENTE PROHIBIDO seleccionar tablas cuya "Fuente" o "Temática" (Tabla Maestra) pertenezca a Seguros/Aseguradoras (ej. APS). Debes elegir tablas de ASFI/Bancos.
        - **REGLA ESTRICTA DE DOMINIO (VITAL)**: Si el usuario pregunta por una "Aseguradora" o "Seguros", está ESTRICTAMENTE PROHIBIDO seleccionar tablas de Bancos (ASFI). Debes elegir tablas de APS.
        - NUNCA selecciones una tabla si su `tematica` o `fuente` no coincide con la naturaleza de la entidad financiera consultada, incluso si hay un miembro que hace "match" por similitud léxica.
        
        ## FORMATO DE RESPUESTA (JSON)
        Responde ÚNICA Y EXCLUSIVAMENTE con este formato Pydantic:
        {
            "existing_info": boolean,
            "reasoning": "Explicación de los hallazgos...",
            "tables": ["NOMBRE_TECNICO_DE_TABLA"],
            "keywords_for_graph": ["BISA", "disponible", "activo"] // Lista de sustantivos base de negocio (Entidades, Cuentas, Rubros) extraídos de la pregunta. NO asumas nombres de columnas ni mandes cadenas completas. ESTRICTAMENTE PROHIBIDO incluir referencias temporales (años, meses, "últimos", "cierre") o lógicas. Extrae palabras puras (ej. "disponibilidades") para que el Grafo encuentre todas sus jerarquías.
        }
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