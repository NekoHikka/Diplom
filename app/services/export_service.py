import pandas as pd
from io import BytesIO
from app.utils.strings import get_string

class ExportService:
    @staticmethod
    def export_to_excel(transactions, accounts, goals, filter_type, lang='uk'):
        # Локализация заголовков
        labels = {
            'date': 'Date' if lang == 'en' else 'Дата',
            'account': 'Account' if lang == 'en' else 'Рахунок',
            'type': 'Type' if lang == 'en' else 'Тип',
            'category': 'Category' if lang == 'en' else 'Категорія',
            'amount': 'Amount' if lang == 'en' else 'Сума',
            'desc': 'Description' if lang == 'en' else 'Опис',
            'balance': 'Balance' if lang == 'en' else 'Баланс',
            'target': 'Target' if lang == 'en' else 'Ціль',
            'progress': 'Progress' if lang == 'en' else 'Прогрес',
            'name': 'Name' if lang == 'en' else 'Назва',
            'sheet_tx': 'Transactions' if lang == 'en' else 'Транзакції',
            'sheet_acc': 'Accounts' if lang == 'en' else 'Рахунки',
            'sheet_goals': 'Goals' if lang == 'en' else 'Цілі'
        }

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 1. Лист транзакций
            tx_data = []
            for t in transactions:
                tx_data.append({
                    labels['date']: t.date.strftime('%Y-%m-%d'),
                    labels['account']: t.account.name if t.account else '---',
                    labels['type']: t.type,
                    labels['category']: t.category,
                    labels['amount']: t.amount,
                    labels['desc']: t.description or ''
                })
            df_tx = pd.DataFrame(tx_data)
            df_tx.to_excel(writer, index=False, sheet_name=labels['sheet_tx'])

            # 2. Лист счетов
            acc_data = []
            for a in accounts:
                acc_data.append({
                    labels['name']: a.name,
                    labels['balance']: a.balance
                })
            df_acc = pd.DataFrame(acc_data)
            df_acc.to_excel(writer, index=False, sheet_name=labels['sheet_acc'])

            # 3. Лист целей
            goal_data = []
            for g in goals:
                # Рассчитываем текущий прогресс (упрощенно - общий баланс)
                # В реальной логике можно считать по привязанным аккаунтам
                goal_data.append({
                    labels['name']: g.name,
                    labels['target']: g.target_amount,
                    labels['account']: g.account_ids
                })
            df_goals = pd.DataFrame(goal_data)
            df_goals.to_excel(writer, index=False, sheet_name=labels['sheet_goals'])

            # Форматирование (ширина колонок)
            for sheet in [labels['sheet_tx'], labels['sheet_acc'], labels['sheet_goals']]:
                worksheet = writer.sheets[sheet]
                worksheet.set_column('A:F', 20)

        output.seek(0)
        return output
