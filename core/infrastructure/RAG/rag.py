from typing import List


def split2chunks(file: str) -> List[str]:
    f = open(file, 'r', encoding='utf-8')
    contents = f.read()

    return [c for c in contents.split("\n\n")]


from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer("shibing624/text2vec-base-chinese")

def embed_chunk(chunk: str) -> List[float]:
    embeddings = embedding_model.encode(chunk, normalize_embeddings=True)
    return embeddings.tolist()


import chromadb
chromadb_client = chromadb.EphemeralClient() #内存型数据库，不会写入磁盘
chromadb_collection = chromadb_client.get_or_create_collection(name="default")

def save_embeddings(chunks: List[str], embeddings: List[List[float]]):
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chromadb_collection.add(
            documents=[chunk],
            embeddings=[embedding],
            ids=[str(i)],
        )

def retrieve(query: str, top_k: int) -> List[str]:
    query_embeddings = embed_chunk(query)
    res = chromadb_collection.query(
        query_embeddings=[query_embeddings],
        n_results=top_k,
    )
    return res["documents"][0]

from sentence_transformers import CrossEncoder

def rerank(query: str, retrieve_chunks: List[str], top_k: int) -> List[str]:
    cross_encoder = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')
    pairs = [(query, chunk) for chunk in retrieve_chunks]
    scores = cross_encoder.predict(pairs)

    scored_chunks = list(zip(retrieve_chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    return [chunk for chunk, _ in scored_chunks[:top_k]]


def main():
    chunks = split2chunks("D:\pywork\PythonProject\data\knowledge\contract_review_rules\contract_type_rules.md")
    embeddings = [embed_chunk(chunk) for chunk in chunks]
    save_embeddings(chunks, embeddings)

    query = "哆啦A梦有什么知名道具"
    retrieved_chunks = retrieve(query, top_k=5)
    # for i, chunk in enumerate(retrieved_chunks):
    #     print(f"[{i}] {chunk}\n")

    reranked_chunks = rerank(query, retrieved_chunks, 5)
    for i, chunk in enumerate(reranked_chunks):
        print(f"[{i}] {chunk}\n")

    return 0

if __name__ == '__main__':
    main()