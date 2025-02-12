from lxml import etree
import json
from colorama import Fore, Style
from translation_progress import TranslationProgress
import os
from datetime import datetime

class FileParser:
    def __init__(self):
        self.progress_tracker = TranslationProgress()
        # 確保日誌目錄存在
        self.log_dir = "./log"
        os.makedirs(self.log_dir, exist_ok=True)
        # 建立日誌檔案名稱
        self.log_file = os.path.join(self.log_dir, f"{datetime.now().strftime('%Y%m%d')}.txt")
        
    def log_translation(self, source, target, translated, file_type, accepted=True):
        """記錄翻譯結果到日誌"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"時間: {timestamp}\n")
            f.write(f"檔案類型: {file_type}\n")
            f.write(f"原文: {source}\n")
            if target:
                f.write(f"原翻譯: {target}\n")
            f.write(f"新翻譯: {translated}\n")
            f.write(f"狀態: {'已接受' if accepted else '已拒絕'}\n")
            f.write("-" * 50 + "\n")

    def get_file_type(self, file_path):
        """
        根據檔案副檔名判斷檔案類型
        """
        ext = file_path.lower().split('.')[-1]
        if ext == 'xliff':
            return 'xliff'
        elif ext == 'xcstrings':
            return 'xcstrings'
        elif ext == 'po':
            return 'po'
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")
    
    def process_file(self, file_type, file_path, output_path, target_lang, 
                    translate_all, supervised, translator, test_mode=False):
        """
        根據檔案類型選擇適當的處理方法
        """
        if file_type == 'xliff':
            self._process_xliff(file_path, output_path, target_lang, 
                              translate_all, supervised, translator, test_mode)
        elif file_type == 'xcstrings':
            self._process_xcstrings(file_path, output_path, target_lang, 
                                  translate_all, supervised, translator, test_mode)
        elif file_type == 'po':
            self._process_po(file_path, output_path, target_lang, 
                           translate_all, supervised, translator, test_mode)
    
    def _process_xliff(self, file_path, output_path, target_lang, 
                      translate_all, supervised, translator, test_mode=False):
        """處理 XLIFF 檔案的翻譯"""
        ns = {"xliff": "urn:oasis:names:tc:xliff:document:1.2"}
        
        with open(file_path, "r", encoding="utf-8") as file:
            xliff_content = file.read()
        
        root = etree.fromstring(xliff_content.encode("utf-8"))
        trans_units = root.findall(".//xliff:trans-unit", ns)
        total_units = len(trans_units)
        if test_mode:
            print(f"{Fore.YELLOW}測試模式：只翻譯前20個條目{Style.RESET_ALL}")
            total_units = min(20, total_units)
        translator.stats.set_total_entries(total_units)
        
        # 載入進度
        progress = self.progress_tracker.load_progress(file_path, target_lang)
        processed_items = set(progress['processed_items']) if progress else set()
        start_index = progress['last_index'] + 1 if progress else 0
        
        print(f"\n{Fore.CYAN}找到 {total_units} 個翻譯單元{Style.RESET_ALL}")
        if progress:
            print(f"{Fore.GREEN}從第 {start_index + 1} 個單元繼續翻譯{Style.RESET_ALL}")
        
        try:
            for i, unit in enumerate(trans_units[start_index:], start=start_index):
                unit_id = unit.get('id', '')
                if unit_id in processed_items:
                    continue
                
                print(f"\n{Fore.YELLOW}處理第 {i+1}/{total_units} 個單元 (ID: {unit_id}){Style.RESET_ALL}")
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
                        
                        if score < translator.SCORE_THRESHOLD_EXISTING:  # 使用類別中定義的閾值
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
                
                # 記錄處理過的項目
                processed_items.add(unit_id)
                
                # 每處理10個項目保存一次進度
                if len(processed_items) % 10 == 0:
                    self.progress_tracker.save_progress(
                        file_path, target_lang, i, total_units, list(processed_items)
                    )
                    
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}檢測到中斷，保存進度...{Style.RESET_ALL}")
            self.progress_tracker.save_progress(
                file_path, target_lang, i, total_units, list(processed_items)
            )
            raise
        
        # 完成後保存最終進度
        self.progress_tracker.save_progress(
            file_path, target_lang, total_units-1, total_units, list(processed_items)
        )
        
        translator.stats.print_stats()
        with open(output_path, "wb") as file:
            file.write(etree.tostring(root, pretty_print=True, encoding="utf-8"))
        print(f"翻譯完成，已儲存到 {output_path}")

    def _process_xcstrings(self, file_path, output_path, target_lang, 
                          translate_all, supervised, translator, test_mode=False):
        """處理 xcstrings 檔案的翻譯"""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        strings = data.get('strings', {})
        total_strings = len(strings)
        if test_mode:
            print(f"{Fore.YELLOW}測試模式：只翻譯前20個條目{Style.RESET_ALL}")
            total_strings = min(20, total_strings)
        translator.stats.set_total_entries(total_strings)
        
        # 載入進度
        progress = self.progress_tracker.load_progress(file_path, target_lang)
        processed_items = set(progress['processed_items']) if progress else set()
        start_index = progress['last_index'] + 1 if progress else 0
        
        print(f"\n{Fore.CYAN}找到 {total_strings} 個字串需要翻譯{Style.RESET_ALL}")
        if progress:
            print(f"{Fore.GREEN}從第 {start_index + 1} 個字串繼續翻譯{Style.RESET_ALL}")
        
        try:
            for i, (key, content) in enumerate(list(strings.items())[start_index:], start=start_index):
                if key in processed_items:
                    continue
                    
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
                
                # 記錄處理過的項目
                processed_items.add(key)
                
                # 每處理10個項目保存一次進度
                if len(processed_items) % 10 == 0:
                    self.progress_tracker.save_progress(
                        file_path, target_lang, i, total_strings, list(processed_items)
                    )
                    
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}檢測到中斷，保存進度...{Style.RESET_ALL}")
            self.progress_tracker.save_progress(
                        file_path, target_lang, i, total_strings, list(processed_items)
                    )
            raise
            
        # 完成後保存最終進度
        self.progress_tracker.save_progress(
            file_path, target_lang, total_strings-1, total_strings, list(processed_items)
        )
        
        translator.stats.print_stats()
        
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"翻譯完成，已儲存到 {output_path}")

    def _process_po(self, file_path, output_path, target_lang, 
                    translate_all, supervised, translator, test_mode=False):
        """處理 .po 檔案的翻譯"""
        import polib
        import shutil
        
        # 先複製原始檔案到輸出路徑
        shutil.copy2(file_path, output_path)
        
        # 使用輸出檔案進行後續操作
        po = polib.pofile(output_path)  # 移除 encoding 參數
        total_entries = len(po)
        processed_count = 0  # 追蹤實際處理的條目數
        
        # 設定最大處理條目數
        max_entries = 20 if test_mode else total_entries
        if test_mode:
            print(f"{Fore.YELLOW}測試模式：只翻譯前{max_entries}個條目{Style.RESET_ALL}")
            total_entries = max_entries
        
        translator.stats.set_total_entries(total_entries)
        
        # 載入進度
        progress = self.progress_tracker.load_progress(file_path, target_lang)
        processed_items = progress['processed_items'] if progress else {}  # 改為字典
        start_index = progress['last_index'] + 1 if progress else 0
        
        print(f"\n{Fore.CYAN}找到 {total_entries} 個翻譯單元{Style.RESET_ALL}")
        if progress:
            print(f"{Fore.GREEN}從第 {start_index + 1} 個單元繼續翻譯{Style.RESET_ALL}")
        
        try:
            for i, entry in enumerate(po[start_index:], start=start_index):
                # 檢查是否達到處理上限
                if processed_count >= max_entries:
                    print(f"\n{Fore.YELLOW}已達到處理上限 ({max_entries} 個條目)，儲存並結束翻譯{Style.RESET_ALL}")
                    break
                
                if entry.obsolete or entry.msgid in processed_items:
                    # 顯示已有的翻譯記錄
                    if entry.msgid in processed_items:
                        print(f"{Fore.CYAN}使用已有翻譯記錄：{processed_items[entry.msgid]}{Style.RESET_ALL}")
                    continue
                
                print(f"\n{Fore.YELLOW}處理第 {processed_count+1}/{max_entries} 個單元{Style.RESET_ALL}")
                print(f"原文: {entry.msgid}")
                
                # 評估現有翻譯
                original_translation = entry.msgstr
                if original_translation:
                    print(f"現有翻譯: {original_translation}")
                    score = translator.evaluate_translation_quality(entry.msgid, original_translation)
                    print(f"{Fore.BLUE}現有翻譯評分: {score}{Style.RESET_ALL}")
                    
                    if not translate_all:
                        print(f"{Fore.GREEN}保持現有翻譯{Style.RESET_ALL}")
                        self.log_translation(entry.msgid, None, original_translation, 'po', True)
                        continue
                    elif score >= translator.SCORE_THRESHOLD_SKIP:  # 使用類別中定義的閾值
                        print(f"{Fore.GREEN}現有翻譯品質良好 ({score}分)，保持不變{Style.RESET_ALL}")
                        self.log_translation(entry.msgid, None, original_translation, 'po', True)
                        continue
                    else:
                        print(f"{Fore.YELLOW}需要重新翻譯 (分數：{score}){Style.RESET_ALL}")
                
                # 處理帶有格式字符的字串
                if '%' in entry.msgid:
                    translated = self._translate_with_formats(
                        entry.msgid, self._extract_format_specs(entry.msgid), 
                        translator, target_lang
                    )
                else:
                    translated = translator.translate(entry.msgid, target_lang)
                
                # 監督模式的處理
                accepted = True
                if supervised:
                    print(f"\n{Fore.CYAN}建議翻譯: {translated}{Style.RESET_ALL}")
                    if original_translation:
                        print(f"{Fore.YELLOW}原有翻譯: {original_translation}{Style.RESET_ALL}")
                    
                    choice = input(f"\n{Fore.YELLOW}是否接受此翻譯？(y/n): {Style.RESET_ALL}").lower()
                    if choice != 'y':
                        print(f"{Fore.GREEN}保持原有翻譯{Style.RESET_ALL}")
                        accepted = False
                        if original_translation:
                            translated = original_translation
                        else:
                            print("跳過此翻譯")
                            continue
                
                entry.msgstr = translated
                
                # 記錄翻譯結果
                self.log_translation(entry.msgid, original_translation, translated, 'po', accepted)
                
                # 更新統計
                if original_translation and original_translation != translated:
                    translator.stats.increment_modified()
                else:
                    translator.stats.increment_new()
                
                # 記錄處理過的項目，使用字典格式
                processed_items[entry.msgid] = translated
                
                # 每10個條目或達到上限時儲存進度和檔案
                if processed_count % 10 == 0 or processed_count >= max_entries:
                    self.progress_tracker.save_progress(
                        file_path, target_lang, i, total_entries, processed_items
                    )
                    po.save(output_path)  # 移除 encoding 參數
                
                processed_count += 1  # 增加已處理計數
                    
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}檢測到中斷，保存進度...{Style.RESET_ALL}")
            self.progress_tracker.save_progress(
                file_path, target_lang, i, total_entries, processed_items
            )
            po.save(output_path)  # 移除 encoding 參數
            raise
        
        # 完成後保存最終進度
        self.progress_tracker.save_progress(
            file_path, target_lang, total_entries-1, total_entries, processed_items
        )
        
        translator.stats.set_output_file(output_path)
        po.save(output_path)  # 移除 encoding 參數
        translator.stats.print_stats()
        print(f"翻譯完成，已儲存到 {output_path}")
    
    def _extract_format_specs(self, text):
        """提取格式說明符，只用於檢測，不替換"""
        import re
        format_specs = re.findall(r'%(?:\d+\$)?[+-]?(?:\d+)?(?:\.\d+)?[diufFeEgGxXoscpaA%]', text)
        return format_specs

    def _translate_with_formats(self, text, format_specs, translator, target_lang):
        """直接使用原始文本進行翻譯，添加格式說明提示詞"""
        print(f"檢測到的格式說明符: {format_specs}")
        
        extra_prompt = """
        注意：這個文本包含格式說明符，必須：
        1. 完全保持格式說明符不變，包括 %s、%d 等
        2. 保持格式說明符的原始順序
        3. 保持格式說明符前後的空格
        4. 格式說明符不需要翻譯，直接保留原樣
        """
        
        # 直接翻譯原始文本
        return translator.translate(
            text=text,
            target_lang=target_lang,
            extra_prompt=extra_prompt
        )
