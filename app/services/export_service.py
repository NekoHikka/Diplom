from io import BytesIO

import pandas as pd

from app.utils.strings import get_string, translate_name


class ExportService:
    @staticmethod
    def _plain_name(value, fallback="---"):
        name = translate_name(value or "").strip()
        return name or fallback

    @staticmethod
    def _format_type(value, lang):
        if value in ("Income", "Дохід"):
            return "Income" if lang == "en" else "Дохід"
        if value in ("Expense", "Витрата"):
            return "Expense" if lang == "en" else "Витрата"
        return value

    @staticmethod
    def _format_goal_accounts(goal, accounts, lang):
        if not goal.account_ids or goal.account_ids == "all":
            return get_string('all_accs_pill', lang=lang)

        accounts_by_id = {str(account.id): account for account in accounts}
        names = []
        for account_id in str(goal.account_ids).split(","):
            account = accounts_by_id.get(account_id.strip())
            if account:
                names.append(ExportService._plain_name(account.name))

        return ", ".join(names) if names else goal.account_ids

    @staticmethod
    def export_to_excel(transactions, accounts, goals, filter_type, lang="uk"):
        labels = {
            "date": "Date" if lang == "en" else "Дата",
            "account": "Account" if lang == "en" else "Рахунок",
            "type": "Type" if lang == "en" else "Тип",
            "category": "Category" if lang == "en" else "Категорія",
            "amount": "Amount" if lang == "en" else "Сума",
            "desc": "Description" if lang == "en" else "Опис",
            "balance": "Balance" if lang == "en" else "Баланс",
            "target": "Target" if lang == "en" else "Ціль",
            "name": "Name" if lang == "en" else "Назва",
            "sheet_tx": "Transactions" if lang == "en" else "Транзакції",
            "sheet_acc": "Accounts" if lang == "en" else "Рахунки",
            "sheet_goals": "Goals" if lang == "en" else "Цілі",
        }

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            tx_data = []
            for transaction in transactions:
                tx_data.append(
                    {
                        labels["date"]: transaction.date.strftime("%Y-%m-%d"),
                        labels["account"]: ExportService._plain_name(
                            transaction.account.name if transaction.account else ""
                        ),
                        labels["type"]: ExportService._format_type(transaction.type, lang),
                        labels["category"]: ExportService._plain_name(transaction.category),
                        labels["amount"]: transaction.amount,
                        labels["desc"]: transaction.description or "",
                    }
                )
            pd.DataFrame(tx_data).to_excel(writer, index=False, sheet_name=labels["sheet_tx"])

            acc_data = []
            for account in accounts:
                acc_data.append(
                    {
                        labels["name"]: ExportService._plain_name(account.name),
                        labels["balance"]: account.balance,
                    }
                )
            pd.DataFrame(acc_data).to_excel(writer, index=False, sheet_name=labels["sheet_acc"])

            goal_data = []
            for goal in goals:
                goal_data.append(
                    {
                        labels["name"]: goal.name,
                        labels["target"]: goal.target_amount,
                        labels["account"]: ExportService._format_goal_accounts(goal, accounts, lang),
                    }
                )
            pd.DataFrame(goal_data).to_excel(writer, index=False, sheet_name=labels["sheet_goals"])

            for sheet in [labels["sheet_tx"], labels["sheet_acc"], labels["sheet_goals"]]:
                worksheet = writer.sheets[sheet]
                worksheet.set_column("A:F", 20)

        output.seek(0)
        return output
