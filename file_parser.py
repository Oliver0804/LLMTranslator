from lxml import etree
import json
from colorama import Fore, Style

class FileParser:
    def get_file_type(self, file_path):
        """
        根據檔案副檔名判斷檔案類型
        """
        ext = file_path.lower().split('.')[-1]
        if ext == 'xliff':
            return 'xliff'
        elif ext == 'xcstrings':
            return 'xcstrings'
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")
    
    def process_file(self, file_type, file_path, output_path, target_lang, 
                    translate_all, supervised, translator):
        """
        根據檔案類型選擇適當的處理方法
        """
        if file_type == 'xliff':
            self._process_xliff(file_path, output_path, target_lang, 
                              translate_all, supervised, translator)
        elif file_type == 'xcstrings':
            self._process_xcstrings(file_path, output_path, target_lang, 
                                  translate_all, supervised, translator)
    
    def _process_xliff(self, file_path, output_path, target_lang, 
                      translate_all, supervised, translator):
        """處理 XLIFF 檔案的翻譯"""
        ns = {"xliff": "urn:oasis:names:tc:xliff:document:1.2"}
        
        with open(file_path, "r", encoding="utf-8") as file:
            xliff_content = file.read()
        
        root = etree.fromstring(xliff_content.encode("utf-8"))
        
        trans_units = root.findall(".//xliff:trans-unit", ns)
        total_units = len(trans_units)
        print(f"\n{Fore.CYAN}找到 {total_units} 個翻譯單元{Style.RESET_ALL}")
        
        for i, unit in enumerate(trans_units):
            print(f"\n{Fore.YELLOW}處理第 {i+1}/{total_units} 個單元 (ID: {unit.get('id', 'N/A')}){Style.RESET_ALL}")
            source = unit.find("xliff:source", ns)
            target = unit.find("xliff:target", ns)
            
            if target is not None:
                current_state = target.get("state", "")
                needs_translation = current_state == "needs-translation"
                
                if current_state == "translated" and translate_all:
                    print(f"\n{Fore.YELLOW}檢查已翻譯內容品質...{Style.RESET_ALL}")
                    print(f"原文: {source.text}")
                    print(f"現有翻譯: {target.text}")
                    score = translator.evaluate_translation_quality(source.text, target.text)
                    print(f"{Fore.YELLOW}現有翻譯評分: {score}{Style.RESET_ALL}")
                    
                    if score < 85:
                        print(f"{Fore.YELLOW}現有翻譯品質不佳，進行重新翻譯{Style.RESET_ALL}")
                        needs_translation = True
                    else:
                        print(f"{Fore.GREEN}現有翻譯品質良好，保持不變{Style.RESET_ALL}")
                        print("=====")
                        continue
                
                if translate_all or needs_translation:
                    translated_text = translator.translate(source.text, target_lang)
                    
                    if supervised:
                        choice = input(f"\n{Fore.YELLOW}是否接受此翻譯？(y/n): {Style.RESET_ALL}").lower()
                        if choice != 'y':
                            print("跳過此翻譯")
                            print("=====")
                            continue
                    
                    target.text = translated_text
                    target.set("state", "translated")
                    print(f"{Fore.GREEN}>>> 更新翻譯: {translated_text}{Style.RESET_ALL}")
                    print("=====")
        
        translator.stats.print_stats()
        with open(output_path, "wb") as file:
            file.write(etree.tostring(root, pretty_print=True, encoding="utf-8"))
        print(f"翻譯完成，已儲存到 {output_path}")

    def _process_xcstrings(self, file_path, output_path, target_lang, 
                          translate_all, supervised, translator):
        """處理 xcstrings 檔案的翻譯"""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        strings = data.get('strings', {})
        total_strings = len(strings)
        print(f"\n{Fore.CYAN}找到 {total_strings} 個字串需要翻譯{Style.RESET_ALL}")
        
        for i, (key, content) in enumerate(strings.items()):
            print(f"\n{Fore.YELLOW}處理第 {i+1}/{total_strings} 個字串{Style.RESET_ALL}")
            print(f"鍵值: {key}")
            
            localizations = content.get('localizations', {})
            target_localization = localizations.get(target_lang, {})
            
            # 檢查是否已有翻譯
            if target_lang in localizations and not translate_all:
                string_unit = target_localization.get('stringUnit', {})
                if string_unit.get('state') == 'translated':
                    print(f"{Fore.GREEN}已有翻譯，跳過{Style.RESET_ALL}")
                    continue
            
            # 使用英文版作為原文
            source_text = key
            if 'en' in localizations:
                en_unit = localizations.get('en', {}).get('stringUnit', {})
                if en_unit.get('value'):
                    source_text = en_unit['value']
            
            translated_text = translator.translate(source_text, target_lang)
            
            if supervised:
                choice = input(f"\n{Fore.YELLOW}是否接受此翻譯？(y/n): {Style.RESET_ALL}").lower()
                if choice != 'y':
                    print("跳過此翻譯")
                    continue
            
            if target_lang not in localizations:
                localizations[target_lang] = {}
            
            localizations[target_lang] = {
                'stringUnit': {
                    'state': 'translated',
                    'value': translated_text
                }
            }
            
            print(f"{Fore.GREEN}>>> 更新翻譯: {translated_text}{Style.RESET_ALL}")
        
        translator.stats.print_stats()
        
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"翻譯完成，已儲存到 {output_path}")
