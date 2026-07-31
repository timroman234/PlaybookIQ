from app.services.vector_store import LocalVectorStore


def test_upsert_and_query_returns_most_similar_first(tmp_path):
    store = LocalVectorStore(persist_path=tmp_path / "store.pkl")

    store.upsert("a", vector=[1.0, 0.0], text="matches exactly", metadata={"document_type": "x"})
    store.upsert("b", vector=[0.0, 1.0], text="orthogonal", metadata={"document_type": "x"})

    results = store.query(vector=[1.0, 0.0], top_k=2)

    assert results[0].content == "matches exactly"
    assert results[0].score > results[1].score


def test_query_filters_by_metadata(tmp_path):
    store = LocalVectorStore(persist_path=tmp_path / "store.pkl")
    store.upsert("a", vector=[1.0, 0.0], text="injury doc", metadata={"document_type": "injury_log"})
    store.upsert("b", vector=[1.0, 0.0], text="scouting doc", metadata={"document_type": "scouting_report"})

    results = store.query(vector=[1.0, 0.0], top_k=5, filters={"document_type": "injury_log"})

    assert len(results) == 1
    assert results[0].content == "injury doc"


def test_persistence_round_trip(tmp_path):
    path = tmp_path / "store.pkl"
    store = LocalVectorStore(persist_path=path)
    store.upsert("a", vector=[1.0, 0.0], text="persisted", metadata={})

    reloaded = LocalVectorStore(persist_path=path)
    results = reloaded.query(vector=[1.0, 0.0], top_k=1)

    assert results[0].content == "persisted"
