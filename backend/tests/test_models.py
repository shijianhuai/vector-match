from vector_match.db.models import Collection, DataIndex, Dataset, DatasetData, TrainingTask


def test_tables_registered():
    assert Dataset.__tablename__ == "datasets"
    assert Collection.__tablename__ == "collections"
    assert DatasetData.__tablename__ == "dataset_data"
    assert DataIndex.__tablename__ == "data_indexes"
    assert TrainingTask.__tablename__ == "training_tasks"


def test_mixin_columns_present():
    for model in (Dataset, Collection, DatasetData, DataIndex, TrainingTask):
        cols = model.__table__.columns
        for name in ("create_time", "update_time", "isvalid"):
            assert name in cols, f"{model.__tablename__} missing {name}"


def test_vector_column_nullable_and_dim():
    col = DataIndex.__table__.columns["vector"]
    assert col.nullable is True
    assert col.type.dim == 1024


def test_data_columns():
    cols = DatasetData.__table__.columns
    assert cols["a"].nullable is True
    assert cols["full_text_tokens"].default.arg == ""
