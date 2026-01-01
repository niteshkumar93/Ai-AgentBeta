from storage.database import engine
from storage.models import Base

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
