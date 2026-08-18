from backend.app.db.database import Base, engine
from backend.app.models.token import Token
from backend.app.models.pair import Pair


def init_db() -> None:
    Base.metadata.create_all(bind=engine)