import os
import re
import json
import random
from PIL import Image
from google import genai
from app.utils.strings import get_string
from app.config import Config

class AIService:
    @staticmethod
    def get_client():
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in configuration.")
        return genai.Client(api_key=Config.GEMINI_API_KEY)

    @staticmethod
    def recognize_receipt(file_stream, existing_categories, user_prompt=None):
        try:
            cat_names_str = ",\n".join([c.name for c in existing_categories])
            img = Image.open(file_stream)
            client = AIService.get_client()

            prompt = get_string('ai_prompts')['base_receipt']
            prompt += f"\nОСЬ ІСНУЮЧІ КАТЕГОРІЇ КОРИСТУВАЧА:\n[{cat_names_str}]\n"
            prompt += "Твоє завдання — підібрати НАЙБІЛЬШ ВІДПОВІДНУ категорію з існуючих.\n"

            if user_prompt:
                prompt += f"\n🚨 ДОДАТКОВІ ВКАЗІВКИ ВІД КОРИСТУВАЧА:\n{user_prompt}\n"

            prompt += """\nПоверни результат СУВОРО як валідний JSON масив.
            Приклад:
            [ {"type": "Витрата", "amount": 345.50, "category": "🛒 Супермаркет", "description": "АТБ", "date": "2026-03-18"} ]
            """

            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=[img, prompt],
                config=genai.types.GenerateContentConfig(temperature=0.1)
            )
            raw_text = response.text.strip()
            
            if raw_text.startswith('```'):
                raw_text = re.sub(r'^```[a-zA-Z]*\n', '', raw_text)
                raw_text = re.sub(r'\n```$', '', raw_text)
            
            match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if match: raw_text = match.group(0)

            data = json.loads(raw_text)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"AI Recognition Error: {e}")
            return []
    @staticmethod
    def parse_csv_statement(csv_text):
        try:
            client = AIService.get_client()
            prompt = f"""
            You are a financial data parser. I will provide you with a CSV text of a bank statement.
            Your task is to extract all transactions and return them STRICTLY as a JSON array.
            Do not include any Markdown formatting like ```json or anything else. Just the raw JSON array.
            
            Format each transaction like this:
            [ {{"type": "Витрата", "amount": 345.50, "category": "🛒 Супермаркет", "description": "Сільпо", "date": "2026-03-18"}} ]
            
            Rules:
            1. 'type' must be either "Витрата" (for expenses/negative amounts) or "Дохід" (for income/positive amounts).
            2. 'amount' must be a positive float number.
            3. 'date' must be in YYYY-MM-DD format.
            4. Guess the best 'category' based on the description (e.g., '🚕 Транспорт', '🍔 Ресторани', '🛒 Супермаркет', '💡 Комуналка', '💰 Зарплата').
            
            CSV DATA:
            {csv_text}
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt,
                config=genai.types.GenerateContentConfig(temperature=0.1)
            )
            raw_text = response.text.strip()
            if raw_text.startswith('```'):
                raw_text = re.sub(r'^```[a-zA-Z]*\n', '', raw_text)
                raw_text = re.sub(r'\n```$', '', raw_text)
            
            match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if match: raw_text = match.group(0)

            data = json.loads(raw_text)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"CSV Parse Error: {e}")
            return []

    @staticmethod
    def analyze_finance(user_data, analysis_type):
        try:
            client = AIService.get_client()
            lang = user_data.get('lang', 'uk')
            prompts = get_string('ai_prompts')
            
            # Определяем задачу: либо стандартный промпт, либо кастомный запрос пользователя
            if analysis_type == 'custom' and user_data.get('user_query'):
                task = f"ANSWER THE USER'S SPECIFIC QUESTION: {user_data['user_query']}"
            else:
                task = prompts.get(f'analytics_{analysis_type}', "Give financial advice.")

            system_instruction = "You are a senior financial analyst and behavioral economist specialist. "
            if lang == 'uk':
                system_instruction = "Ти — провідний фінансовий аналітик та спеціаліст з поведінкової економіки. "

            prompt = f"{system_instruction} Client: {user_data['username']}. "
            prompt += f"Type: {user_data['context_prefix']}. Period: last {user_data['period_days']} days.\n"
            prompt += f"DATA:\n- Balance: {user_data['total_balance']} {user_data.get('currency', '₴')}\n"
            prompt += f"- Income: {user_data['income']} {user_data.get('currency', '₴')}\n"
            prompt += f"- Expenses: {user_data['expenses']} {user_data.get('currency', '₴')}\n"
            prompt += f"- Daily Avg: {user_data.get('daily_avg', 0)} {user_data.get('currency', '₴')}\n"
            prompt += f"- Runway: {user_data.get('runway', 0)} days\n"
            prompt += f"- Trend: {user_data.get('trend_percent', 0)}% compared to prev period\n"
            prompt += f"GOALS:\n{user_data['goals_list']}\nCATEGORIES:\n{user_data['cat_totals']}\n"
            prompt += f"TRANSACTIONS:\n{user_data['tx_list']}\n"
            prompt += f"TASK:\n{task}\n"

            lang_instruction = "IMPORTANT: Write your response ONLY in Ukrainian language." if lang == 'uk' else "IMPORTANT: Write your response ONLY in English language."
            prompt += f"\n{lang_instruction}\n"
            prompt += "Write clearly, max 8-10 sentences. Be specific and helpful based on the data provided."

            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt,
                config=genai.types.GenerateContentConfig(temperature=0.7)
            )
            return response.text.replace('**', '').replace('*', '• ').replace('\n', '<br>')
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            raise e
