import os
import asyncpg
import pandas as pd
import logging
from agents import Agent, function_tool
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List
from pydantic import BaseModel

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

class SqlExecutorAgent:
    """
    Agente experto en la ejecución de consultas SQL.
    Su única responsabilidad es interactuar con Postgres y devolver resultados estructurados.
    """
    
    INSTRUCTIONS = """
    ## ROL: EJECUTOR SQL (ANALYST DATAX)
    Tu misión es ejecutar consultas SQL validadas en la base de datos de producción.
    
    ## REGLAS DE OPERACIÓN
    1. **Contexto de Entrada**: Recibirás un objeto JSON (proveniente del SQL Agent) con la estructura `{"queries": [{"sql_query": "...", "query_explanation": "..."}]}`.
    2. **Extracción**: Debes extraer el campo `sql_query` de cada objeto en la lista `queries`.
    3. **Ejecución Directa**: Usa la herramienta `ejecutar_consulta_sql` para correr el código SQL extraído.
    4. **Sin Modificaciones**: No intentes corregir, optimizar o alterar el SQL recibido a menos que falle. Si falla, reporta el error exacto.
    5. **Formato de Salida**: Los resultados se presentan como una tabla Markdown generada a partir de un DataFrame de Pandas.
    6. **Enfoque**: Solo ejecutas SQL. No haces análisis, no generas consultas nuevas, ni validas esquemas.
    """

    def __init__(self):
        # Configuración de base de datos desde variables de entorno
        self.db_user = os.getenv("USER_DB", "user_rag")
        self.db_pass = os.getenv("PASS_DB", "pass_rag")
        self.db_name = os.getenv("DATABASE_DB", "rag_db")
        self.db_host = os.getenv("HOST_DB", "db")
        self.db_port = os.getenv("PORT_DB", "5432")

        @function_tool
        async def ejecutar_consulta_sql(sql: str) -> str:
            """
            Ejecuta una consulta SQL en la base de datos Postgres y devuelve los resultados 
            como un DataFrame de Pandas convertido a formato Markdown.
            
            Args:
                sql: El comando SQL exacto a ejecutar.
            """
            logger.info(f"Ejecutando SQL: {sql}")
            try:
                # Conexión a Postgres usando asyncpg
                conn = await asyncpg.connect(
                    user=self.db_user,
                    password=self.db_pass,
                    database=self.db_name,
                    host=self.db_host,
                    port=self.db_port
                )
                try:
                    rows = await conn.fetch(sql)
                    if not rows:
                        return "✅ Consulta ejecutada exitosamente. No se devolvieron resultados (0 filas)."
                    
                    # Convertir registros de asyncpg a lista de diccionarios
                    data = [dict(r) for r in rows]
                    
                    # Crear DataFrame de Pandas
                    df = pd.DataFrame(data)
                    
                    # Formatear números para evitar notación científica y mejorar legibilidad
                    # Se aplica a todas las columnas numéricas
                    for col in df.select_dtypes(include=['number']).columns:
                        df[col] = df[col].apply(lambda x: f"{x:,.2f}" if x % 1 != 0 else f"{x:,.0f}")
                    
                    # Convertir a Markdown para una visualización premium en el chat
                    return df.to_markdown(index=False, tablefmt="github")
                
                finally:
                    await conn.close()
                    
            except Exception as e:
                logger.error(f"Error en ejecución SQL: {str(e)}")
                return f"❌ Error al ejecutar la consulta SQL: {str(e)}"

        self.agent = Agent(
            name="SQL Executor",
            instructions=self.INSTRUCTIONS,
            tools=[ejecutar_consulta_sql],
            model="gpt-4o-mini" # O el modelo configurado por defecto
        )
