from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

# Database Config - Main
host = os.getenv("HOST")
port = os.getenv("PORT")  
user = os.getenv("USER")
password = os.getenv("PASS")
database = os.getenv("DATABASE")

# Database Config - Local/Specific
port_local = os.getenv("PORT_LOCAL")  
user_local = os.getenv("USER_LOCAL")
password_local = os.getenv("PASS_LOCAL")
database_cube = os.getenv("DATABASE_CUBE")
database_bulk = os.getenv("DATABASE_BULK")

# Shared Engines and factories to prevent connection leaks
# These are created once at module load time.
engine_rag = create_async_engine(
    f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}", 
    echo=False, future=True
)
factory_rag = async_sessionmaker(bind=engine_rag, expire_on_commit=False)

engine_cube = create_async_engine(
    f"postgresql+asyncpg://{user_local}:{password_local}@{host}:{port_local}/{database_cube}", 
    echo=False, future=True
)
factory_cube = async_sessionmaker(bind=engine_cube, expire_on_commit=False)

engine_bulk = create_async_engine(
    f"postgresql+asyncpg://{user_local}:{password_local}@{host}:{port_local}/{database_bulk}", 
    echo=False, future=True
)
factory_bulk = async_sessionmaker(bind=engine_bulk, expire_on_commit=False)

class Session():
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = factory_rag()
        return self.session

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            print(f"An error occurred: {exc_value}\n place: {traceback}")
            await self.session.rollback()
        else:
            print("Committing changes to the database...")
            await self.session.commit()
        await self.session.close()

class SessionCube():
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = factory_cube()
        return self.session

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            print(f"An error occurred: {exc_value}\n place: {traceback}")
            await self.session.rollback()
        else:
            print("Committing changes to the database...")
            await self.session.commit()
        await self.session.close()

class SessionBulk():
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = factory_bulk()
        return self.session

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            print(f"An error occurred: {exc_value}\n place: {traceback}")
            await self.session.rollback()
        else:
            print("Committing changes to the database...")
            await self.session.commit()
        await self.session.close()

class Base(DeclarativeBase):
    pass