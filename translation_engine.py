import ollama
import deepl
from colorama import Fore, Style
import time

class TranslationStats:
    def __init__(self):
        self.deepl_calls = 0
        self.modified_translations = 0
        self.new_translations = 0
        self.total_entries = 0
        self.start_time = time.time()
        self.output_file = None
        
    def set_output_file(self, filepath):
        self.output_file = filepath
        
    def increment_deepl(self):
        self.deepl_calls += 1
        
    def increment_modified(self):
        self.modified_translations += 1
        
    def increment_new(self):
        self.new_translations += 1
        
    def set_total_entries(self, total):
        self.total_entries = total
        
    def get_elapsed_time(self):
        return time.time() - self.start_time
        
    def print_stats(self):
        elapsed_time = self.get_elapsed_time()
        print(f"\n{Fore.YELLOW}翻譯報告:{Style.RESET_ALL}")
        print(f"總處理項目: {self.total_entries} 筆")
        print(f"修正翻譯: {self.modified_translations} 筆 ({self.modified_translations/self.total_entries*100:.1f}%)")
        print(f"新增翻譯: {self.new_translations} 筆 ({self.new_translations/self.total_entries*100:.1f}%)")
        print(f"DeepL API 調用: {self.deepl_calls} 次 ({self.deepl_calls/self.total_entries*100:.1f}%)")
        if self.output_file:
            print(f"輸出檔案: {self.output_file}")
        print(f"總耗時: {elapsed_time:.1f} 秒")

class TranslationContext:
    def __init__(self, domain: str = "一般", style: str = "正式"):
        self.domain = domain
        self.style = style
    
    def get_context(self) -> str:
        return f"""
領域：{self.domain}
風格：{self.style}
"""

class TranslationEngine:
    def __init__(self, use_deepl=False, deepl_api_key=None, domain="software"):
        self.use_deepl = use_deepl
        self.deepl_api_key = deepl_api_key
        self.domain = domain
        self.stats = TranslationStats()
        
        # 評分閾值設定
        self.SCORE_THRESHOLD_SKIP = 90  # 高於此分數的翻譯將被保留
        self.SCORE_THRESHOLD_DEEPL = 85  # 低於此分數的翻譯將使用 DeepL 重新翻譯
        self.SCORE_THRESHOLD_EXISTING = 85  # 現有翻譯評分閾值
        
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
        """
        判斷翻譯品質時更加注意格式符號
        """
        scores = []
        retries = 0
        
        prompt = f"""請依照以下標準評估翻譯品質，給出 0-100 分：
        1. 翻譯領域「{self.domain}」，請確保翻譯品質符合專業標準。準確性 (40分)：翻譯是否準確傳達原文含義
        2. 繁體中文使用 (20分)：出現簡體字會被扣 20 分
        3. 自然度 (30分)：用字遣詞是否符合台灣用語習慣，特別是{self.domain}領域的專業用語
        4. 格式處理 (10分)：
           - 如果原文有 %s, %d 等格式符號，翻譯必須完整保留
           - 格式符號的順序必須正確
           - 格式符號前後的空格必須保持一致
        
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

    def _translate_with_formats(self, text, format_specs, translator, target_lang):
        """改進格式符號的處理"""
        placeholders = []
        temp_text = text
        
        # 添加用於偵測格式順序的索引
        for i, spec in enumerate(format_specs):
            placeholder = f"__{i+1}:{spec}__"
            placeholders.append(placeholder)
            temp_text = temp_text.replace(spec, placeholder)
        
        translated = self.translate(temp_text, target_lang)
        
        # 還原格式符號時保持原始空格
        for spec, placeholder in zip(format_specs, placeholders):
            translated = translated.replace(placeholder, spec)
            
        return translated

    def _extract_format_specs(self, text):
        """提取格式說明符"""
        import re
        format_specs = re.findall(r'%(?:\d+\$)?[-+]?(?:\d+)?(?:\.\d+)?[diufFeEgGxXoscpaA%]', text)
        return format_specs

    def translate(self, text, target_lang="ZH-HANT", extra_prompt=""):
        """翻譯文本，支援額外提示詞"""
        print(f"\n{Fore.CYAN}== 開始翻譯 =={Style.RESET_ALL}")
        print(f"原文: {text}")
        
        if not self.should_translate(text):
            print(f"{Fore.YELLOW}文字不需要翻譯，保持原樣{Style.RESET_ALL}")
            return text
        
        # 添加格式處理的提示詞
        format_prompt = extra_prompt if extra_prompt else ""
        
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
        5. 數字直接使用阿拉伯數字，不使用中文數字
        6. 如果原文中有其他語言的短語或專有名詞，請保持原文不變
        7. Key是金鑰的意思，不要翻譯成鑰匙
        {format_prompt}
        
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
        
        # 如果有格式符號，還原它們
        if format_specs:
            final_text = llm_translation
            for spec, placeholder in zip(format_specs, placeholders):
                final_text = final_text.replace(placeholder, spec)
            llm_translation = final_text
        
        print(f"\n{Fore.CYAN}LLM 翻譯結果: {llm_translation}{Style.RESET_ALL}")
        score = self.evaluate_translation_quality(text, llm_translation)
        print(f"{Fore.CYAN}LLM 翻譯評分: {score}{Style.RESET_ALL}")
        
        final_translation = llm_translation
        
        if score < self.SCORE_THRESHOLD_DEEPL and self.use_deepl and self.deepl_api_key:
            print(f"\n{Fore.RED}翻譯品質不達標 (低於 {self.SCORE_THRESHOLD_DEEPL} 分)，使用 DeepL 進行翻譯...{Style.RESET_ALL}")
            try:
                # 使用 encode('utf-8') 處理 Unicode 字符
                deepl_translation = self.deepl_client.translate_text(
                    text, 
                    target_lang=target_lang, 
                    preserve_formatting=True
                ).text.encode('utf-8').decode('utf-8').strip()
                
                self.stats.increment_deepl()
                print(f"{Fore.RED}DeepL 翻譯結果: {deepl_translation}{Style.RESET_ALL}")
                final_translation = deepl_translation
            except Exception as e:
                print(f"{Fore.RED}DeepL 翻譯失敗：{e}，使用 LLM 翻譯結果{Style.RESET_ALL}")
                final_translation = llm_translation
        
        else:
            self.stats.increment_new()
        
        print(f"\n{Fore.GREEN}最終採用翻譯: {final_translation}{Style.RESET_ALL}")
        print("=====")
        return final_translation

    def get_stats(self):
        return self.stats
