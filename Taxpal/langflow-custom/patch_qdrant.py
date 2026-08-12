from pathlib import Path
import importlib.util


# Locate Langflow's installed Qdrant component
spec = importlib.util.find_spec("lfx_bundles.qdrant.qdrant")

if spec is None or spec.origin is None:
    raise RuntimeError("Could not locate Qdrant component.")

path = Path(spec.origin)

print(f"Found Qdrant component: {path}")

text = path.read_text(encoding="utf-8")


# ============================================================
# FIX 1: Langflow expects page_content, but our Qdrant payload
# stores the document text under "text".
# ============================================================

old_payload = (
    'StrInput(name="content_payload_key", '
    'display_name="Content Payload Key", '
    'value="page_content", advanced=True)'
)

new_payload = (
    'StrInput(name="content_payload_key", '
    'display_name="Content Payload Key", '
    'value="text", advanced=True)'
)

if old_payload in text:
    text = text.replace(
        old_payload,
        new_payload,
        1
    )
    print("Changed content payload key: page_content -> text")

elif 'value="text"' in text and 'name="content_payload_key"' in text:
    print("Content payload key already uses text.")

else:
    raise RuntimeError(
        "Could not find content payload key."
    )


# ============================================================
# FIX 2: Our collection uses a named dense vector called
# "dense", while LangChain defaults to vector_name="".
# ============================================================

old_retrieval = (
    "qdrant = QdrantVectorStore("
    "embedding=self.embedding, "
    "client=client, "
    "**qdrant_kwargs)"
)

new_retrieval = (
    "qdrant = QdrantVectorStore("
    "embedding=self.embedding, "
    "client=client, "
    'vector_name="dense", '
    "**qdrant_kwargs)"
)

if old_retrieval in text:
    text = text.replace(
        old_retrieval,
        new_retrieval,
        1
    )
    print("Added vector_name='dense' to retrieval.")

elif 'vector_name="dense"' in text:
    print("Retrieval already uses vector_name='dense'.")

else:
    raise RuntimeError(
        "Could not find Qdrant retrieval constructor."
    )


# ============================================================
# OPTIONAL: Make Langflow ingestion use the same vector name.
# This does not affect your existing 329 points.
# ============================================================

old_ingestion = (
    "documents, embedding=self.embedding, ids=ids, "
    "**qdrant_kwargs, **server_kwargs"
)

new_ingestion = (
    "documents, embedding=self.embedding, ids=ids, "
    'vector_name="dense", '
    "**qdrant_kwargs, **server_kwargs"
)

if old_ingestion in text:
    text = text.replace(
        old_ingestion,
        new_ingestion,
        1
    )
    print("Added vector_name='dense' to Langflow ingestion.")
else:
    print(
        "Ingestion constructor not changed. "
        "This is okay for retrieval testing."
    )


# Save patched component
path.write_text(text, encoding="utf-8")

print("Qdrant component patched successfully.")