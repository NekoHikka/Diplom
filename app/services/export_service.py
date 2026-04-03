import pandas as pd
from io import BytesIO

class ExportService:
    @staticmethod
    def export_to_excel(transactions, filter_type):
        data = []
        for t in transactions:
            cat_clean = t.category.split(' ', 1)[-1] if ' ' in t.category else t.category
            acc_clean = t.account.name.split(' ', 1)[-1] if t.account and ' ' in t.account.name else (t.account.name if t.account else '---')
            data.append({
                'Дата': t.date.strftime('%Y-%m-%d'),
                'Рахунок': acc_clean,
                'Тип': t.type,
                'Категорія': cat_clean,
                'Сума (ГРН)': t.amount,
                'Опис': t.description
            })
            
        columns = ['Дата', 'Рахунок', 'Тип', 'Категорія', 'Сума (ГРН)', 'Опис']
        df = pd.DataFrame(data, columns=columns)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Виписка ({filter_type})')
        output.seek(0)
        return output
