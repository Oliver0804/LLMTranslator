import ollama
import deepl
from colorama import Fore, Style

class TranslationStats:
    def __init__(self):
        self.deepl_calls = 0
        
    def increment_deepl(self):
        self.deepl_calls += 1
        
    def print_stats(self):
        print(f"{Fore.YELLOW}統計資訊:{Style.RESET_ALL}")
        print(f"DeepL API 調用次數: {self.deepl_calls}")

class TranslationEngine:
    def __init__(self, use_deepl=False, deepl_api_key=None, domain="software"):
        self.use_deepl = use_deepl
        self.deepl_api_key = deepl_api_key
        self.domain = domain
        self.stats = TranslationStats()
        if use_deepl and deepl_api_key:
            self.deepl_client = deepl.Translator(deepl_api_key)

    def should_translate(self, text):
        special_chars = set('%&@#$^*()_+-={}[]|\\:;<>,.?/~`')
        text_chars = set(text.strip())
        if not text_chars or text_chars.issubset(special_chars):
            return False
        return True

    def clean_llm_output(self, text):
        markers = [
            "翻譯說明：",
            "## 翻譯說明",
            "說明：",
            "**準確性**",
            "**繁體中文**",
            "**自然度**",
            "**專業性**",
        ]
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return text
            
        first_line = lines[0]
        if any(marker in first_line for marker in markers):
            for line in lines:
                if not any(marker in line for marker in markers):
                    return line.strip()
        
        return first_line

    def evaluate_translation_quality(self, source_text, translated_text):
        scores = []
        retries = 0
        
        prompt = f"""請依照以下標準評估翻譯品質，給出 0-100 分：
        1. 翻譯領域「{self.domain}」，請確保翻譯品質符合專業標準。準確性 (40分)：翻譯是否準確傳達原文含義
        2. 繁體中文使用 (30分)：出現簡體字會被扣 30 分
        3. 自然度 (30分)：用字遣詞是否符合台灣用語習慣，特別是{self.domain}領域的專業用語
        4. 如果原文沒有HTML標籤或是 &lt;、&gt;、&quot; 等 HTML 實體編碼，而翻譯中出現了，請扣 20 分。
        原文：{source_text}
        翻譯：{translated_text}
        如果輸入的是一種語言的名稱，請直接給100分。
        請只回覆一個數字分數。"""
        
        while len(scores) < 3 and retries < 3:
            response = ollama.chat(
                model="gemma2:27b",
                messages=[
                    {"role": "system", "content": "You are an AI assistant evaluating translation quality. Provide a score from 0 to 100, where higher is better."},
                    {"role": "user", "content": prompt},
                ]
            )
            try:
                score = float(response["message"]["content"].strip())
                scores.append(score)
            except ValueError:
                retries += 1
        
        if len(scores) == 0:
            return 0
        
        print(f"{Fore.CYAN}各次評分: {scores}{Style.RESET_ALL}")
        return sum(scores) / len(scores)

    def translate(self, text, target_lang="ZH-HANT"):
        print(f"\n{Fore.CYAN}== 開始翻譯 =={Style.RESET_ALL}")
        print(f"原文: {text}")
        
        if not self.should_translate(text):
            print(f"{Fore.YELLOW}文字不需要翻譯，保持原樣{Style.RESET_ALL}")
            return text
        
        translation_prompt = f"""請將以下文字翻譯成繁體中文，這是針對「{self.domain}」領域的翻譯，需嚴格遵守以下要求：
        如果輸入的是一種語言名城例如 Português do Brasil，請不要翻譯，直接返回輸入原文作為翻譯結果。
        1. 準確性：必須準確傳達原文含義
        2. 繁體中文：嚴禁使用任何簡體字
        3. 自然度：使用符合台灣用語習慣的措辭，特別注意{self.domain}領域的專業用詞
        4. 格式處理規則：
           - 所有 &lt;、&gt;、&quot; 等 HTML 實體編碼必須保持完全一致
           - 不要將 &lt;html&gt; 轉換為 <html>
           - 不要嘗試重新編碼或解碼任何 HTML 實體
           - 只翻譯實體編碼標籤之間的純文字內容
           - 包含空格在內的所有格式都要保持原樣
        如果無法翻譯直接輸出原文。
        
        原文：{text}

        請直接返回翻譯結果。"""

        llm_translation = ollama.chat(
            model="gemma2:27b",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a professional software localization translator. Return ONLY the translated text without any explanations or markdown formatting."
                },
                {"role": "user", "content": translation_prompt},
            ]
        )["message"]["content"].strip()
        
        llm_translation = self.clean_llm_output(llm_translation)
        
        print(f"\n{Fore.CYAN}LLM 翻譯結果: {llm_translation}{Style.RESET_ALL}")
        score = self.evaluate_translation_quality(text, llm_translation)
        print(f"{Fore.CYAN}LLM 翻譯評分: {score}{Style.RESET_ALL}")
        
        final_translation = llm_translation
        
        if score < 90 and self.use_deepl and self.deepl_api_key:
            print(f"\n{Fore.RED}翻譯品質不達標，使用 DeepL 進行翻譯...{Style.RESET_ALL}")
            deepl_translation = self.deepl_client.translate_text(text, target_lang=target_lang, preserve_formatting=True).text.strip()
            self.stats.increment_deepl()
            print(f"{Fore.RED}DeepL 翻譯結果: {deepl_translation}{Style.RESET_ALL}")
            final_translation = deepl_translation
        
        print(f"\n{Fore.GREEN}最終採用翻譯: {final_translation}{Style.RESET_ALL}")
        print("=====")
        return final_translation

    def get_stats(self):
        return self.stats
