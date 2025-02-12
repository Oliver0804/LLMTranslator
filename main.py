import json
import sys
import os
from datetime import datetime
from colorama import Fore, Style
from file_parser import FileParser
from translation_engine import TranslationEngine, TranslationContext

# 翻譯設定
TRANSLATION_SETTINGS = {
    "model": "gemma2:27b",
    "target_language": "zh-Hant-TW",
    "domain": "APP Mesh Network Wireless Communication",
    "style": "easy to understand",
    "retry_count": 3,
    "min_score": 60,
    "prompt_version": "en",
}

def load_prompts():
    """載入提示詞檔案"""
    try:
        with open('prompts.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{Fore.RED}載入提示詞失敗：{e}{Style.RESET_ALL}")
        sys.exit(1)

def parse_arguments():
    """處理命令行參數"""
    import argparse
    parser = argparse.ArgumentParser(description='翻譯本地化檔案')
    parser.add_argument('-i', '--input', required=True,
                       help='要翻譯的檔案路徑 (.xliff, .xcstrings, or .po)')
    parser.add_argument('-o', '--output', help='輸出檔案路徑', default=None)
    parser.add_argument('-t', '--target-lang', default='zh-Hant-TW', 
                       help='目標語言 (預設: zh-Hant-TW)')
    parser.add_argument('-all', '--translate-all', action='store_true',
                       help='重新翻譯所有字串，包括已有翻譯的')
    parser.add_argument('-s', '--supervised', action='store_true',
                       help='監督模式：每個翻譯都需要手動確認')
    parser.add_argument('-p', '--prompt-version', choices=['zh', 'en'], 
                       default='en', help='提示詞版本 (預設: en)')
    parser.add_argument('-d', '--domain', default='software',
                       help='翻譯領域 (預設: software)')
    parser.add_argument('-deepl', '--use-deepl', action='store_true',
                       help='使用 DeepL API')
    parser.add_argument('--deepl-key', help='DeepL API Key')
    parser.add_argument('-c', '--continue-translation', action='store_true',
                       help='從上次中斷的地方繼續翻譯')
    parser.add_argument('-test', '--test-mode', action='store_true',
                       help='測試模式：只翻譯前20個條目')
    
    return parser.parse_args()

def generate_output_path(input_path, file_type):
    """生成輸出檔案路徑"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(input_path)[0]
    return f"{base_name}_translated_{timestamp}.{file_type}"

def show_settings_confirmation(args, output_path):
    """顯示設定確認"""
    print(f"\n{Fore.YELLOW}=== 翻譯設定 ==={Style.RESET_ALL}")
    print(f"目標語言: {args.target_lang}")
    print(f"輸入檔案: {args.input}")
    print(f"輸出檔案: {output_path}")
    print(f"翻譯領域: {args.domain}")
    print(f"翻譯所有項目: {args.translate_all}")
    print(f"監督模式: {args.supervised}")
    print(f"使用 DeepL: {args.use_deepl}")
    print(f"DeepL API Key: {'已設定' if args.deepl_key else '未設定'}")
    print(f"接續翻譯: {args.continue_translation}")
    print(f"測試模式: {args.test_mode}")
    
    confirm = input(f"\n{Fore.YELLOW}是否確認開始翻譯？(y/n): {Style.RESET_ALL}").lower()
    return confirm == 'y'

def main():
    args = parse_arguments()
    
    # 初始化檔案解析器
    file_parser = FileParser()
    try:
        file_type = file_parser.get_file_type(args.input)
    except ValueError as e:
        print(f"{Fore.RED}錯誤：{str(e)}{Style.RESET_ALL}")
        sys.exit(1)
    
    # 如果指定要繼續翻譯，顯示上次進度
    if args.continue_translation:
        progress = file_parser.progress_tracker.print_last_progress(args.input, args.target_lang)
        if not progress:
            print(f"{Fore.YELLOW}找不到先前的進度記錄，將從頭開始翻譯{Style.RESET_ALL}")
    
    # 生成輸出路徑
    output_path = args.output or generate_output_path(args.input, file_type)
    
    # 顯示設定並確認
    if not show_settings_confirmation(args, output_path):
        print("取消翻譯")
        return
    
    # 初始化翻譯引擎
    translator = TranslationEngine(
        use_deepl=args.use_deepl,
        deepl_api_key=args.deepl_key,
        domain=args.domain
    )
    
    # 處理翻譯
    try:
        file_parser.process_file(
            file_type=file_type,
            file_path=args.input,
            output_path=output_path,
            target_lang=args.target_lang,
            translate_all=args.translate_all,
            supervised=args.supervised,
            translator=translator,
            test_mode=args.test_mode  # 添加測試模式參數
        )
    except Exception as e:
        print(f"{Fore.RED}處理檔案時發生錯誤：{str(e)}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main()
