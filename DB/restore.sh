#!/bin/bash
set -e

# Este script es ejecutado por el entrypoint de PostgreSQL al inicializar la base de datos.
# Restauramos el dump binario que mapeamos en /tmp/backup_db.dump

DUMP_FILE="/tmp/backup_db.dump"

if [ -f "$DUMP_FILE" ]; then
    echo "🐘 Iniciando restauración de base de datos desde $DUMP_FILE..."
    pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$DUMP_FILE"
    echo "✅ Restauración completada con éxito."
else
    echo "⚠️ No se encontró el archivo de dump en $DUMP_FILE. Saltando restauración."
fi
