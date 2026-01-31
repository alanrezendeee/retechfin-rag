import pandas as pd

def inferir_categoria(descricao: str) -> str:
    d = descricao.lower()
    if "cartão" in d or "credito" in d or "crédito" in d:
        return "cartao_credito"
    if "celesc" in d or "luz" in d or "energia" in d:
        return "energia"
    return "outros"

def load_expenses_from_excel(path: str):
    xls = pd.ExcelFile(path)

    all_expenses = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        # espera colunas exatamente assim
        # Despesas | Vcto | Valor | Status | Categoria
        for _, row in df.iterrows():
            descricao = row.get("Despesas")
            if pd.isna(descricao):
                continue

            valor = row.get("Valor")
            if pd.isna(valor):
                continue

            venc = row.get("Vcto")
            status = row.get("Status")
            categoria_planilha = row.get("Categoria")

            if pd.isna(categoria_planilha) or str(categoria_planilha).strip() == "":
                categoria = inferir_categoria(str(descricao))
            else:
                categoria = str(categoria_planilha).strip().lower()


            expense = {
                "descricao": str(descricao),
                "vencimento_dia": int(venc) if not pd.isna(venc) else None,
                "valor": float(valor),
                "status": str(status) if not pd.isna(status) else "",
                "referencia": sheet, # nome da aba = mês
                "categoria": categoria
            }

            all_expenses.append(expense)

    return all_expenses
