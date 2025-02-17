import re
import requests
import argparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import os


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


def extract_paths_from_website(url, output_file, page):
    """
    从网站中提取所有 JS 文件的路径，并保存到输出文件，同时打印到控制台。
    :param url: 网站首页的 URL。
    :param output_file: 输出文件路径。
    :param page: Playwright 页面实例。
    """
    js_files = extract_js_files_from_website(url, page)
    if not js_files:
        print(f"没有找到 JS 文件，退出。")
        return

    all_paths = []

    for js_file in js_files:
        print(f"正在处理 JS 文件: {js_file}")
        js_code = download_js_file(js_file)
        if js_code:
            paths = extract_paths(js_code)
            all_paths.extend(paths)

    # 去重并保持顺序
    unique_paths = list(dict.fromkeys(all_paths))

    # 将路径同时打印到控制台并保存到输出文件
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            for path in unique_paths:
                print(path)  # 打印到控制台
                file.write(path + '\n')  # 保存到文件

        print(f"路径提取完成！共提取到 {len(unique_paths)} 个路径，结果已保存到 '{output_file}'。")
    except Exception as e:
        print(f"发生错误：{e}")


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
    js_extensions = ('.js', '.jsx', '.ts', '.tsx', '.map')  # 支持的文件扩展名

    # 遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(js_extensions):
                file_path = os.path.join(root, file)
                print(f"\n正在处理文件: {file_path}")
                paths = process_local_js_file(file_path)
                if paths:
                    all_paths.extend(paths)

    # 去重并保持顺序
    unique_paths = list(dict.fromkeys(all_paths))

    # 保存结果
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for path in unique_paths:
                print(path)  # 打印到控制台
                f.write(path + '\n')
        print(f"\n路径提取完成！共提取到 {len(unique_paths)} 个路径，结果已保存到 '{output_file}'。")
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
