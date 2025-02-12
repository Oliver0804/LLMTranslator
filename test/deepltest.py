
import deepl

def translate_text(text: str, target_lang: str, api_key: str) -> str:
    deepl_client = deepl.DeepLClient(api_key)
    result = deepl_client.translate_text(text, target_lang=target_lang)
    return result.text

def main():
    DEEPL_API_KEY = "your_api_key_here"  # 替換為你的 DeepL API 金鑰
    test_text = "Hello, how are you?"
    target_language = "ZH-HANT"  # 目標語言（ZH-HANT 表示繁體中文）

    translated_text = translate_text(test_text, target_language,DEEPL_API_KEY)
    print(translated_text)

if __name__ == "__main__":
    main()
