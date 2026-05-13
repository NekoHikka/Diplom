import os
import re
import json
import random
import time
import requests
from PIL import Image
from google import genai
from google.genai import errors
from app.utils.strings import get_string
from app.utils.icons import display_item_name, icon_value, infer_icon_id
from app.config import Config

class AIService:
    QUOTA_EXHAUSTED = "__AI_QUOTA_EXHAUSTED__"
    RECEIPT_MODELS = ("gemini-3.1-flash-lite", "gemini-2.5-flash")

    @staticmethod
    def _category_reference(existing_categories):
        refs = []
        for c in existing_categories or []:
            refs.append({
                "exact": c.name,
                "display": display_item_name(c.name),
                "type": c.type,
            })
        return refs

    @staticmethod
    def _normalize_category_choice(value, category_refs):
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        exact_map = {ref["exact"]: ref["exact"] for ref in category_refs}
        display_map = {ref["display"].lower(): ref["exact"] for ref in category_refs}
        if value in exact_map:
            return value
        display = display_item_name(value).strip()
        if display.lower() in display_map:
            return display_map[display.lower()]
        if value.startswith("icon:"):
            head, _, tail = value.partition(" ")
            return f"{head} {display_item_name(tail or value).strip()}".strip()
        icon_id = infer_icon_id(display, fallback="folder")
        return f"{icon_value(icon_id)} {display or 'Інше'}"

    @staticmethod
    def get_client():
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in configuration.")
        return genai.Client(api_key=Config.GEMINI_API_KEY)

    @staticmethod
    def _is_quota_error(error):
        error_text = str(error).lower()
        return "resource_exhausted" in error_text or "429" in error_text or "quota" in error_text

    @staticmethod
    def _call_openrouter(prompt, model, temperature=0.7):
        """Unified method for OpenRouter API calls."""
        if not Config.OPENROUTER_API_KEY:
            print("Error: OPENROUTER_API_KEY is not set.")
            return None
        
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://github.com/google/gemini-cli", # Required for OpenRouter
                    "X-Title": "Finance App",
                },
                data=json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature
                }),
                timeout=180  # 3 minutes для ии
            )
            response.raise_for_status()
            res_json = response.json()
            if 'choices' in res_json and len(res_json['choices']) > 0:
                content = res_json['choices'][0]['message']['content']
                print(f"OpenRouter raw content (first 100): {str(content)[:100]}")
                return content
            print(f"OpenRouter empty response: {res_json}")
            return None
        except requests.exceptions.Timeout:
            print(f"OpenRouter Timeout ({model}): request exceeded 180s")
            return None
        except Exception as e:
            print(f"OpenRouter Error ({model}): {e}")
            return None

    @staticmethod
    def _clean_json_response(raw_text):
        """Extract JSON from potential markdown/text formatting."""
        if not raw_text: return ""
        raw_text = raw_text.strip()
        if raw_text.startswith('```'):
            raw_text = re.sub(r'^```[a-zA-Z]*\n', '', raw_text)
            raw_text = re.sub(r'\n```$', '', raw_text)
        match = re.search(r'\[.*\]|\{.*\}', raw_text, re.DOTALL)
        return match.group(0) if match else raw_text

    @staticmethod
    def recognize_receipt(file_stream, existing_categories, user_prompt=None):
        try:
            category_refs = AIService._category_reference(existing_categories)
            cat_names_str = json.dumps(category_refs, ensure_ascii=False)
            img = Image.open(file_stream)
            client = AIService.get_client()

            prompt = get_string('ai_prompts')['base_receipt']
            prompt += f"\nОСЬ ІСНУЮЧІ КАТЕГОРІЇ КОРИСТУВАЧА:\n{cat_names_str}\n"
            prompt += "Твоє завдання — підібрати НАЙБІЛЬШ ВІДПОВІДНУ категорію з існуючих. Якщо підходить існуюча категорія, повертай її поле exact повністю, включно з icon:... префіксом. Якщо не підходить жодна, створи коротку назву без emoji, без icon: і без декоративних символів.\n"

            if user_prompt:
                prompt += f"\n🚨 ДОДАТКОВІ ВКАЗІВКИ ВІД КОРИСТУВАЧА:\n{user_prompt}\n"

            prompt += """\nПоверни результат СУВОРО як валідний JSON масив.
            Приклад:
            [ {"type": "Витрата", "amount": 345.50, "category": "icon:cart Супермаркет", "description": "АТБ", "date": "2026-03-18"} ]
            """

            last_quota_error = None
            for model in AIService.RECEIPT_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[img, prompt],
                        config=genai.types.GenerateContentConfig(temperature=0.1)
                    )
                    raw_text = AIService._clean_json_response(response.text)
                    data = json.loads(raw_text)
                    return data if isinstance(data, list) else []
                except Exception as model_error:
                    print(f"AI Recognition Error ({model}): {model_error}")
                    if AIService._is_quota_error(model_error):
                        last_quota_error = model_error
                    continue

            if last_quota_error:
                return AIService.QUOTA_EXHAUSTED
            return []
        except Exception as e:
            print(f"AI Recognition Error: {e}")
            if AIService._is_quota_error(e):
                return AIService.QUOTA_EXHAUSTED
            return []

    @staticmethod
    def parse_statement(text, existing_categories=None, is_xlsx=False):
        try:
            category_names = json.dumps(AIService._category_reference(existing_categories), ensure_ascii=False)

            lines = [l for l in text.split('\n') if l.strip()]  # drop blank lines

            # --- Chunking for large files ---
            # Free models typically support ~4K-8K tokens. ~6000 chars is a safe limit.
            CHAR_LIMIT = 6000
            CHUNK_ROWS = 40   # data rows per chunk (excluding header)

            if len(text) > CHAR_LIMIT and len(lines) > CHUNK_ROWS + 2:
                print(f"Large file detected ({len(text)} chars, {len(lines)} lines) — chunking into batches of {CHUNK_ROWS} rows")
                # First line is likely a header row; keep it for each chunk
                header = lines[0]
                data_lines = lines[1:]
                chunks = [data_lines[i:i+CHUNK_ROWS] for i in range(0, len(data_lines), CHUNK_ROWS)]

                all_transactions = []
                balance = None
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_text = header + '\n' + '\n'.join(chunk)
                    print(f"  Chunk {chunk_idx+1}/{len(chunks)}: {len(chunk)} rows, {len(chunk_text)} chars")
                    txs, bal = AIService._parse_chunk(chunk_text, category_names)
                    if txs:
                        all_transactions.extend(txs)
                    if bal is not None:
                        balance = bal  # keep last balance value

                print(f"Chunked result: {len(all_transactions)} total transactions")
                return all_transactions, balance
            else:
                # Small enough — single call
                return AIService._parse_chunk(text, category_names)

        except Exception as e:
            print(f"Statement Parse Error: {e}")
            import traceback; traceback.print_exc()
            return None, None

    @staticmethod
    def _parse_chunk(text, category_names):
        """Call AI for a single chunk of bank statement text."""
        try:
            prompt = f"""You are a precise data extraction API. Your ONLY task is to parse bank statement text into a JSON array.
You MUST output ONLY a valid JSON array and absolutely NO other text, markdown formatting (like ```json), comments, or conversational responses. If you fail to do this, the system will crash.
If no transactions are found in the text, you MUST return exactly this string: []

TRANSACTION FORMAT (each item in the array MUST strictly follow this):
{{
    "type": "Витрата" or "Дохід",
    "amount": NUMBER (positive float, e.g. 150.50),
    "category": "NAME",
    "description": "TEXT",
    "date": "YYYY-MM-DD"
}}

RULES & NUANCES:
1. "type": Use EXACTLY "Витрата" for spending/expenses, and "Дохід" for incoming money/deposits. 
   - Look for keywords like "Мінус", "Списання", "Купівля", "Видача" for "Витрата".
   - Look for keywords like "Плюс", "Поповнення", "Зарахування", "Переказ" (if positive) for "Дохід".
2. "amount": MUST be a positive number. Remove any negative signs, currency symbols (грн, UAH), or thousand separators (spaces/commas).
3. "date": Convert all dates to standard YYYY-MM-DD format. Look for formats like DD.MM.YYYY or DD.MM.
4. "category": You MUST try to use exactly one of these existing categories if it matches: {category_names}. Existing categories have "exact" and "display"; return "exact" when there is a match, including icon:... prefix. If no category fits, create a short plain category name without emoji and without icon: prefix (e.g. "Продукти"). The app will add the SVG icon later.
5. "description": Keep it short but descriptive. Extract the actual merchant name or purpose. Remove excess numbers or technical bank codes.
6. BALANCE: If you see the final balance on the account in the text (often called "Кінцевий залишок", "Залишок", "Balance"), append one special object at the end of the array formatted exactly like this: {{"type": "BALANCE", "amount": X}}

DATA SOURCE:
---
{text}
---
"""
            primary_model = "openai/gpt-oss-120b:free"
            fallback_model = "meta-llama/llama-3.3-70b-instruct:free"

            def _call_ai(temp=0.0):
                print(f"Calling OpenRouter Primary ({primary_model}, temp={temp})...")
                res = AIService._call_openrouter(prompt, primary_model, temperature=temp)
                if res is None:
                    print(f"Primary failed (None), calling OpenRouter Fallback ({fallback_model})...")
                    res = AIService._call_openrouter(prompt, fallback_model, temperature=temp)
                return res

            raw_text = _call_ai(temp=0.0)
            print(f"AI Response Attempt 1: {raw_text[:200] if raw_text else 'None'}")
            
            # Retry ONLY if the network/API completely failed (None), not if AI returned []
            # [] means AI found no transactions — that is a valid answer, do not re-query
            if raw_text is None:
                if len(text) > 100:
                    print("First attempt returned None (network/API failure), retrying with fallback...")
                    raw_text = _call_ai(temp=0.2)
                    print(f"AI Response Attempt 2: {raw_text[:200] if raw_text else 'None'}")

            if raw_text is None:
                return None, None
            
            cleaned_text = AIService._clean_json_response(raw_text)
            print(f"Cleaned AI Response: {cleaned_text[:200]}")
            if not cleaned_text or cleaned_text.strip() == "":
                return [], None

            data = json.loads(cleaned_text)
            print(f"Parsed {len(data) if isinstance(data, list) else '0'} items from AI")
            if isinstance(data, list):
                balance = None
                filtered = []
                for item in data:
                    if isinstance(item, dict):
                        if item.get('type') == 'BALANCE':
                            try: balance = float(item.get('amount', 0))
                            except: pass
                        else:
                            filtered.append(item)
                return filtered, balance
            return [], None
        except Exception as e:
            print(f"Chunk Parse Error: {e}")
            import traceback; traceback.print_exc()
            return None, None

    @staticmethod
    def choose_existing_categories(transactions, existing_categories):
        if not transactions or not existing_categories:
            return {}
        try:
            CHUNK_SIZE = 50  # max transactions per AI call
            category_refs = AIService._category_reference(existing_categories)
            category_names = category_refs
            compact_transactions = []
            for idx, tx in enumerate(transactions):
                compact_transactions.append({
                    "id": idx,
                    "type": tx.get("type"),
                    "suggested_category": tx.get("category"),
                    "description": tx.get("description", ""),
                    "amount": tx.get("amount"),
                })

            # Split into chunks if needed
            chunks = [compact_transactions[i:i+CHUNK_SIZE]
                      for i in range(0, len(compact_transactions), CHUNK_SIZE)]

            merged = {}
            for chunk_idx, chunk in enumerate(chunks):
                print(f"  Categorizing chunk {chunk_idx+1}/{len(chunks)} ({len(chunk)} txs)...")
                result = AIService._categorize_chunk(chunk, category_names)
                merged.update(result)

            return merged
        except Exception as e:
            print(f"AI category choice error: {e}")
            return {}

    @staticmethod
    def _categorize_chunk(compact_transactions, category_names):
        """Categorize a single chunk of transactions."""
        try:
            category_refs = category_names
            prompt = f"""You are a Ukrainian finance app categorization assistant.

Your job: assign the best category to each transaction.

RULES:
1. Use EXACTLY the "exact" value of one of the EXISTING categories if it fits well. Keep the icon:... prefix unchanged.
2. If NO existing category fits, create a NEW one. New categories MUST follow this format:
   - A short Ukrainian name (e.g. "Спорт", "Тварини", "Освіта")
   - No emoji, no icon: prefix, and no decorative symbols. The app will attach the SVG icon later.
3. Return a STRICT JSON object: keys = transaction "id" (integer), values = category name (string).
4. Do NOT return null — always assign something.
5. Output ONLY the JSON object, no markdown, no extra text.

Existing categories:
{json.dumps(category_names, ensure_ascii=False)}

Transactions to categorize:
{json.dumps(compact_transactions, ensure_ascii=False)}
"""
            raw_text = AIService._call_openrouter(prompt, "openai/gpt-oss-120b:free", temperature=0.0)
            if not raw_text:
                return {}

            raw_text = AIService._clean_json_response(raw_text)
            data = json.loads(raw_text)
            result = {}
            for k, v in data.items():
                if str(k).isdigit() and v and isinstance(v, str) and v.strip():
                    normalized = AIService._normalize_category_choice(v, category_refs)
                    if normalized:
                        result[int(k)] = normalized
            return result
        except Exception as e:
            print(f"AI category choice error: {e}")
            return {}

    @staticmethod
    def extract_transaction_request(user_text, accounts, categories):
        try:
            account_data = [{"id": a.id, "name": a.name, "is_shared": bool(a.is_shared)} for a in accounts]
            category_data = [{"name": c.name, "display": display_item_name(c.name), "type": c.type, "is_shared": bool(c.is_shared)} for c in categories]
            prompt = f"""
            Parse the user's message. If they ask to add transactions, return JSON:
            {{
              "can_add": true,
              "transactions": [
                {{"date":"YYYY-MM-DD","type":"Витрата|Дохід","amount":150,"description":"...","account_id":1,"category":"exact existing category name, including icon: prefix, or null"}}
              ]
            }}
            If they are not asking to add transactions, return {{"can_add": false}}.

            Accounts:
            {json.dumps(account_data, ensure_ascii=False)}

            Existing categories:
            {json.dumps(category_data, ensure_ascii=False)}

            User message:
            {user_text}
            """
            raw_text = AIService._call_openrouter(prompt, "openai/gpt-oss-120b:free", temperature=0.0)
            if not raw_text:
                return {"can_add": False}
            
            raw_text = AIService._clean_json_response(raw_text)
            return json.loads(raw_text)
        except Exception as e:
            print(f"AI transaction extraction error: {e}")
            return {"can_add": False}

    @staticmethod
    def analyze_finance(user_data, analysis_type):
        try:
            lang = user_data.get('lang', 'uk')
            prompts = get_string('ai_prompts')
            
            if analysis_type == 'custom' and user_data.get('user_query'):
                task = f"ANSWER THE USER'S SPECIFIC QUESTION: {user_data['user_query']}"
            else:
                task = prompts.get(f'analytics_{analysis_type}', "Give financial advice.")

            system_instruction = "You are a senior financial analyst. "
            if lang == 'uk':
                system_instruction = "Ти — провідний фінансовий аналітик. "

            prompt = f"{system_instruction} Client: {user_data['username']}. DATA:\n"
            prompt += f"- Balance: {user_data['total_balance']} {user_data.get('currency', '₴')}\n"
            prompt += f"- Income: {user_data['income']} {user_data.get('currency', '₴')}\n"
            prompt += f"- Expenses: {user_data['expenses']} {user_data.get('currency', '₴')}\n"
            prompt += f"GOALS:\n{user_data['goals_list']}\nCATEGORIES:\n{user_data['cat_totals']}\n"
            prompt += f"TASK:\n{task}\n"
            prompt += "Write max 8-10 sentences. Be specific. IMPORTANT: Write ONLY in " + ("Ukrainian" if lang == 'uk' else "English")

            response_text = AIService._call_openrouter(prompt, "openai/gpt-oss-120b:free", temperature=0.7)
            if not response_text:
                return "AI analysis unavailable."
            
            return response_text.replace('**', '').replace('*', '• ').replace('\n', '<br>')
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            raise e
