from advisor.rag.ingest import chunk_text


def test_chunking_basic():
    text = "abcdefghij" * 200  # 2000 chars
    chunks = chunk_text(text, size=800, overlap=120)
    assert len(chunks) > 1
    assert all(c for c in chunks)
    # Adjacent chunks share overlap region
    assert chunks[0][-50:] == chunks[1][:50] or chunks[0][-120:] == chunks[1][:120]


def test_chunking_short_text():
    chunks = chunk_text("short", size=800, overlap=120)
    assert chunks == ["short"]


def test_chunking_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []
