import re
import requests
import argparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import os
import csv


def extract_paths(js_code):
    """
    从 JavaScript 代码中提取路径。
    :param js_code: JavaScript 文件的内容（字符串）。
    :return: 去重后的路径列表。
    """
    patterns = [
        r'(?:require|import)\s*\(\s*["\']([^"\']+)["\']\s*\)',  # 匹配 require 和 import
        r"n\.e\(\s*['\"]([^'\"]+)['\"]\s*\)",  # 匹配 Promise.all 中动态加载的路径
        r'path\s*:\s*["\']([^"\']+)["\']',  # 匹配 path 字段中的路径
        r'["\'](/[^"\']+)[\'"]',  # 匹配包含 / 的路径
        r'url\s*:\s*["\']([^"\']+)["\']',  # 匹配 url 字段
        r'(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']\)',  # 匹配 axios 等请求
        r'\.(?:get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']\)',  # 匹配 HTTP 方法
        r'api/[a-zA-Z0-9/_-]+',  # 匹配 api 路径
        r'v[1-9]/[a-zA-Z0-9/_-]+',  # 匹配版本号路径 如 v1/xxx
    ]

    paths = []
    for pattern in patterns:
        paths.extend(re.findall(pattern, js_code))

    # 过滤和清理路径
    cleaned_paths = []
    for path in paths:
        # 忽略常见的非 API 路径
        if any(ignore in path.lower() for ignore in ['.js', '.css', '.html', '.png', '.jpg', '.gif', '.svg']):
            continue
        # 确保路径以 / 开头
        if not path.startswith('/'):
            path = '/' + path
        cleaned_paths.append(path)

    # 去重并保持顺序
    unique_paths = list(dict.fromkeys(cleaned_paths))
    return unique_paths


def extract_js_files_from_website(url, page):
    """
    从网页中提取所有 JS 文件的 URL。
    :param url: 网站首页的 URL。
    :param page: Playwright 页面实例。
    :return: JS 文件 URL 列表。
    """
    # 打开网页
    page.goto(url, wait_until='networkidle')  # 等待网络请求完成
    
    # 获取所有网络请求
    js_urls = set()
    
    # 监听网络请求
    page.on('request', lambda request: 
        js_urls.add(request.url) if request.resource_type == 'script' else None
    )
    
    # 等待页面加载完成
    page.wait_for_load_state('networkidle')
    time.sleep(2)  # 额外等待以确保动态加载完成
    
    # 获取页面上的静态脚本
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')
    static_js = [urljoin(url, script['src']) for script in soup.find_all('script', src=True)]
    
    js_urls.update(static_js)
    return list(js_urls)


def download_js_file(js_url):
    """
    下载单个 JS 文件的内容。
    :param js_url: JS 文件的 URL。
    :return: JS 文件内容。
    """
    try:
        response = requests.get(js_url)
        response.raise_for_status()  # 确保请求成功
        return response.text
    except requests.RequestException as e:
        print(f"无法下载 JS 文件 '{js_url}': {e}")
        return ''


def extract_sensitive_info(content):
    """
    从内容中提取敏感信息。
    :param content: 要检查的内容字符串。
    :return: 字典形式的敏感信息结果。
    """
    patterns = {
        '手机号': r'1[3-9]\d{9}',
        '身份证号': r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]',
        'API密钥': r'(?i)(?:key|api[_-]?key|secret|token)["\s]*(?::|=)["\s]*[\w\-+=]{16,}',
        '邮箱': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'IP地址': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        '数据库连接串': r'(?i)(?:jdbc|mongodb|mysql|postgresql|redis)://[^\s<>"\']+',
        'AWS密钥': r'(?i)(?:AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}',
        'JWT令牌': r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*',
        'GitHub令牌': r'(?i)github[_\-\s]*token[_\-\s]*[\w\-+=]{35,40}',
        '私钥': r'-----BEGIN (?:RSA )?PRIVATE KEY-----[^-]*-----END (?:RSA )?PRIVATE KEY-----',
        '微信openid': r'(?i)openid["\s]*(?::|=)["\s]*[\w\-]{28}',
        # 新增各种ID匹配模式
        '通用ID': r'(?i)(?:"|\'|\s|^)([a-zA-Z]+[iI][dD])["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '数据库ID': r'(?i)(?:"|\'|\s|^)(?:record|row|entity|object)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '用户ID': r'(?i)(?:"|\'|\s|^)(?:user|account|member|customer)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '订单ID': r'(?i)(?:"|\'|\s|^)(?:order|transaction|payment)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '商品ID': r'(?i)(?:"|\'|\s|^)(?:product|goods|item|sku)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '设备ID': r'(?i)(?:"|\'|\s|^)(?:device|equipment|machine)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
        '会话ID': r'(?i)(?:"|\'|\s|^)(?:session|token)_?[iI][dD]["\s]*(?::|=)["\s]*["\']?([\w-]{4,})["\']?',
    }
    
    results = {}
    for info_type, pattern in patterns.items():
        matches = re.finditer(pattern, content)
        if matches:
            results[info_type] = []
            for match in matches:
                # 获取匹配文本的上下文（前后20个字符）
                start_pos = max(0, match.start() - 20)
                end_pos = min(len(content), match.end() + 20)
                context = content[start_pos:end_pos]
                
                results[info_type].append({
                    'value': match.group(),
                    'context': context,
                    'position': (match.start(), match.end())
                })
    
    return results


def save_results_to_csv(paths, sensitive_info, output_file):
    """
    将API路径和敏感信息保存到同一个CSV文件中。
    :param paths: API路径列表
    :param sensitive_info: 敏感信息字典
    :param output_file: 输出文件路径
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 将输出文件扩展名改为.csv
    csv_path = os.path.splitext(output_file)[0] + '.csv'
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow(['类型', '值', '文件', '上下文', '位置'])
        
        # 写入API路径
        for path in paths:
            writer.writerow(['API路径', path, '', '', ''])
        
        # 写入敏感信息
        for info_type, info_list in sensitive_info.items():
            for info in info_list:
                writer.writerow([
                    info_type,
                    info['value'],
                    info.get('file', 'N/A'),
                    info['context'].replace('\n', ' '),  # 移除换行符以避免CSV格式混乱
                    f"({info['position'][0]}, {info['position'][1]})"
                ])
    
    return csv_path


def extract_paths_from_website(url, output_file, page):
    """
    从网站中提取所有 JS 文件的路径和敏感信息。
    """
    js_files = extract_js_files_from_website(url, page)
    if not js_files:
        print(f"没有找到 JS 文件，退出。")
        return

    all_paths = []
    all_sensitive_info = {}

    for js_file in js_files:
        print(f"\n正在处理 JS 文件: {js_file}")
        js_code = download_js_file(js_file)
        if js_code:
            paths = extract_paths(js_code)
            all_paths.extend(paths)
            
            sensitive_info = extract_sensitive_info(js_code)
            for info_type, info_list in sensitive_info.items():
                if info_type not in all_sensitive_info:
                    all_sensitive_info[info_type] = []
                for info in info_list:
                    info['file'] = js_file
                all_sensitive_info[info_type].extend(info_list)

    unique_paths = list(dict.fromkeys(all_paths))
    
    try:
        csv_path = save_results_to_csv(unique_paths, all_sensitive_info, output_file)
        
        print(f"\n提取完成！")
        print(f"- 共提取到 {len(unique_paths)} 个API路径")
        print(f"- 发现 {len(all_sensitive_info)} 种类型的敏感信息")
        print(f"结果已保存到: {csv_path}")
        
        if all_sensitive_info:
            print("\n⚠️ 警告：发现敏感信息！请检查输出文件查看详细信息。")
            
    except Exception as e:
        print(f"保存结果时出错: {str(e)}")


def run_playwright_script(url=None, urls_file=None, output_file='api.txt'):
    """
    使用 Playwright 启动浏览器并提取网站的 JS 文件。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-web-security']  # 禁用同源策略
        )
        context = browser.new_context(
            ignore_https_errors=True,  # 忽略 HTTPS 错误
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # 设置请求超时
        page.set_default_timeout(30000)  # 30 秒
        
        try:
            if url:
                extract_paths_from_website(url, output_file, page)
            elif urls_file:
                with open(urls_file, 'r') as file:
                    urls = file.readlines()
                    for url in urls:
                        url = url.strip()
                        if url:
                            print(f"\n正在处理 URL: {url}")
                            try:
                                extract_paths_from_website(url, output_file, page)
                            except Exception as e:
                                print(f"处理 URL {url} 时出错: {str(e)}")
                                continue
            else:
                print("未指定 URL 或 URLs 文件。")
        except Exception as e:
            print(f"发生错误: {str(e)}")
        finally:
            context.close()
            browser.close()


def process_local_js_file(file_path):
    """
    处理本地 JS 文件。
    :param file_path: JS 文件路径。
    :return: 提取的路径列表。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            js_code = f.read()
        return extract_paths(js_code)
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                js_code = f.read()
            return extract_paths(js_code)
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {str(e)}")
            return []
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {str(e)}")
        return []


def process_local_directory(directory, output_file):
    """
    处理本地目录中的所有 JS 文件。
    :param directory: 目录路径。
    :param output_file: 输出文件路径。
    """
    all_paths = []
    all_sensitive_info = {}
    js_extensions = ('.js', '.jsx', '.ts', '.tsx', '.map')

    # 遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(js_extensions):
                file_path = os.path.join(root, file)
                print(f"\n正在处理文件: {file_path}")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except Exception as e:
                        print(f"处理文件 {file_path} 时出错: {str(e)}")
                        continue
                except Exception as e:
                    print(f"处理文件 {file_path} 时出错: {str(e)}")
                    continue

                paths = extract_paths(content)
                if paths:
                    all_paths.extend(paths)

                sensitive_info = extract_sensitive_info(content)
                for info_type, info_list in sensitive_info.items():
                    if info_type not in all_sensitive_info:
                        all_sensitive_info[info_type] = []
                    for info in info_list:
                        info['file'] = file_path
                    all_sensitive_info[info_type].extend(info_list)

    unique_paths = list(dict.fromkeys(all_paths))
    
    try:
        csv_path = save_results_to_csv(unique_paths, all_sensitive_info, output_file)
        
        print(f"\n提取完成！")
        print(f"- 共提取到 {len(unique_paths)} 个API路径")
        print(f"- 发现 {len(all_sensitive_info)} 种类型的敏感信息")
        print(f"结果已保存到: {csv_path}")
        
        if all_sensitive_info:
            print("\n⚠️ 警告：发现敏感信息！请检查输出文件查看详细信息。")
            
    except Exception as e:
        print(f"保存结果时出错: {str(e)}")


def main():
    """
    主函数，处理命令行参数并执行相应的操作。
    """
    parser = argparse.ArgumentParser(description="提取 JS 文件中的 API 路径")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-u', '--url', type=str, help='指定单个 URL')
    group.add_argument('-l', '--urls-file', type=str, help='指定包含多个 URL 的文件')
    group.add_argument('-d', '--directory', type=str, help='指定本地目录路径')
    parser.add_argument('-o', '--output-file', type=str, default='api_paths.txt', 
                        help='指定输出文件名 (默认为 api_paths.txt)')

    args = parser.parse_args()

    if args.directory:
        # 处理本地目录
        if not os.path.isdir(args.directory):
            print(f"错误：目录 '{args.directory}' 不存在")
            return
        process_local_directory(args.directory, args.output_file)
    else:
        # 处理 URL
        run_playwright_script(url=args.url, urls_file=args.urls_file, 
                            output_file=args.output_file)


if __name__ == "__main__":
    main()
