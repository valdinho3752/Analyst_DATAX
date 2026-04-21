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
    tool_filter={"include": ["get_table_schema", "search_exact_members"]}
)

class sql_queries(BaseModel):
    sql_query: str
    query_explanation: str

class sql_Output(BaseModel):
    queries: List[sql_queries]

class SqlAgent:
    
    INSTRUCTIONS = ("""
        ## ROL: ARQUITECTO SQL (EJECUTOR TÉCNICO)
        Tu misión es generar consultas SQL precisas basadas en la metadata técnica.
        
        ## TU ENTRADA
        - Pregunta Original: El objetivo de negocio del usuario.
        - Validación del Grafo: Un JSON técnico que confirma tablas válidas y niveles jerárquicos (Nv1, Nv2, etc.).
        
        ## REGLAS DE OPERACIÓN
        1. **Interpretación de Jerarquía (VITAL)**: 
           - Tu prioridad absoluta es responder a la granularidad de la pregunta del usuario. 
           - Si el usuario pide un saldo macro (ej. "Activos", "Monto de seguros"), usa preferentemente los niveles **Nv1 o Nv2** recomendados por el Grafo. 
           - **OBLIGATORIO**: Ignora cualquier miembro granular (Nv3+) si el nivel Nv2 ya engloba semánticamente el concepto. No generes filtros masivos de Nv4 si un solo filtro de Nv2 es suficiente.
        2. **Sintaxis**: Postgres puro. Usa comillas dobles para nombres de tablas y columnas (ej. "S_BOS...").
        3. **Comportamiento Cronológico y Dinámica Temporal**: 
           - **Filtros de Año**: Si el usuario pide los "últimos años" (3 por defecto), usa: `WHERE "Año" > (SELECT MAX("Año") FROM tabla) - 3`. Si no especifica periodo, asume el cierre actual: `WHERE "Año" = (SELECT MAX("Año") FROM tabla)`. Si pide un año específico, usa el valor absoluto.
           - **Tratamiento por Tipo de Hecho**: 
             * Hechos tipo `saldo`: Filtra obligatoriamente por periodo de cierre (ej. `AND "Mes" = 'Diciembre'`) para totales anuales para evitar duplicidad.
             * Hechos tipo `flujo`: Puedes usar `SUM` sobre los meses sin restringir al cierre.
           - **Agrupamiento Dinámico**: Agrupa los resultados según la granularidad solicitada: si pide "gestiones" o "anual", agrupa por "Año"; si pide "mensual", agrupa por "Año" y "Mes"; si pide por "entidad", agrupa por el nombre de la entidad, etc. Siempre aplica funciones de agregación (`SUM`, `AVG`) según lo permita la metadata del hecho.
        4. **Herramientas de Verificación**: 
           - Usa OBLIGATORIAMENTE `get_table_schema` para confirmar el nombre real de las columnas antes de escribir el SQL.
           - Usa `search_exact_members` solo para encontrar nombres de entidades específicas (ej. "Banco BISA") si el Grafo no proporcionó el literal exacto.
        
        ## RESTRICCIONES ESTRICTAS
        - Prohibido el uso de `LIKE` o `ILIKE`. Usa `=`.
        - Prohibido inventar nombres de columnas o tablas.
        - Prohibidas las subconsultas correlacionadas en el SELECT.
        
        ## FORMATO DE SALIDA (JSON)
        Genera un SQL limpio y eficiente que responda directamente a la pregunta inicial. Responde ÚNICAMENTE en formato JSON validado por Pydantic.
    """)
    def __init__(self):
        self.qdrant_mcp_server = qdrant_mcp_server
        self.mcp_servers = [self.qdrant_mcp_server]
        self.agent = Agent(
            name="SQL Architect",
            instructions=self.INSTRUCTIONS,
            output_type=sql_Output,
            mcp_servers=self.mcp_servers,
            model="gpt-5.4-2026-03-05"
        )
