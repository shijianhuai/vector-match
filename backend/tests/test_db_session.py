from vector_match.core.config import Settings
from vector_match.db.base import utcnow
from vector_match.db.session import make_engine, make_session_factory


def test_utcnow_tz_aware():
    assert utcnow().tzinfo is not None


def test_make_engine_and_session_factory():
    engine = make_engine(Settings())
    assert engine.dialect.name == "postgresql"
    factory = make_session_factory(engine)
    assert factory is not None
