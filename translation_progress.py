import json
import os
from datetime import datetime

class TranslationProgress:
    def __init__(self, progress_dir=".progress"):
        self.progress_dir = progress_dir
        self.ensure_progress_dir()
        
    def ensure_progress_dir(self):
        """確保進度目錄存在"""
        if not os.path.exists(self.progress_dir):
            os.makedirs(self.progress_dir)
    
    def get_progress_file(self, file_path, target_lang):
        """生成進度檔案路徑"""
        file_hash = hash(file_path + target_lang)
        return os.path.join(self.progress_dir, f"progress_{file_hash}.json")
    
    def load_progress(self, file_path, target_lang):
        """載入翻譯進度"""
        progress_file = self.get_progress_file(file_path, target_lang)
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"找到先前進度：已處理 {data['processed_count']}/{data['total_count']} 個項目")
                    return data
            except Exception as e:
                print(f"載入進度檔案時發生錯誤: {e}")
        return None
    
    def save_progress(self, file_path, target_lang, current_index, total_count, processed_items):
        """保存翻譯進度"""
        progress_data = {
            'file_path': file_path,
            'target_lang': target_lang,
            'last_index': current_index,
            'processed_count': len(processed_items),
            'total_count': total_count,
            'processed_items': processed_items,
            'last_update': datetime.now().isoformat()
        }
        
        progress_file = self.get_progress_file(file_path, target_lang)
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
