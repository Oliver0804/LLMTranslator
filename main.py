import json
import time
import requests
from datetime import datetime
from tqdm import tqdm
from typing import Optional, Dict
import os
import sys

# Settings for translation
TRANSLATION_SETTINGS = {
    "model": "gemma2:27b",  # LLM model to use
    "target_language": "zh-Hant-TW",  # Target language: pl,se,de,fr,es,zh-Hant-TW
    "domain": "APP Mesh Network Wireless Communication",  # Professional domain
    "style": "easy to understand",  # Translation style
    "retry_count": 3,  # Number of retries
    "min_score": 60,  # Minimum acceptable score
    "prompt_version": "en",  # Prompt version (zh or en)
}

# Load prompts from JSON file
def load_prompts():
    try:
        with open('prompts.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading prompts: {e}")
        sys.exit(1)

PROMPTS = load_prompts()

# 終端機色彩常數
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class TranslationMemory:
    def __init__(self, max_examples: int = 5):
        self.memory: Dict[str, str] = {}
        self.memory_file = "translation_memory.json"
        self.max_examples = max_examples
        self.load_memory()
    
    def load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memory = json.load(f)
        except Exception as e:
            print(f"載入翻譯記憶時發生錯誤: {e}")
            self.memory = {}
    
    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存翻譯記憶時發生錯誤: {e}")
    
    def get_translation(self, text: str) -> tuple[Optional[str], Optional[int]]:
        """獲取翻譯，同時返回該翻譯的歷史分數"""
        if text not in self.memory:
            return None, None
        return self.memory[text].get('translation'), self.memory[text].get('score', 0)
    
    def add_translation(self, source: str, target: str, score: int = 0):
        """添加翻譯到記憶體，包含分數信息"""
        self.memory[source] = {
            'translation': target,
            'score': score,
            'timestamp': datetime.now().isoformat()
        }
        self.save_memory()
    
    def get_similar_translations(self, text: str) -> list:
        """獲取與當前文本相似的翻譯記錄"""
        return find_similar_entries(text, self.memory, self.max_examples)

def log_translation(original, old_translation, new_translation, score=None):
    """Log translation results to log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"""[{timestamp}]
Source: {original}
{f'Previous translation: {old_translation}' if old_translation else ''}
New translation: {new_translation}
{f'Score: {score}' if score else ''}
{'=' * 50}
"""
    with open('translation_log.txt', 'a', encoding='utf-8') as f:
        f.write(log_entry)

def call_ollama(prompt, model=TRANSLATION_SETTINGS["model"], max_retries=TRANSLATION_SETTINGS["retry_count"]):
    """呼叫 Ollama API 進行翻譯"""
    print(f"{Colors.BLUE}>> 翻譯提示詞:{Colors.ENDC}")
    print("-" * 50)
    print(prompt)
    print("-" * 50)
    
    for attempt in range(max_retries):
        try:
            response = requests.post('http://localhost:11434/api/generate',
                json={
                    "model": model,
                    "prompt": f"{prompt}",
                    "stream": False
                }, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'response' in data:
                    print(f"{Colors.GREEN}>> LLM 回應:{Colors.ENDC}")
                    print("-" * 50)
                    print(data['response'])
                    print("-" * 50)
                    return data['response']
            
            print(f"{Colors.WARNING}>> 重試 {attempt + 1}/{max_retries}{Colors.ENDC}")
            time.sleep(2 * (attempt + 1))
            continue
            
        except Exception as e:
            print(f"{Colors.FAIL}>> 錯誤: {str(e)}{Colors.ENDC}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return "翻譯服務暫時無法使用，請稍後再試"
    
    return "無法獲取翻譯結果"

def validate_special_chars(original: str, translation: str) -> tuple[bool, str]:
    """驗證特殊符號是否正確保留，返回 (是否通過, 警告訊息)"""
    patterns = [
        r'%@', r'%d', r'%s', r'%lld', r'%i', r'%f', r'%u', r'%x',  # 基本格式
        r'%\d+\$@', r'%\d+\$d', r'%\d+\$s',  # 帶數字的格式
        r'\${.*?}',  # 變數名稱格式
        r'%[\d.]*lld%%',  # 百分比格式
    ]
    
    def count_pattern(text: str, pattern: str) -> int:
        import re
        return len(re.findall(pattern, text))
    
    # 檢查每個模式在原文和翻譯中的出現次數是否相同
    for pattern in patterns:
        if count_pattern(original, pattern) != count_pattern(translation, pattern):
            return False, f"特殊格式 {pattern} 數量不匹配"
    
    # 如果原文只包含特殊格式，翻譯必須完全相同
    if all(c in '%$@{}[]() ' for c in original.replace(' ', '')):
        if original.strip() != translation.strip():
            return False, "純格式字串必須完全相同"
        return True, ""
        
    return True, ""

def evaluate_translation(original: str, translation: str, max_retries=TRANSLATION_SETTINGS["retry_count"], is_double_check=False) -> tuple[int, str]:
    """評估翻譯品質並返回分數和警告訊息"""
    
    # 首先檢查特殊字符
    format_valid, warning = validate_special_chars(original, translation)
    if not format_valid:
        print(f"{Colors.WARNING}>> 格式警告: {warning}{Colors.ENDC}")
    
    # 使用選定語言版本的評分提示詞
    prompt_template = PROMPTS[TRANSLATION_SETTINGS["prompt_version"]]["evaluation"]
    prompt = prompt_template.format(original=original, translation=translation)
    
    print(f"{Colors.BLUE}>> {TRANSLATION_SETTINGS['prompt_version'].upper()} 評分提示詞:{Colors.ENDC}")
    print("-" * 50)
    print(prompt)
    print("-" * 50)
    
    for attempt in range(max_retries):
        response = call_ollama(prompt)
        if response and response != "翻譯服務暫時無法使用" and response != "無法獲取翻譯結果":
            try:
                score = ''.join(filter(str.isdigit, response))
                base_score = int(score) if score else 50
                
                # 調整分數：如果格式有問題，扣分但不歸零
                final_score = base_score - (20 if not format_valid else 0)
                final_score = max(0, min(100, final_score))  # 確保分數在 0-100 之間
                
                # 高分驗證
                if final_score >= 95 and not is_double_check:
                    print(f"{Colors.WARNING}>> 檢測到高分 ({final_score})，進行二次驗證...{Colors.ENDC}")
                    second_score, _ = evaluate_translation(
                        original, 
                        translation, 
                        max_retries=1, 
                        is_double_check=True
                    )
                    final_score = (final_score + second_score) // 2
                    print(f"{Colors.BLUE}>> 最終分數: {final_score}{Colors.ENDC}")
                
                return final_score, warning
                
            except Exception as e:
                print(f"{Colors.FAIL}>> 評分過程發生錯誤: {str(e)}{Colors.ENDC}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
    
    return 50, "無法獲得評分"

def evaluate_both_translations(key, en_text, translation):
    """評估 key 和 en_text 的翻譯結果"""
    key_score, key_warning = evaluate_translation(key, translation)
    en_score, en_warning = evaluate_translation(en_text, translation) if en_text and en_text != key else (0, "")
    
    # 如果都有分數，返回較高的分數
    if en_score > 0:
        return max(key_score, en_score), key_warning if key_score >= en_score else en_warning
    return key_score, key_warning

class TranslationContext:
    def __init__(self, domain: str = "一般", style: str = "正式"):
        self.domain = domain
        self.style = style
    
    def get_context(self) -> str:
        return f"""
領域：{self.domain}
風格：{self.style}
"""

def fix_format_variables(original: str, translation: str) -> str:
    """修正翻譯中的格式變數"""
    import re
    
    # 定義所有可能的格式模式
    patterns = [
        (r'%\d+\$@', r'%@'),  # %1$@ -> %@
        (r'%\d+\$d', r'%d'),  # %1$d -> %d
        (r'%\d+\$s', r'%s'),  # %1$s -> %s
        (r'%\d+\$lld', r'%lld'),  # %1$lld -> %lld
    ]
    
    # 從原文中提取所有格式變數
    original_vars = []
    for pattern, _ in patterns:
        original_vars.extend(re.findall(pattern, original))
    if not original_vars:  # 如果沒有帶數字的格式，檢查基本格式
        original_vars = re.findall(r'%[@ds]|%lld', original)
    
    # 如果沒有找到變數，返回原翻譯
    if not original_vars:
        return translation
    
    # 建立一個新的翻譯字串，逐個替換格式變數
    result = translation
    for i, var in enumerate(original_vars):
        # 尋找翻譯中對應位置的格式變數
        simple_patterns = r'%[@ds]|%lld'
        trans_vars = re.findall(simple_patterns, result)
        
        if i < len(trans_vars):
            # 替換翻譯中的變數為原文中的格式
            result = result.replace(trans_vars[i], var, 1)
    
    return result

def translate_with_ollama(text: str, context: TranslationContext, memory: TranslationMemory, previous_translations: list = None):
    """直接使用記憶翻譯或處理特殊格式變數"""
    # 檢查記憶和純變數文本
    cached_translation, cached_score = memory.get_translation(text)
    
    # 只有當快取的翻譯存在且分數達標時才使用
    if cached_translation and (cached_score is None or cached_score >= TRANSLATION_SETTINGS["min_score"]):
        print(f"{Colors.BLUE}>> 使用快取翻譯 (分數: {cached_score}):{Colors.ENDC} {cached_translation}")
        return cached_translation, True, cached_score
    
    if all(c in '%$@{}[]() ' for c in text):
        memory.add_translation(text, text, 100)  # 純格式字符串給予滿分
        return text, True, 100
    
    # 使用選定語言版本的提示詞
    prompt_template = PROMPTS[TRANSLATION_SETTINGS["prompt_version"]]["translation"]
    prompt = prompt_template.format(
        target_language=TRANSLATION_SETTINGS["target_language"],
        text=text,
        memory_context=format_memory_context(text, memory),
        translation_context=context.get_context()
    )

    # 如果有歷史翻譯，也使用對應語言版本的格式
    if previous_translations:
        avoid_text = "避免使用以下低品質翻譯：" if TRANSLATION_SETTINGS["prompt_version"] == "zh" else "Previous low-quality translations to avoid:"
        prompt += f"\n\n{avoid_text}"
        for prev_trans in previous_translations:
            prompt += f"\n- {prev_trans}"
            
    prompt += "\n\nTranslation:"

    translation = call_ollama(prompt).strip()
    
    # 清理回應，只保留實際翻譯內容
    if translation:
        # 移除可能的前綴説明
        if ":" in translation:
            translation = translation.split(":")[-1].strip()
        # 移除引號如果存在
        translation = translation.strip('"').strip("'")
        
        # 檢查並修正格式變數
        format_valid, _ = validate_special_chars(text, translation)
        if not format_valid:
            fixed_translation = fix_format_variables(text, translation)
            format_valid, _ = validate_special_chars(text, fixed_translation)
            if format_valid:
                translation = fixed_translation
        
        if translation not in ["翻譯服務暫時無法使用，請稍後再試", "無法獲取翻譯結果"]:
            return translation, False, None  # 返回新翻譯，非快取，無分數
            
    return translation, False, None

def format_memory_context(text: str, memory: TranslationMemory) -> str:
    """格式化相關的翻譯記憶作為上下文"""
    similar_entries = memory.get_similar_translations(text)
    if not similar_entries:
        return "無相關翻譯記錄"
    
    context = "相關翻譯記錄：\n"
    for source, target in similar_entries:
        context += f"原文：{source}\n翻譯：{target}\n"
    return context

def find_similar_entries(text: str, memory: Dict[str, str], max_entries: int) -> list:
    """找出相似的翻譯記錄"""
    from difflib import SequenceMatcher
    
    def similarity(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    # 計算所有記憶項目與當前文本的相似度
    similar_items = [
        (source, target, similarity(text, source))
        for source, target in memory.items()
    ]
    
    # 排序並返回最相似的幾個
    similar_items.sort(key=lambda x: x[2], reverse=True)
    return [(source, target) for source, target, _ in similar_items[:max_entries]]

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def save_translations(data, original_file, model="gemma2:27b"):
    # 從模型名稱中移除非法字元
    safe_model_name = "".join(c for c in model if c.isalnum() or c in ":-_")
    
    # 生成帶時間戳和模型名稱的新檔名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.splitext(original_file)[0]
    new_file = f"{file_name}_translated_{safe_model_name}_{timestamp}.xcstrings"
    
    # 保存翻譯後的完整數據
    with open(new_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return new_file

def create_translation_unit(translation: str) -> dict:
    """創建標準的翻譯單元結構"""
    return {
        "stringUnit": {
            "state": "translated",  # 必須包含狀態
            "value": translation    # 翻譯內容
        }
    }

def process_json_value(value: dict, memory: TranslationMemory, context: TranslationContext) -> dict:
    """處理 JSON 值並進行翻譯"""
    if not isinstance(value, dict):
        return value
        
    try:
        result = {}
        for k, v in value.items():
            if k == "variations":
                print(f"{Colors.BLUE}>> 處理變化結構{Colors.ENDC}")
                try:
                    # 修正：存取變數前先確認它們存在
                    result[k] = {}
                    for variation_type in v:
                        result[k][variation_type] = {}
                        variation_data = v[variation_type]
                        for form, form_data in variation_data.items():
                            result[k][variation_type][form] = process_json_value(form_data, memory, context)
                except Exception as e:
                    print(f"{Colors.FAIL}>> 處理變化結構時發生錯誤: {str(e)}{Colors.ENDC}")
                    result[k] = v
                    
            elif isinstance(v, dict):
                result[k] = process_json_value(v, memory, context)
                
            elif k == "value" and isinstance(v, str):
                print(f"\n{Colors.BLUE}>> 處理文本:{Colors.ENDC} {v}")
                try:
                    translation, is_cached, cached_score = translate_with_ollama(v, context, memory, [])
                    
                    if not is_cached:
                        score, warning = evaluate_translation(v, translation)
                        print(f"{Colors.GREEN}>> 翻譯結果:{Colors.ENDC} {translation}")
                        print(f"{Colors.BLUE}>> 品質分數:{Colors.ENDC} {score}")
                        
                        if score < TRANSLATION_SETTINGS["min_score"]:
                            previous_translations = [translation]
                            print(f"{Colors.WARNING}>> 分數過低 ({score})，嘗試改進翻譯...{Colors.ENDC}")
                            improved_translation = translate_with_improve_loop(
                                v, None, translation, 
                                context, memory, "String"
                            )
                            # 再次評估改進後的翻譯
                            improved_score, _ = evaluate_translation(v, improved_translation)
                            print(f"{Colors.GREEN}>> 改進後翻譯:{Colors.ENDC} {improved_translation}")
                            print(f"{Colors.BLUE}>> 改進後分數:{Colors.ENDC} {improved_score}")
                            
                            # 使用分數較高的版本
                            if improved_score > score:
                                translation = improved_translation
                                score = improved_score
                            
                        # 保存最終結果
                        memory.add_translation(v, translation, score)
                        
                    result[k] = translation
                    
                except Exception as e:
                    print(f"{Colors.FAIL}>> 翻譯過程發生錯誤: {str(e)}\n{Colors.ENDC}")
                    result[k] = v  # 保留原文
            else:
                result[k] = v
                
        return result
        
    except Exception as e:
        print(f"{Colors.FAIL}>> 處理 JSON 時發生錯誤: {str(e)}\n堆疊追蹤:{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        return value

def translate_variations(variations: dict, memory: TranslationMemory, context: TranslationContext) -> dict:
    """Specifically handle plural variations"""
    result = {}
    for variation_type, forms in variations.items():
        if variation_type == "plural":
            print(f"{Colors.BLUE}>> Processing plural variation{Colors.ENDC}")
            result[variation_type] = {}
            for form, content in forms.items():
                if "stringUnit" in content:
                    string_unit = content["stringUnit"]
                    if "value" in string_unit:
                        source_text = string_unit["value"]
                        print(f"{Colors.BLUE}>> Source text ({form}):{Colors.ENDC} {source_text}")
                        
                        translation, is_cached = translate_with_ollama(source_text, context, memory)
                        
                        if not is_cached:
                            score, warning = evaluate_translation(source_text, translation)
                            print(f"{Colors.GREEN}>> Translation ({form}):{Colors.ENDC} {translation}")
                            print(f"{Colors.BLUE}>> Quality score ({form}):{Colors.ENDC} {score}")
                        else:
                            print(f"{Colors.GREEN}>> Using cached translation ({form}):{Colors.ENDC} {translation}")
                            
                        result[variation_type][form] = {
                            "stringUnit": {
                                "state": "translated",
                                "value": translation
                            }
                        }
                    else:
                        result[variation_type][form] = content
                else:
                    result[variation_type][form] = content
        else:
            result[variation_type] = forms
    return result

def print_strings(file_path, context: Optional[TranslationContext] = None):
    """Process localization strings and add target language if missing"""
    if context is None:
        context = TranslationContext(
            domain=TRANSLATION_SETTINGS["domain"],
            style=TRANSLATION_SETTINGS["style"]
        )
    
    memory = TranslationMemory()
    target_lang = TRANSLATION_SETTINGS["target_language"]
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    strings = data.get('strings', {})
    total = len(strings)
    processed = 0
    
    for key, value in strings.items():
        try:
            processed += 1
            print(f"\nProcessing: {processed}/{total}")
            
            if isinstance(value, dict) and "localizations" in value:
                localizations = value["localizations"]
                
                # Try to get English text as source
                source_text = key
                if "en" in localizations and "stringUnit" in localizations["en"]:
                    source_text = localizations["en"]["stringUnit"].get("value", key)
                
                # Check if target language exists
                if target_lang not in localizations:
                    # 新翻譯流程
                    print(f"{Colors.BLUE}>> Adding new translation for {key}{Colors.ENDC}")
                    print(f"{Colors.BLUE}Source text:{Colors.ENDC} {source_text}")
                    
                    best_translation = None
                    best_score = 0
                    attempt = 0
                    
                    while attempt < TRANSLATION_SETTINGS["retry_count"]:
                        translation, is_cached = translate_with_ollama(source_text, context, memory)
                        
                        if is_cached:
                            print(f"{Colors.GREEN}>> Using cached translation:{Colors.ENDC} {translation}")
                            best_translation = translation
                            break
                            
                        score, warning = evaluate_translation(source_text, translation)
                        print(f"{Colors.GREEN}>> Translation attempt {attempt + 1}:{Colors.ENDC} {translation}")
                        print(f"{Colors.BLUE}>> Quality score:{Colors.ENDC} {score}")
                        
                        if warning:
                            print(f"{Colors.WARNING}>> Warning: {warning}{Colors.ENDC}")
                        
                        if score > best_score:
                            best_translation = translation
                            best_score = score
                        
                        if score >= TRANSLATION_SETTINGS["min_score"]:
                            break
                            
                        print(f"{Colors.WARNING}>> Score below minimum ({TRANSLATION_SETTINGS['min_score']}), retrying...{Colors.ENDC}")
                        attempt += 1
                        
                    # 使用最佳翻譯結果
                    localizations[target_lang] = create_translation_unit(best_translation)
                    
                elif "variations" in localizations[target_lang]:
                    # ...existing variations handling code...
                    pass
                else:
                    # 更新現有翻譯流程
                    current = localizations[target_lang].get("stringUnit", {}).get("value")
                    if current:
                        score, warning = evaluate_translation(source_text, current)
                        print(f"{Colors.BLUE}>> Existing translation score: {score}{Colors.ENDC}")
                        
                        if score < TRANSLATION_SETTINGS["min_score"]:
                            print(f"{Colors.WARNING}>> Low score ({score}), retranslating...{Colors.ENDC}")
                            best_translation = None
                            best_score = 0
                            attempt = 0
                            
                            while attempt < TRANSLATION_SETTINGS["retry_count"]:
                                translation, is_cached = translate_with_ollama(source_text, context, memory)
                                
                                if is_cached:
                                    best_translation = translation
                                    break
                                    
                                new_score, warning = evaluate_translation(source_text, translation)
                                print(f"{Colors.GREEN}>> New translation attempt {attempt + 1}:{Colors.ENDC} {translation}")
                                print(f"{Colors.BLUE}>> Quality score:{Colors.ENDC} {new_score}")
                                
                                if new_score > best_score:
                                    best_translation = translation
                                    best_score = new_score
                                
                                if new_score >= TRANSLATION_SETTINGS["min_score"]:
                                    break
                                    
                                print(f"{Colors.WARNING}>> Score below minimum, retrying...{Colors.ENDC}")
                                attempt += 1
                            
                            if best_translation:
                                localizations[target_lang]["stringUnit"]["value"] = best_translation

            print("-" * 50)
            
        except Exception as e:
            print(f"{Colors.FAIL}Error processing item: {str(e)}{Colors.ENDC}")
            continue
    
    # Save translation results
    new_file = save_translations(data, file_path, model=TRANSLATION_SETTINGS["model"])
    print(f"\nTranslation results saved to: {new_file}")

def translate_with_improve_loop(key, source_text, current_translation, context, memory, source_type):
    """處理翻譯改進循環"""
    max_attempts = TRANSLATION_SETTINGS["retry_count"]
    current_attempt = 0
    best_translation = current_translation
    best_score = 0
    previous_translations = []

    while current_attempt < max_attempts:
        try:
            # 加入前次翻譯作為反面參考
            translation, is_cached, _ = translate_with_ollama(
                source_text if source_text else key,
                context, 
                memory,
                previous_translations
            )
            
            if is_cached:
                print(f"{Colors.GREEN}>> 使用快取翻譯{Colors.ENDC}")
                return translation
                
            print(f"{Colors.GREEN}>> 翻譯結果 (嘗試 {current_attempt + 1}):{Colors.ENDC} {translation}")
            
            score, warning = evaluate_translation(source_text if source_text else key, translation)
            print(f"{Colors.BLUE}>> 品質分數:{Colors.ENDC} {score}")
            
            if warning:
                print(f"{Colors.WARNING}>> 警告: {warning}{Colors.ENDC}")
            
            if score > best_score:
                best_translation = translation
                best_score = score
                
            if score >= TRANSLATION_SETTINGS["min_score"]:
                break
                
            # 記錄這次的翻譯用於下次避免
            previous_translations.append(translation)
            current_attempt += 1
            print(f"{Colors.WARNING}>> 分數不足，進行第 {current_attempt + 1} 次嘗試...{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.FAIL}>> 改進翻譯時發生錯誤: {str(e)}{Colors.ENDC}")
            break
    
    return best_translation

if __name__ == "__main__":
    # 選擇提示詞版本
    version = input("Select prompt version (zh/en, default: en): ").strip().lower()
    if version in ["zh", "en"]:
        TRANSLATION_SETTINGS["prompt_version"] = version
    
    context = TranslationContext(
        domain=TRANSLATION_SETTINGS["domain"],
        style=TRANSLATION_SETTINGS["style"]
    )
    file_path = "Localizable.xcstrings"
    print_strings(file_path, context)
