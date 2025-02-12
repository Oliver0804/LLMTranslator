import argparse
from colorama import init, Fore, Style
from datetime import datetime
import os
from translation_engine import TranslationEngine
from file_parser import FileParser

init()

def get_output_filename(input_path, target_lang):
    """
    根據輸入檔名生成輸出檔名，保持原始副檔名
    格式：原檔名_語言_年月日時分.原副檔名
    """
    base_name = os.path.splitext(input_path)[0]
    ext = os.path.splitext(input_path)[1]
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    return f"{base_name}_{target_lang}_{timestamp}{ext}"

def main():
    parser = argparse.ArgumentParser(description="翻譯工具")
    parser.add_argument("-t", "--target-lang", required=True, help="目標語言，如 ZH-HANT")
    parser.add_argument("-i", "--input", required=True, help="輸入文件")
    parser.add_argument("-all", action="store_true", help="翻譯所有內容，包括已翻譯的")
    parser.add_argument("-supervised", action="store_true", help="啟用監督模式，每次翻譯後需要確認")
    parser.add_argument("-deepl", action="store_true", help="使用 DeepL API 進行翻譯")
    parser.add_argument("--deepl-key", type=str, help="DeepL API 金鑰")
    parser.add_argument("-d", "--domain", default="軟體介面", type=str,
                       help="翻譯領域，例如：軟體介面、醫療、法律、工程技術等")
    
    args = parser.parse_args()
    
    # 創建檔案解析器和翻譯引擎實例
    file_parser = FileParser()
    translator = TranslationEngine(use_deepl=args.deepl, 
                                 deepl_api_key=args.deepl_key,
                                 domain=args.domain)
    
    # 取得檔案類型和輸出路徑
    try:
        file_type = file_parser.get_file_type(args.input)
        print(f"檔案類型: {file_type}")
    except ValueError as e:
        print(f"{Fore.RED}錯誤: {e}{Style.RESET_ALL}")
        return

    output_path = get_output_filename(args.input, args.target_lang)
    
    # 顯示設定確認
    print(f"\n{Fore.YELLOW}=== 翻譯設定 ==={Style.RESET_ALL}")
    print(f"目標語言: {args.target_lang}")
    print(f"輸入檔案: {args.input}")
    print(f"輸出檔案: {output_path}")
    print(f"翻譯領域: {args.domain}")
    print(f"翻譯所有項目: {args.all}")
    print(f"監督模式: {args.supervised}")
    print(f"使用 DeepL: {args.deepl}")
    print(f"DeepL API Key: {'已設定' if args.deepl_key else '未設定'}")
    
    confirm = input(f"\n{Fore.YELLOW}是否確認開始翻譯？(y/n): {Style.RESET_ALL}").lower()
    if confirm != 'y':
        print("取消翻譯")
        return
    
    # 進行翻譯處理
    file_parser.process_file(
        file_type=file_type,
        file_path=args.input,
        output_path=output_path,
        target_lang=args.target_lang,
        translate_all=args.all,
        supervised=args.supervised,
        translator=translator
    )

if __name__ == "__main__":
    main()
