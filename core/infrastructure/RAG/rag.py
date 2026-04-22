from typing import List

VECTOR_COUNTS = 5
SEARCH_RANKS = 5

def split2chunks(file: str) -> List[str]:
    """把文本拆封成小块"""
    f = open(file, 'r', encoding='utf-8')
    contents = f.read()

    return [c for c in contents.split("\n\n")]


from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer("shibing624/text2vec-base-chinese")

def embed_chunk(chunk: str) -> List[float]:
    """把文本转换成浮点向量"""
    embeddings = embedding_model.encode(chunk, normalize_embeddings=True)
    return embeddings.tolist()


import chromadb
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DB_PATH = PROJECT_ROOT / "data" / "knowledge" / "db" / "chroma_db"
# chromadb_client = chromadb.EphemeralClient() #内存型数据库，不会写入磁盘
_chromadb_client = None
_chromadb_collection = None


def _get_chromadb_collection():
    """惰性获取 Chroma collection，避免长期复用已关闭 client。"""
    global _chromadb_client, _chromadb_collection
    if _chromadb_collection is None:
        _chromadb_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        _chromadb_collection = _chromadb_client.get_or_create_collection(name="default")
    return _chromadb_collection


def _reset_chromadb_client() -> None:
    """丢弃当前 Chroma client，下次访问时重新创建。"""
    global _chromadb_client, _chromadb_collection
    _chromadb_client = None
    _chromadb_collection = None

def save_embeddings(chunks: List[str], embeddings: List[List[float]]):
    """保存向量和文件到数据库中"""
    collection = _get_chromadb_collection()
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            ids=[str(i)],
        )

def retrieve(query: str, top_k: int) -> List[str]:
    """向量召回，吧问题变成一串向量，随后去数据库中找意思最接近的"""
    query_embeddings = embed_chunk(query)
    try:
        res = _get_chromadb_collection().query(
            query_embeddings=[query_embeddings],
            n_results=top_k,
        )
    except RuntimeError as exc:
        if "client has been closed" not in str(exc):
            raise
        _reset_chromadb_client()
        res = _get_chromadb_collection().query(
            query_embeddings=[query_embeddings],
            n_results=top_k,
        )
    # print(res)
    return res["documents"][0]

from sentence_transformers import CrossEncoder
_cross_encoder = None


def _get_cross_encoder():
    """惰性加载 rerank 模型，避免每次检索重复初始化。"""
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')
    return _cross_encoder

def rerank(query: str, retrieve_chunks: List[str], top_k: int) -> List[str]:
    """把获取的向量按照和问题的关联程度重排。并获取前top_k个"""
    pairs = [(query, chunk) for chunk in retrieve_chunks]
    scores = _get_cross_encoder().predict(pairs)

    scored_chunks = list(zip(retrieve_chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    return [chunk for chunk, _ in scored_chunks[:top_k]]

def get_and_rerank_chunks(query: str, get_top_k: int = VECTOR_COUNTS, rank_top_k: int = SEARCH_RANKS) -> List[str]:
    retrieve_chunks = retrieve(query, get_top_k)
    reranked_chunks = rerank(query, retrieve_chunks, rank_top_k)

    return reranked_chunks

def format_chunks(chunks: List[str]) -> str:
    """把检索到的文本块格式化为可拼进提示词的参考资料。"""
    return "\n\n".join(
        f"[资料{i}]\n{chunk.strip()}"
        for i, chunk in enumerate(chunks, start=1)
        if chunk.strip()
    )

def main():
    # chunks = split2chunks("D:\pywork\PythonProject\data\knowledge\contract_review_rules\contract_type_rules.md")
    # embeddings = [embed_chunk(chunk) for chunk in chunks]
    # save_embeddings(chunks, embeddings)

    query = "帮我检验这个合同"
    retrieved_chunks = retrieve(query, top_k=30)
    # for i, chunk in enumerate(retrieved_chunks):
    #     print(f"[{i}] {chunk}\n")

    reranked_chunks = rerank(query, retrieved_chunks, 5)
    for i, chunk in enumerate(reranked_chunks):
        print(f"[{i}] {chunk}\n")

    return 0

if __name__ == '__main__':
    main()
