from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import faiss
import os
import json
from openai import OpenAI
from excel_loader import load_expenses_from_excel

app = FastAPI()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

expenses = load_expenses_from_excel("financas_2025.xlsx")
expense_objects = expenses

# -----------------------------
# Utils
# -----------------------------

def normalize_operation(op: str | None) -> str:
    """
    Retorna o tipo de pipeline:
    - deterministic: operações numéricas/precisas
    - semantic: perguntas abertas / busca / explicação
    """
    if not op:
        return "semantic"

    op = op.lower()

    # qualquer coisa que envolva cálculo/estatística precisa ser determinística
    if any(x in op for x in [
        "total", "sum", "count", "average", "media", "média", "max", "min",
        "total_pago", "total_pendente", "total_aberto"
    ]):
        return "deterministic"

    return "semantic"


def expense_to_text(exp: dict) -> str:
    return (
        f"Despesa: {exp['descricao']} | "
        f"Vencimento: dia {exp['vencimento_dia']} | "
        f"Valor: {exp['valor']} | "
        f"Status: {exp['status']} | "
        f"Referencia: {exp['referencia']} | "
        f"Categoria: {exp['categoria']}"
    )


def dynamic_k(n: int, min_k=8, max_k=120, ratio=0.10) -> int:
    """
    k dinâmico para pipeline semântico.
    Para n pequeno, devolve n. Para n grande, limita por max_k.
    """
    if n <= min_k:
        return n
    k = int(n * ratio)
    k = max(min_k, k)
    k = min(max_k, k)
    k = min(k, n)
    return k


def parse_query_with_llm(question: str) -> dict:
    """
    Parser simples (MVP) mas mais estável:
    - força operation a um conjunto pequeno de valores
    - extrai filtros básicos
    """
    default_filters = {
        "vendor_contains": None,
        "referencia_mes": None,
        "status": None,
        "categoria": None,
        "operation": "search",  # search | list | total | total_pago | total_pendente
    }

    prompt = f"""
Extraia filtros estruturados da pergunta sobre despesas.
Retorne APENAS um JSON válido (sem texto antes/depois).

Campos:
- vendor_contains: string ou null (ex: "Bruno", "The Retech")
- referencia_mes: string ou null (ex: "Janeiro", "Março")
- status: string ou null (ex: "Pago", "Pendente")
- categoria: string ou null (ex: "cartao_credito", "energia", "aluguel")
- operation: UMA destas opções:
    "search", "list", "total", "total_pago", "total_pendente"

Regras para operation:
- Se pedir "total", "quanto", "soma" -> "total"
- Se pedir "total pago", "quanto paguei", "pago" -> "total_pago"
- Se pedir "pendente", "em aberto" -> "total_pendente"
- Se pedir "quais", "listar", "mostre" -> "list"
- Caso contrário -> "search"

Pergunta: {question}
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return default_filters

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return default_filters

    # garante chaves
    for k in default_filters:
        if k not in data:
            data[k] = default_filters[k]

    # normaliza operation para valores conhecidos
    op = (data.get("operation") or "search").lower()
    allowed = {"search", "list", "total", "total_pago", "total_pendente"}
    if op not in allowed:
        # heurística mínima
        if "total" in op or "sum" in op:
            op = "total"
        elif "list" in op:
            op = "list"
        else:
            op = "search"
    data["operation"] = op

    return data


def embed_texts(texts: list[str]) -> np.ndarray:
    clean_texts = [str(t).strip() for t in texts if t is not None and str(t).strip() != ""]
    if len(clean_texts) == 0:
        raise ValueError("Nenhum texto válido para gerar embeddings")

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=clean_texts
    )
    vectors = [item.embedding for item in response.data]
    return np.array(vectors).astype("float32")


# -----------------------------
# Indexação (global)
# -----------------------------

documents = [expense_to_text(e) for e in expenses]

print(f"Total documentos para embedding: {len(documents)}")
for i, d in enumerate(documents):
    if not d or str(d).strip() == "":
        print("Documento inválido na posição", i, d)

doc_vectors = embed_texts(documents)

DIM = doc_vectors.shape[1]
index = faiss.IndexFlatL2(DIM)
index.add(doc_vectors)


# -----------------------------
# API
# -----------------------------

class Question(BaseModel):
    question: str


@app.get("/")
def root():
    return {"message": "RAG financeiro rodando com despesas indexadas"}


@app.post("/ask")
def ask(q: Question):

    # 1) Query Understanding
    filters = parse_query_with_llm(q.question)
    print(f"Filtros: {filters}")

    operation = filters.get("operation", "search")
    operation_type = normalize_operation(operation)

    # 2) Pré-filtro estruturado (para reduzir universo)
    candidates = []
    for exp in expense_objects:
        ok = True

        if filters.get("vendor_contains"):
            if filters["vendor_contains"].lower() not in exp["descricao"].lower():
                ok = False

        if filters.get("referencia_mes"):
            if filters["referencia_mes"].lower() not in str(exp["referencia"]).lower():
                ok = False

        if filters.get("status"):
            if filters["status"].lower() not in str(exp["status"]).lower():
                ok = False

        if filters.get("categoria"):
            if filters["categoria"].lower() != str(exp["categoria"]).lower():
                ok = False

        if ok:
            candidates.append(exp)

    if len(candidates) == 0:
        candidates = expense_objects

    # -----------------------------
    # 3) PIPELINE DETERMINÍSTICO
    # -----------------------------
    if operation_type == "deterministic":

        # Dataset COMPLETO: não usa FAISS para decidir o conjunto
        selected_expenses = candidates
        results = [expense_to_text(e) for e in selected_expenses]

        # regras simples (MVP) por operation
        if operation in ["total", "total_pago", "total_pendente"]:

            # filtra por status quando aplicável
            if operation == "total_pago":
                selected_expenses = [e for e in selected_expenses if str(e.get("status", "")).lower() == "pago"]
            elif operation == "total_pendente":
                # ajusta conforme seu padrão de status (pendente/em aberto/etc)
                selected_expenses = [e for e in selected_expenses if str(e.get("status", "")).lower() in ["pendente", "em aberto", "aberto"]]

            results = [expense_to_text(e) for e in selected_expenses]
            total = sum(float(e["valor"]) for e in selected_expenses)

            prompt = f"""
O usuário perguntou:
{q.question}

O total calculado com precisão foi:
R$ {total:,.2f}

Explique de forma natural e profissional.
Não recalcule valores.
Se não houver itens, diga que não encontrou despesas no filtro aplicado.
"""

            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.choices[0].message.content or ""

            return {
                "question": q.question,
                "filters_usados": filters,
                "answer": answer,
                "usados_como_contexto": results
            }

        # fallback determinístico: se cair aqui, trata como list
        operation_type = "semantic"

    # -----------------------------
    # 4) PIPELINE SEMÂNTICO
    # -----------------------------

    # Aqui sim faz sentido FAISS e k dinâmico
    query_vec = embed_texts([q.question])

    # "k grande" para recall no index global, mas ainda controlado
    # depois filtramos para ficar apenas no conjunto "candidates"
    global_k = 200  # recall; pode ajustar
    distances, indices = index.search(query_vec, k=min(global_k, len(documents)))

    # cria um set rápido de ids válidos (candidates)
    candidate_ids = set(id(exp) for exp in candidates)
    results = []
    selected_expenses = []

    for i in indices[0]:
        exp = expense_objects[i]
        if id(exp) not in candidate_ids:
            continue
        results.append(documents[i])
        selected_expenses.append(exp)

    # aplica k dinâmico na lista final (após filtro)
    k_final = dynamic_k(len(results))
    results = results[:k_final]
    selected_expenses = selected_expenses[:k_final]

    prompt = f"""
Use apenas as despesas abaixo para responder.

Despesas encontradas:
{results}

Pergunta do usuário:
{q.question}
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    answer = resp.choices[0].message.content or ""

    return {
        "question": q.question,
        "filters_usados": filters,
        "answer": answer,
        "usados_como_contexto": results
    }
