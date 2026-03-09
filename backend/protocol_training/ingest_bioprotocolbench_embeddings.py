"""
BioProBench Embedding Pipeline
================================
Embeds 27K protocols and up to 100K training instances into Pinecone
for RAG-based protocol reasoning.

Namespace: protocol-corpus
"""

import os
import json
import logging
import hashlib
from pathlib import Path

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

CORPUS_PATH = Path(CORPUS_DIR)
BATCH_SIZE = 50  # Pinecone upsert batch size
MAX_CHUNK_CHARS = 1500


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list:
    """Split text into chunks for embedding."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = text.replace(". ", ".\n").split("\n")
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]


def embed_protocols(embedding_client=None, vector_store=None, max_protocols: int = 30000):
    """
    Embed BioProBench protocols into Pinecone protocol-corpus namespace.

    Args:
        embedding_client: Azure OpenAI client for embeddings
        vector_store: Pinecone vector store instance
        max_protocols: Max protocols to embed

    Returns:
        dict with counts of embedded items
    """
    protocols_file = os.path.join(CORPUS_DIR, 'bioprotocolbench_protocols.jsonl')
    training_file = os.path.join(CORPUS_DIR, 'bioprotocolbench_training.json')

    stats = {"protocols_embedded": 0, "training_embedded": 0, "chunks_created": 0, "errors": 0}

    if not os.path.exists(protocols_file):
        logger.warning(f'[BPB-Embed] Protocols not found at {protocols_file}. Run ingest_bioprotocolbench first.')
        return stats

    if not embedding_client or not vector_store:
        logger.error('[BPB-Embed] embedding_client and vector_store are required')
        return stats

    deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

    # --- Embed protocols ---
    logger.info('[BPB-Embed] Embedding BioProBench protocols...')
    vectors_batch = []

    with open(protocols_file, "r") as f:
        for i, line in enumerate(f):
            if i >= max_protocols:
                break
            try:
                protocol = json.loads(line)
                title = protocol.get("title", "Untitled")
                domain = protocol.get("domain", "unknown")
                source = protocol.get("source", "bioprotocolbench")

                # Build text from protocol
                steps = protocol.get("steps", [])
                steps_text = " ".join([
                    s.get("text", "") if isinstance(s, dict) else str(s)
                    for s in steps
                ])
                reagents = ", ".join(protocol.get("reagents", [])[:20])
                equipment = ", ".join(protocol.get("equipment", [])[:20])

                full_text = f"{title}. {steps_text}"
                if reagents:
                    full_text += f" Reagents: {reagents}."
                if equipment:
                    full_text += f" Equipment: {equipment}."

                # Chunk
                chunks = _chunk_text(full_text)

                for ci, chunk in enumerate(chunks):
                    vec_id = hashlib.md5(f"bpb-{i}-{ci}".encode()).hexdigest()

                    try:
                        resp = embedding_client.embeddings.create(
                            model=deployment,
                            input=chunk,
                            dimensions=1536,
                        )
                        embedding = resp.data[0].embedding
                    except Exception as e:
                        if stats["errors"] < 5:  # Log first 5 errors at warning level
                            logger.warning(f'[BPB-Embed] Embedding failed for protocol {i} chunk {ci}: {e}')
                        stats["errors"] += 1
                        continue

                    vectors_batch.append({
                        "id": vec_id,
                        "values": embedding,
                        "metadata": {
                            "text": chunk[:1000],
                            "title": title[:200],
                            "domain": domain,
                            "source": source,
                            "type": "protocol",
                            "protocol_idx": i,
                            "chunk_idx": ci,
                        }
                    })
                    stats["chunks_created"] += 1

                    # Batch upsert
                    if len(vectors_batch) >= BATCH_SIZE:
                        try:
                            vector_store.index.upsert(
                                vectors=vectors_batch,
                                namespace="protocol-corpus"
                            )
                        except Exception as e:
                            logger.error(f'[BPB-Embed] Pinecone upsert failed: {e}')
                            stats["errors"] += 1
                        vectors_batch = []

                stats["protocols_embedded"] += 1

                if (i + 1) % 500 == 0:
                    logger.info(f'[BPB-Embed]   Embedded {i + 1} protocols, {stats["chunks_created"]} chunks')

            except Exception as e:
                logger.debug(f'[BPB-Embed] Protocol {i} failed: {e}')
                stats["errors"] += 1

    # Flush remaining
    if vectors_batch:
        try:
            vector_store.index.upsert(vectors=vectors_batch, namespace="protocol-corpus")
        except Exception as e:
            logger.error(f'[BPB-Embed] Final Pinecone upsert failed: {e}')

    # --- Embed training instances (QA, error correction) ---
    if os.path.exists(training_file):
        logger.info('[BPB-Embed] Embedding BioProBench training instances...')
        try:
            with open(training_file, "r") as f:
                training_data = json.load(f)

            vectors_batch = []
            instance_count = 0
            max_instances = 50000  # Cap for cost control

            for task_name, instances in training_data.items():
                if instance_count >= max_instances:
                    break
                if not isinstance(instances, list):
                    continue
                for inst in instances[:10000]:  # Max 10K per task
                    if instance_count >= max_instances:
                        break

                    # Build searchable text from instance
                    text_parts = []
                    if isinstance(inst, dict):
                        for key in ["question", "input", "protocol", "context", "text"]:
                            if key in inst and inst[key]:
                                text_parts.append(str(inst[key])[:500])
                        for key in ["answer", "output", "correction"]:
                            if key in inst and inst[key]:
                                text_parts.append(str(inst[key])[:500])
                    else:
                        text_parts.append(str(inst)[:1000])

                    text = " ".join(text_parts)
                    if len(text) < 50:
                        continue

                    vec_id = hashlib.md5(f"bpb-train-{task_name}-{instance_count}".encode()).hexdigest()

                    try:
                        resp = embedding_client.embeddings.create(
                            model=deployment,
                            input=text[:1500],
                            dimensions=1536,
                        )
                        embedding = resp.data[0].embedding
                    except Exception as e:
                        stats["errors"] += 1
                        continue

                    vectors_batch.append({
                        "id": vec_id,
                        "values": embedding,
                        "metadata": {
                            "text": text[:1000],
                            "task": task_name,
                            "source": "bioprotocolbench_training",
                            "type": "training_instance",
                        }
                    })
                    instance_count += 1
                    stats["training_embedded"] += 1

                    if len(vectors_batch) >= BATCH_SIZE:
                        try:
                            vector_store.index.upsert(vectors=vectors_batch, namespace="protocol-corpus")
                        except Exception as e:
                            logger.error(f'[BPB-Embed] Training upsert failed: {e}')
                        vectors_batch = []

            if vectors_batch:
                try:
                    vector_store.index.upsert(vectors=vectors_batch, namespace="protocol-corpus")
                except Exception as e:
                    logger.error(f'[BPB-Embed] Final training upsert failed: {e}')

        except Exception as e:
            logger.error(f'[BPB-Embed] Training embedding failed: {e}')

    logger.info(f'[BPB-Embed] Embedding complete: {stats}')
    return stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print('BioProBench Embedding Pipeline')
    print('Requires embedding_client and vector_store arguments.')
    print('Run via the orchestrator or pass Azure OpenAI + Pinecone clients.')
