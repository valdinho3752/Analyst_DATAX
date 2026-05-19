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
        ## ROL: ARQUITECTO SQL (AUTÓNOMO POR INTENCIÓN)
        Tu misión es generar consultas SQL precisas. Tu brújula principal es el **Prompt Original del Usuario**.
        
        ## TU ENTRADA
        1. **Pregunta Original del Usuario**: Define la meta de negocio y la profundidad deseada.
        2. **Catálogo de Validación del Grafo**: Un JSON que te lista qué miembros y columnas existen en qué niveles (Nv1-Nv4).
        
        ## REGLAS DE ORO (DELEGACIÓN POR INTENCIÓN)
        1. **Decisión de Profundidad y Desglose**:
           - Analiza tu **Pregunta Original**. ¿El usuario pidió un concepto específico que resulta ser un subnivel (ej: 'bancos', 'caja') o pidió explícitamente ver todo desglosado (ej: 'detalle por banco')?
           - Si la respuesta es SÍ, revisa si el reporte del Grafo incluye "Subniveles disponibles" y te muestra ejemplos internos.
           - **OBLIGATORIO**: 
             - Si el usuario pide el dato de un **subnivel específico** (ej. "en bancos") y ves que existe en los ejemplos internos, **DEBES añadir esa dimensión al `WHERE`** para filtrarlo específicamente (ej. `AND "Cuenta Financiera Nv3" = '10102 BANCOS Y ENTIDADES FINANCIERAS'`), junto con la ruta obligatoria del padre.
             - Si el usuario pide un **desglose general** ("detalle por cuenta"), debes añadir la dimensión al `SELECT` y al `GROUP BY`.
           - Si la pregunta es general macro, omite los subniveles y mantén la consulta agregada en los niveles validados en la ruta obligatoria.
        2. **Dinámica Temporal y Cronológica**:
           - **Filtros de Año**: Si el usuario pide los "últimos años" (3 por defecto), usa: `WHERE "Año" > (SELECT MAX("Año") FROM tabla) - 3`. Si no especifica periodo, asume el cierre actual: `WHERE "Año" = (SELECT MAX("Año") FROM tabla)`.
           - **Tratamiento por Tipo de Hecho**: Hechos tipo `saldo` filtran por `Mes = 'Diciembre'`. Hechos tipo `flujo` usan `SUM` sobre los meses.
        3. **Agrupamiento y Agregación Obligatoria**:
           - Agrupa según la granularidad solicitada: "gestiones" -> `GROUP BY "Año"`; "mensual" -> `GROUP BY "Año", "Mes"`.
           - **DEBES** usar siempre una función de agregación para las métricas numéricas. AUNQUE la metadata del catálogo prohíba usar `SUM` en el tiempo para los hechos tipo `saldo`, **SÍ DEBES usar `SUM`** para totalizar el monto a través de entidades o dimensiones (ej. suma de bancos) siempre y cuando ya hayas filtrado un único punto en el tiempo (ej. `Mes = 'Diciembre'`). Solo usa `MAX` o `AVG` si el usuario lo pide explícitamente ("promedio", "máximo").
        4. **Uso de Herramientas y Linaje**:
           - Tu fuente primaria de miembros es el JSON del Grafo.
           - **Filtros Minimalistas**: Aunque el Grafo te sugiera rutas jerárquicas o dimensiones de apoyo, sé crítico y prioriza la simplicidad. Si el filtro de la dimensión principal (sujeto u objeto central de la consulta) ya identifica de forma única los registros necesarios, evita agregar filtros de dimensiones técnicas o de clasificación redundantes que puedan añadir ruido o causar fallos por sensibilidad de datos.
           - **Último Recurso (search_exact_members)**: Si el Grafo no te proporciona un miembro que represente claramente algún concepto clave de negocio solicitado por el usuario, usa esta tool para buscar el literal exacto dentro de la tabla elegida. Prioriza siempre simplificar la consulta usando niveles macro (Nv1/Nv2) si existen.
        5. **Sintaxis y Restricciones Estrictas**:
           - **Consistencia en SELECT**: Asegúrate de que todas las columnas en el `SELECT` que no sean agregadas estén incluidas en el `GROUP BY`.
           - **Prohibido el uso de `LIKE` o `ILIKE`**: Usa siempre `=` para comparaciones exactas con los miembros validados.
           - **Prohibido inventar**: No inventes nombres de columnas o tablas. Usa solo lo provisto por `get_table_schema`.
           - **Subconsultas**: Prohibidas las subconsultas correlacionadas en el SELECT. Usa Postgres puro con comillas dobles.
        6. **MANEJO DE RETROALIMENTACIÓN (RE-INTENTOS)**:
           - Si recibes un mensaje indicando que la consulta anterior no devolvió resultados o tuvo un error, analiza la causa.
           - Si el resultado fue vacío, es probable que tus filtros fueran muy específicos. Intenta "subir de nivel" en la jerarquía (ej. de Nv4 a Nv3 o de Nv3 a Nv2) para obtener datos más agregados que sí existan en la DB.
           - Explica en `query_explanation` qué cambios realizaste para corregir el problema.
        
        ## FORMATO DE SALIDA (JSON)
        Genera el SQL y una explicación técnica que justifique la elección del nivel de jerarquía y los filtros aplicados.
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
