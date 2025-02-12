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
        """保存翻譯進度
        processed_items: dict, key為原文，value為翻譯文"""
        progress_data = {
            'file_path': file_path,
            'target_lang': target_lang,
            'last_index': current_index,
            'processed_count': len(processed_items),
            'total_count': total_count,
            'processed_items': processed_items,  # 現在是字典格式
            'output_file': self.get_last_output_path(file_path),
            'last_update': datetime.now().isoformat()
        }
        
        progress_file = self.get_progress_file(file_path, target_lang)
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
    def get_last_output_path(self, input_path):
        """從輸入檔案路徑獲取對應的最後輸出檔案路徑"""
        base_dir = os.path.dirname(input_path)
        files = [f for f in os.listdir(base_dir) if f.startswith(os.path.basename(input_path).split('.')[0])]
        if not files:
            return None
        # 按修改時間排序，取最新的
        files.sort(key=lambda x: os.path.getmtime(os.path.join(base_dir, x)), reverse=True)
        return os.path.join(base_dir, files[0])

    def print_last_progress(self, file_path, target_lang):
        """顯示上次翻譯的進度信息"""
        progress = self.load_progress(file_path, target_lang)
        if progress:
            print(f"\n=== 上次翻譯進度 ===")
            print(f"檔案: {progress['file_path']}")
            print(f"輸出: {progress.get('output_file', '未知')}")
            print(f"進度: {progress['processed_count']}/{progress['total_count']}")
            print(f"最後更新: {progress['last_update']}")
            print("==================")
        return progress
