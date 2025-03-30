import json
import time
import uuid
import re
import os
import sys
import requests
import hashlib
import hmac
import base64
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging
from colorama import Fore, Style, init

# 初始化 colorama
init(autoreset=True)

# 设置环境变量
os.environ['ALIBABA_ACCESS_KEY_ID'] = "YOUR_ACCESS_KEY_ID"  # 替换为你的AccessKeyId
os.environ['ALIBABA_ACCESS_KEY_SECRET'] = "YOUR_ACCESS_KEY_SECRET"  # 替换为你的AccessKeySecret

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("translate.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlibabaTranslator:
    def __init__(self, access_key_id, access_key_secret, target_language="zh", source_language="auto"):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.target_language = target_language
        self.source_language = source_language
        self.url = "http://mt.cn-hangzhou.aliyuncs.com/api/translate/web/general"
        self.max_workers = 20  # 并发线程数
        self.request_interval = 0.1  # 请求间隔时间(秒)
        
        # 正则表达式，用于识别标题、列表和代码块等
        self.md_title_pattern = re.compile(r'^#{1,6}\s+(.+)$')
        self.md_list_pattern = re.compile(r'^(\s*[-*+]\s+)(.+)$')
        self.md_ordered_list_pattern = re.compile(r'^(\s*\d+\.\s+)(.+)$')
        self.md_code_block_pattern = re.compile(r'^```[a-zA-Z]*$')
        self.md_inline_code_pattern = re.compile(r'`([^`]+)`')
        self.md_link_pattern = re.compile(r'$$([^$$]+)\]$([^)]+)$')
        
        # 不翻译的内容类型
        self.skip_translate_types = ["code_block", "inline_code", "url", "empty"]
    
    def translate_text(self, text, retry_count=3):
        """翻译单个文本片段，支持重试"""
        if not text.strip():
            return text  # 返回空文本
        
        for attempt in range(retry_count):
            try:
                # 准备请求体
                body = {
                    "FormatType": "text",
                    "SourceLanguage": self.source_language,
                    "TargetLanguage": self.target_language,
                    "SourceText": text,
                    "Scene": "general"
                }
                
                body_str = json.dumps(body, ensure_ascii=False)
                body_bytes = body_str.encode('utf-8')

                # 计算 Content-MD5
                content_md5 = base64.b64encode(hashlib.md5(body_bytes).digest()).decode('utf-8')
                
                # 生成请求头
                date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
                nonce = str(uuid.uuid4())

                # 准备签名字符串
                string_to_sign = (
                    "POST\n"
                    "application/json\n"
                    f"{content_md5}\n"
                    "application/json\n"
                    f"{date}\n"
                    f"x-acs-signature-method:HMAC-SHA1\n"
                    f"x-acs-signature-nonce:{nonce}\n"
                    f"x-acs-signature-version:1.0\n"
                    "/api/translate/web/general"
                )
                
                # 计算签名
                signature = base64.b64encode(
                    hmac.new(
                        self.access_key_secret.encode('utf-8'),
                        string_to_sign.encode('utf-8'),
                        hashlib.sha1
                    ).digest()
                ).decode('utf-8')

                # 设置请求头
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Content-MD5': content_md5,
                    'Date': date,
                    'Host': 'mt.cn-hangzhou.aliyuncs.com',
                    'x-acs-signature-nonce': nonce,
                    'x-acs-signature-method': 'HMAC-SHA1',
                    'x-acs-signature-version': '1.0',
                    'Authorization': f'acs {self.access_key_id}:{signature}'
                }

                # 发送请求
                response = requests.post(self.url, data=body_bytes, headers=headers)

                # 解析响应
                if response.status_code == 200:
                    result = response.json()
                    if result.get('Code') == '200':
                        time.sleep(self.request_interval)  # 避免请求过快
                        return result.get('Data', {}).get('Translated')
                    else:
                        logger.warning(f"翻译错误: {result.get('Message', '未知错误')} (尝试 {attempt+1}/{retry_count})")
                        if attempt < retry_count - 1:
                            time.sleep(1 * (attempt + 1))  # 指数级退避
                            continue
                        return f"[翻译错误] {text}"
                else:
                    logger.warning(f"请求错误: HTTP {response.status_code} (尝试 {attempt+1}/{retry_count})")
                    if attempt < retry_count - 1:
                        time.sleep(1 * (attempt + 1))  # 指数级退避
                        continue
                    return f"[请求错误] {text}"
                
            except Exception as e:
                logger.error(f"处理文本时出错: {e} (尝试 {attempt+1}/{retry_count})")
                if attempt < retry_count - 1:
                    time.sleep(1 * (attempt + 1))  # 指数级退避
                    continue
                return f"[处理错误] {text}"
                
        return f"[多次尝试后失败] {text}"

    def analyze_line(self, line):
        """分析行的类型和内容，以决定如何翻译"""
        line = line.rstrip('\n')
        
        # 空行
        if not line.strip():
            return {"type": "empty", "content": line, "prefix": "", "suffix": ""}
        
        # 检查是否为标题
        title_match = self.md_title_pattern.match(line)
        if title_match:
            prefix = line[:line.find(title_match.group(1))]
            return {"type": "title", "content": title_match.group(1), "prefix": prefix, "suffix": ""}
        
        # 检查是否为无序列表
        list_match = self.md_list_pattern.match(line)
        if list_match:
            return {"type": "list", "content": list_match.group(2), "prefix": list_match.group(1), "suffix": ""}
        
        # 检查是否为有序列表
        ordered_list_match = self.md_ordered_list_pattern.match(line)
        if ordered_list_match:
            return {"type": "ordered_list", "content": ordered_list_match.group(2), "prefix": ordered_list_match.group(1), "suffix": ""}
        
        # 检查是否为代码块标记
        if self.md_code_block_pattern.match(line):
            return {"type": "code_block_marker", "content": line, "prefix": "", "suffix": ""}
            
        # 处理行内代码和链接
        processed_line = line
        inline_code_matches = self.md_inline_code_pattern.findall(line)
        link_matches = self.md_link_pattern.findall(line)
        
        if inline_code_matches or link_matches:
            # 保存需要特殊处理的部分
            replacements = {}
            
            # 处理行内代码
            for i, code in enumerate(inline_code_matches):
                placeholder = f"__CODE_{i}__"
                processed_line = processed_line.replace(f"`{code}`", placeholder)
                replacements[placeholder] = f"`{code}`"
            
            # 处理链接
            for i, (text, url) in enumerate(link_matches):
                placeholder = f"__LINK_{i}__"
                processed_line = processed_line.replace(f"[{text}]({url})", placeholder)
                replacements[placeholder] = {"text": text, "url": url}
            
            return {"type": "mixed", "content": processed_line, "replacements": replacements, "prefix": "", "suffix": ""}
        
        # 普通文本
        return {"type": "text", "content": line, "prefix": "", "suffix": ""}

    def process_mixed_content(self, analysis, translated_text):
        """处理包含代码和链接的混合内容"""
        result = translated_text
        
        for placeholder, replacement in analysis["replacements"].items():
            if isinstance(replacement, dict):  # 链接
                # 仅翻译链接文本，保留URL
                translated_link_text = self.translate_text(replacement["text"])
                result = result.replace(placeholder, f"[{translated_link_text}]({replacement['url']})")
            else:  # 代码
                result = result.replace(placeholder, replacement)
                
        return result

    def translate_file(self, input_file, output_file, batch_size=50):
        """翻译整个 Markdown 文件，添加批处理功能"""
        try:
            # 确保输入文件存在
            if not os.path.exists(input_file):
                logger.error(f"输入文件不存在: {input_file}")
                return False
                
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 读取输入文件
            with open(input_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                
            # 分析每一行
            analyses = [self.analyze_line(line) for line in lines]
            
            # 是否在代码块内部（不需要翻译）
            in_code_block = False
            
            # 处理每一行
            translated_lines = []
            tasks = []
            
            logger.info(f"开始翻译文件: {input_file} -> {output_file} (共 {len(lines)} 行)")
            
            # 提前准备翻译任务
            for i, analysis in enumerate(analyses):
                if analysis["type"] == "code_block_marker":
                    in_code_block = not in_code_block
                    tasks.append(None)  # 占位符，不需要翻译
                elif in_code_block or analysis["type"] in self.skip_translate_types:
                    tasks.append(None)  # 占位符，不需要翻译
                else:
                    tasks.append({"index": i, "content": analysis["content"]})
            
            # 使用 ThreadPoolExecutor 进行并行翻译
            # 分批处理，避免同时创建过多线程
            translations = {}
            active_tasks = [task for task in tasks if task is not None]
            total_tasks = len(active_tasks)
            
            logger.info(f"需要翻译的行数: {total_tasks}")
            
            for batch_start in range(0, total_tasks, batch_size):
                batch_end = min(batch_start + batch_size, total_tasks)
                batch_tasks = active_tasks[batch_start:batch_end]
                
                logger.info(f"处理批次 {batch_start//batch_size + 1}, 行 {batch_start+1}-{batch_end} (共 {len(batch_tasks)} 行)")
                
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {}
                    for task in batch_tasks:
                        future = executor.submit(self.translate_text, task["content"])
                        futures[future] = task["index"]
                    
                    for future in futures:
                        index = futures[future]
                        try:
                            translations[index] = future.result()
                        except Exception as e:
                            logger.error(f"翻译第 {index+1} 行时出错: {e}")
                            translations[index] = f"[翻译失败] {analyses[index]['content']}"
            
            # 构建最终翻译结果
            in_code_block = False
            for i, analysis in enumerate(analyses):
                if analysis["type"] == "code_block_marker":
                    in_code_block = not in_code_block
                    translated_lines.append(analysis["content"])
                elif in_code_block or analysis["type"] in self.skip_translate_types:
                    translated_lines.append(analyses[i]["content"])
                else:
                    if analysis["type"] == "mixed":
                        # 处理混合内容（包含代码和链接）
                        translated_content = self.process_mixed_content(analysis, translations.get(i, "[翻译丢失]"))
                    else:
                        translated_content = translations.get(i, "[翻译丢失]")
                    
                    # 重新构建行，保留前缀和后缀
                    translated_line = f"{analysis['prefix']}{translated_content}{analysis['suffix']}"
                    translated_lines.append(translated_line)
            
            # 写入输出文件
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write('\n'.join(translated_lines))
                
            logger.info(f"翻译完成! 共处理 {len(lines)} 行，结果已保存到 {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"处理文件时出错: {e}")
            return False

def validate_file(file_path):
    """验证文件路径是否有效"""
    if not os.path.exists(file_path):
        raise argparse.ArgumentTypeError(f"文件不存在: {file_path}")
    return file_path

def get_default_output_filename(input_file):
    """根据输入文件生成默认输出文件名"""
    base_name, ext = os.path.splitext(input_file)
    return f"{base_name}_translated{ext}"

def main():
    # 打印工具名称和作者信息
    print(Fore.CYAN + Style.BRIGHT + "\n" + "="*50)
    print(Fore.MAGENTA + Style.BRIGHT + "阿里云Markdown翻译 V1.0")
    print(Fore.YELLOW + Style.BRIGHT + "作者: Zero_Tu")
    print(Fore.CYAN + Style.BRIGHT + "="*50 + "\n")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='阿里云机器翻译工具 - 支持Markdown格式翻译')
    parser.add_argument('-f', '--file', type=validate_file, required=True, 
                        help='要翻译的输入文件路径')
    parser.add_argument('-o', '--output', type=str,
                        help='翻译结果输出文件路径 (默认为: <输入文件名>_translated.<扩展名>)')
    parser.add_argument('-s', '--source', type=str, default='auto',
                        help='源语言代码 (默认: auto)')
    parser.add_argument('-t', '--target', type=str, default='zh',
                        help='目标语言代码 (默认: zh)')
    parser.add_argument('--threads', type=int, default=20,
                        help='并发线程数 (默认: 20)')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='批处理大小 (默认: 50)')
    parser.add_argument('--interval', type=float, default=0.1,
                        help='请求间隔时间，秒 (默认: 0.1)')
    
    args = parser.parse_args()
    
    # 获取 API 密钥 (从环境变量获取)
    access_key_id = os.environ.get('ALIBABA_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('ALIBABA_ACCESS_KEY_SECRET')
    
    if not access_key_id or not access_key_secret:
        logger.error("错误: 未提供阿里云 API 密钥。请在代码中设置正确的环境变量值。")
        return 1
    
    # 生成输出文件名（如果未提供）
    output_file = args.output or get_default_output_filename(args.file)
    
    # 初始化翻译器
    translator = AlibabaTranslator(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        source_language=args.source,
        target_language=args.target
    )
    
    # 设置性能参数
    translator.max_workers = args.threads
    translator.request_interval = args.interval
    
    # 执行翻译
    logger.info(Fore.GREEN + "=== 阿里云翻译工具 ===")
    logger.info(f"输入文件: {args.file}")
    logger.info(f"输出文件: {output_file}")
    logger.info(f"语言: {args.source} -> {args.target}")
    logger.info(f"性能设置: 线程={args.threads}, 批大小={args.batch_size}, 间隔={args.interval}秒")
    
    start_time = time.time()
    success = translator.translate_file(args.file, output_file, args.batch_size)
    end_time = time.time()
    
    if success:
        logger.info(Fore.GREEN + f"总耗时: {end_time - start_time:.2f} 秒")
        return 0
    else:
        logger.error("翻译过程中出现错误，请检查日志了解详情。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
