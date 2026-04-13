import json
# from langchain_google_vertexai import VertexAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models

# --- CARGAR TU JSON ---
with open("./metadata/metadata_demo.json", "r", encoding="utf-8") as f:
    metadata_raw = json.load(f)

# Lista para guardar los puntos listos para Qdrant
puntos_qdrant = []
id_counter = 0

# --- PROCESAMIENTO (LA MAGIA) ---
# Tu JSON empieza con el nombre de la tabla como llave principal
for nombre_tabla, data_tabla in metadata_raw.items():
    
    dataset = data_tabla.get("Nombre dataset")
    desc_tabla = data_tabla.get("Descripcion tabla")
    
    # 1. CREAR CHUNK MAESTRO DE TABLA
    # Recopilamos nombres de columnas para dar contexto
    dims = list(data_tabla.get("Dimensiones", {}).keys())
    hechos = list(data_tabla.get("Hechos", {}).keys())
    
    texto_tabla = (
        f"Tabla de Base de Datos: {nombre_tabla}. "
        f"Dataset: {dataset}. "
        f"Descripción: {desc_tabla}. "
        f"Contiene las dimensiones: {', '.join(dims)} y los hechos: {', '.join(hechos)}."
    )
    
    puntos_qdrant.append({
        "texto": texto_tabla,
        "payload": {
            "tipo": "tabla_maestra",
            "nombre_tabla": nombre_tabla,
            **data_tabla
        }
    })

    # 2. PROCESAR DIMENSIONES
    columnas_dim = data_tabla.get("Dimensiones", {})
    for col_nombre, col_data in columnas_dim.items():
        # Aplanar la lista de miembros para el texto (solo los primeros 10)
        miembros_ejemplo = ", ".join(map(str, col_data.get("Miembros", [])[:10]))
        
        texto_dim = (
            f"Columna Dimensión: {col_nombre}. "
            f"Pertenece a la Tabla: {nombre_tabla}. "
            f"Descripción: {col_data.get('Descripcion')}. "
            f"Valores ejemplo: {miembros_ejemplo}. "
            f"Jerarquía: {col_data.get('Jerarquia')}."
        )
        
        puntos_qdrant.append({
            "texto": texto_dim,
            "payload": {
                "tipo": "dimension",
                "nombre_columna": col_nombre,
                "tabla_origen": nombre_tabla,
                **col_data
            }
        })

        # 2.1 PROCESAR CHUNKS POR CADA MIEMBRO
        for miembro in col_data.get("Miembros", []):
            texto_miembro = (
                f"Valor/Miembro: {miembro}. "
                f"Dimensión: {col_nombre}. "
                f"Tabla: {nombre_tabla}. "
                f"Descripción: {col_data.get('Descripcion')}."
            )
            
            puntos_qdrant.append({
                "texto": texto_miembro,
                "payload": {
                    "tipo": "miembro_dimension",
                    "valor_miembro": miembro,
                    "nombre_columna": col_nombre,
                    "tabla_origen": nombre_tabla
                }
            })

    # 3. PROCESAR HECHOS (MÉTRICAS)
    # Aquí es vital incluir la lógica de cálculo y agregación
    columnas_hechos = data_tabla.get("Hechos", {})
    for col_nombre, col_data in columnas_hechos.items():
        
        texto_hecho = (
            f"Métrica o Hecho: {col_nombre}. "
            f"Tabla: {nombre_tabla}. "
            f"Descripción: {col_data.get('Descripcion')}. "
            f"Unidad: {col_data.get('Unidad de medida')}. "
            f"Agregaciones permitidas: {col_data.get('Funcioenes de agregacion')}. "
            f"Agregaciones prohibidas: {col_data.get('Funciones de agregacion prohibidas')}. "
            f"Advertencias: {col_data.get('Avertencias')}."
        )
        
        puntos_qdrant.append({
            "texto": texto_hecho,
            "payload": {
                "tipo": "hecho",
                "nombre_columna": col_nombre,
                "tabla_origen": nombre_tabla,
                **col_data
            }
        })

print(f"✅ Procesado completado. Se generaron {len(puntos_qdrant)} chunks.")

# Guardar en JSON para su posterior vectorización
OUTPUT_FILE = "chunks_demo3.json"
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(puntos_qdrant, f, indent=4, ensure_ascii=False)

print(f"💾 Chunks guardados exitosamente en: {OUTPUT_FILE}")