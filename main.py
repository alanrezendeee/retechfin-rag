from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import faiss
import os
from openai import OpenAI
from excel_loader import load_expenses_from_excel

app = FastAPI()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

expenses = load_expenses_from_excel("financas_2025.xlsx")

# função que transforma uma despesa em texto padronizado
def expense_to_text(exp):
    return (
        f"Despesa: {exp['descricao']} | "
        f"Vencimento: dia {exp['vencimento_dia']} | "
        f"Valor: {exp['valor']} | "
        f"Status: {exp['status']} | "
        f"Referencia: {exp['referencia']} | "
        f"Categoria: {exp['categoria']}"
    )

# transforma todas despesas em textos
documents = [expense_to_text(e) for e in expenses]

# debug documentos pra não ter nenhum vazio
print(f"Total documentos para embedding: {len(documents)}")
for i, d in enumerate(documents):
    if not d or str(d).strip() == "":
        print("Documento inválido na posição", i, d)

expense_objects = expenses

# ----------- gerar embeddings  reais ----------------------
def embed_texts(texts: list[str]) -> np.ndarray:
    # garante que só vai string válida e não vazia
    clean_texts = [
        str(t).strip()
        for t in texts
        if t is not None and str(t).strip() != ""
    ]

    if len(clean_texts) == 0:
        raise ValueError("Nenhum texto válido para gerar embeddings")

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=clean_texts
    )

    vectors = [item.embedding for item in response.data]
    return np.array(vectors).astype("float32")

doc_vectors = embed_texts(documents)

# -------- FAISS em memória (ainda com vetores fake) --------

DIM = doc_vectors.shape[1]
index = faiss.IndexFlatL2(DIM)
index.add(doc_vectors)

# -----------------------------------------------------------

class Question(BaseModel):
    question: str

@app.get("/")
def root():
    return {"message": "RAG financeiro rodando com despesas indexadas"}

@app.post("/ask")
def ask(q: Question):

    # embedding real da pergunta
    query_vec = embed_texts([q.question])

    distances, indices, = index.search(query_vec, k=500)
    
    results = []
    selected_expenses = []

    # detecta se a pergunta é sobre cartão de crédito
    is_credit_card_query = (
        "cartão" in q.question.lower() or
        "credito" in q.question.lower() or
        "crédito" in q.question.lower()
    )

    THRESHOLD = 1.05

    for d, i in zip(distances[0], indices[0]):
        if d <= THRESHOLD:
            exp = expense_objects[i]

            # se for pergunta de cartão, só aceita categoria de cartão
            if is_credit_card_query and exp["categoria"] not in ["cartao_credito"]:
                continue

            results.append(documents[i])
            selected_expenses.append(exp)

    #context = "\n".join(results)
    prompt = f"""
    Use apenas as despesas abaixo para responder.

    Despesas encontradas:
    {results}

    Pergunta do usuário:
    {q.question}
    """

    resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
    )

    answer = resp.output_text

    return {
        "question": q.question,
        "answer": answer,
        "usados_como_contexto": results
    }
