from db_connection import Session, SessionCube, SessionBulk
from sqlalchemy import text
import xml.etree.ElementTree as ET
import re
import json
class MetadataBuilder:
    def __init__(self, session_factory_rag: Session, session_factory_cube: SessionCube, session_factory_bulk: SessionBulk):
        self.session_factory_rag = session_factory_rag
        self.session_factory_cube = session_factory_cube
        self.session_factory_bulk = session_factory_bulk

    
    async def get_tables(self):
        async with self.session_factory_rag() as session:
            # Example of retrieving table names from the database
            result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            return [row[0] for row in result.fetchall()]
        
    async def get_columns(self, table_name: str):
        async with self.session_factory_rag() as session:
            # Example of retrieving column names for a specific table
            result = await session.execute(text(f"""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = :table_name
            """), {"table_name": table_name})
            return [(row[0], row[1]) for row in result.fetchall()]
    
    async def get_distinct_values(self, table_name: str, column_name: str):
        async with self.session_factory_rag() as session:
            # Example of retrieving distinct values from a specific column in a table
            result = await session.execute(text(f"""
                SELECT DISTINCT "{column_name}" 
                FROM "{table_name}"
            """))
            return [row[0] for row in result.fetchall()]
    
    async def get_facts_from_cube(self,  table_name: str):
        async with self.session_factory_cube() as session:
            facts = []

            db_result = await session.execute(text(f"""
                SELECT "facts" 
                FROM "cube"
                WHERE "cubename" = :table_name
            """), {"table_name": table_name})
            if db_result.rowcount > 0:
                 facts = self.xml_converter(db_result.fetchall()[0][0])
            return facts
        
    async def get_facts_from_bulk(self, table_name: str):
        async with self.session_factory_bulk() as session:
            facts = []

            db_result = await session.execute(text(f"""
                SELECT "hechos" 
                FROM "cubecatalogweb"
                WHERE "codigointerno" = :table_name
            """), {"table_name": table_name})
            if db_result.rowcount > 0:
                 facts = self.bulk_facts_to_list(db_result.fetchall()[0][0])
            return facts
        
    @staticmethod
    def xml_converter(xml_string: str):
        xml_facts = ET.fromstring(xml_string)
        facts = []
        for fact in xml_facts.findall('Fact'):
            fact_name = fact.get('name')
            facts.append(fact_name)
        return facts
    
    @staticmethod
    def bulk_facts_to_list(facts_string: str):
        if not facts_string:
            return []
        return [fact.strip() for fact in re.split(r'[y,]', facts_string) if fact.strip()]
    

if __name__ == "__main__":
    import asyncio

    async def main():
        builder = MetadataBuilder(Session, SessionCube, SessionBulk)
        tables = await builder.get_tables()
        metadata = {}
        for table in tables:
            print(f"Table: {table}")
            facts_from_cube = await builder.get_facts_from_cube(table)
            facts_from_bulk = await builder.get_facts_from_bulk(table)

            columns = await builder.get_columns(table)
            dimensions = []
            facts = []
            metadata[table] = {
                "Nombre dataset": "",
                "Descripcion tabla": "",
                "Fuente": "",
                "Granularidad": "",
                "Tematica": "",
                "Idioma": "",
                "Dimensiones": {},
                "Hechos": {}
            }
            for column in columns:
                column_name, column_type = column
                if column_name in facts_from_cube or column_name in facts_from_bulk or column_type in ['numeric','double precision']:
                    facts.append(column)
                else:
                    dimensions.append(column)
            for dimension in dimensions:
                dim_name, dim_type = dimension
                metadata[table]["Dimensiones"][dim_name] = {
                    "Tipo dato": dim_type,
                    "Tipo dimension": "",
                    "Descripcion": "",
                    "Miembros" : await builder.get_distinct_values(table, dim_name),
                    "Jerarquia": "",
                }
            for fact in facts:
                fact_name, fact_type = fact
                metadata[table]["Hechos"][fact_name] = {
                    "Tipo dato": fact_type,
                    "Tipo hecho": "",
                    "Descripcion": "",
                    "Unidad de medida": "",
                    "Funciones de agregacion": "",
                    "Funciones de agregacion prohibidas": "",
                    "Avertencias": "",
                    "Dependencias": "",
                }
        with open("metadata_structure2.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)   

    asyncio.run(main())        
