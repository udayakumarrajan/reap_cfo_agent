from erp_service.core.database import create_db_engine, get_session_factory, SqlAlchemyERP
from bootstrap.config import DATABASE_URL

def init_db(db_url: str = DATABASE_URL) -> SqlAlchemyERP:
    """
    Initializes the database engine, session factory, and SqlAlchemyERP repository.
    """
    engine = create_db_engine(db_url)
    session_factory = get_session_factory(engine)
    return SqlAlchemyERP(session_factory)
