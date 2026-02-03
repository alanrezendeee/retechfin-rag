# ReTechFin RAG

RAG (Retrieval-Augmented Generation) para consultas sobre despesas financeiras. O projeto carrega dados de uma planilha Excel, indexa com embeddings + FAISS e responde perguntas em linguagem natural via API.

## Pré-requisitos

- **Python 3.11+** (recomendado 3.11 ou 3.12)
- **Chave da API OpenAI** ([criar aqui](https://platform.openai.com/api-keys))
- Planilha de despesas no formato esperado (veja [Estrutura da planilha](#estrutura-da-planilha))

## Passo a passo para rodar o projeto

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd retechfin-rag
```

### 2. Criar o ambiente virtual (venv)

O ambiente virtual isola as dependências do projeto do resto do Python instalado no seu computador.

**No macOS/Linux:**

```bash
python3 -m venv .venv
```

**No Windows (PowerShell):**

```powershell
python -m venv .venv
```

Se der erro tipo "python3 não encontrado", tente apenas `python` no lugar de `python3`.

### 3. Ativar o ambiente virtual

Enquanto o venv estiver ativo, o terminal usa o Python e os pacotes desse projeto.

**No macOS/Linux:**

```bash
source .venv/bin/activate
```

**No Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**No Windows (CMD):**

```cmd
.venv\Scripts\activate.bat
```

Quando ativado, o início da linha do terminal costuma mostrar `(.venv)`.

### 4. Instalar as dependências

Ainda com o venv ativo:

```bash
pip install -r requirements.txt
```

### 5. Configurar a chave da API OpenAI

A aplicação usa a variável de ambiente `OPENAI_API_KEY`.

**macOS/Linux (temporário, só nesta sessão do terminal):**

```bash
export OPENAI_API_KEY="sua-chave-aqui"
```

**Windows (PowerShell, temporário):**

```powershell
$env:OPENAI_API_KEY = "sua-chave-aqui"
```

Para não precisar exportar toda vez, você pode colocar a linha no seu `~/.bashrc`, `~/.zshrc` ou no perfil do PowerShell.

### 6. Colocar a planilha no lugar

Deixe o arquivo **`financas_2025.xlsx`** na raiz do projeto (mesma pasta do `main.py`). Se o nome ou o caminho for outro, será preciso ajustar no código onde a planilha é carregada.

### 7. Subir o servidor

```bash
uvicorn main:app --reload
```

- `--reload`: reinicia o servidor quando você alterar arquivos (útil em desenvolvimento).

Você deve ver algo como:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 8. Testar a API

- **Documentação interativa (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Raiz:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/) — retorna uma mensagem de status.
- **Perguntar (POST /ask):** no Swagger, use o endpoint `POST /ask` com um body JSON, por exemplo:

```json
{
  "question": "Quais são as despesas de janeiro?"
}
```

## Estrutura da planilha

O Excel deve ter abas (uma por mês ou referência) e colunas:

| Coluna   | Descrição                          |
|----------|------------------------------------|
| Despesas | Nome/descrição da despesa          |
| Vcto     | Dia do vencimento (número)         |
| Valor    | Valor numérico                     |
| Status   | Ex.: Pago, Pendente                |
| Categoria| Opcional; se vazia, é inferida     |

## Variáveis de ambiente

| Variável         | Obrigatória | Descrição                    |
|------------------|-------------|-----------------------------|
| `OPENAI_API_KEY` | Sim         | Chave da API OpenAI         |

## Tecnologias

- **FastAPI** — API HTTP
- **OpenAI** — embeddings e modelo (Chat Completions)
- **FAISS** — busca por similaridade
- **Pandas / openpyxl** — leitura do Excel

## Licença

[Defina conforme o seu projeto.]
