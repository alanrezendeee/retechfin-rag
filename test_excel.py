from excel_loader import load_expenses_from_excel

expenses = load_expenses_from_excel("financas_2025.xlsx")

print (f"Total carregado: {len(expenses)}")

for e in expenses[:10]:
    print(e)
