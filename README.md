# API Path Extractor

一个强大的工具，用于从 JavaScript 文件和网页中提取 API 路径。支持处理本地文件、在线网页以及批量 URL。

## 功能特点

- 🔍 支持多种路径提取模式：
  - RESTful API 路径
  - Ajax 请求路径
  - 动态加载路径
  - 版本化 API 路径 (如 v1/api/...)
- 📁 支持多种输入源：
  - 本地 JS 文件目录
  - 单个网页 URL
  - 批量 URL 列表
- 🔧 支持多种文件格式：
  - JavaScript (.js)
  - TypeScript (.ts)
  - React/Vue 文件 (.jsx, .tsx)
  - Source Map 文件 (.map)
- ⚡ 自动处理：
  - 文件编码（UTF-8/GBK）
  - 路径去重
  - 动态加载的 JS 文件
  - 路径清理和标准化

## 安装要求
```

pip install -r requirements.txt 

```

必需的依赖包：
- playwright
- beautifulsoup4
- requests
- argparse

## 使用方法

### 1. 处理本地目录

```

python api.py -d ./your_js_files -o output.txt
```

### 2. 处理单个 URL

```

python api.py -u https://example.com -o output.txt
```

### 3. 处理批量 URL

```

python api.py -l urls.txt -o output.txt
```

### 参数说明

- `-d, --directory`: 指定要处理的本地目录路径
- `-u, --url`: 指定要处理的单个 URL
- `-l, --urls-file`: 指定包含多个 URL 的文件
- `-o, --output-file`: 指定输出文件名（默认为 api_paths.txt）

## 输出示例

```
/api/v1/users
/api/v2/products
/v1/auth/login
/api/data/statistics
...
```

## 注意事项

1. 处理在线 URL 时需要安装 Playwright 的浏览器：
```bash
playwright install chromium
```

2. 确保有足够的权限访问目标网站和本地文件

3. 处理大型网站时可能需要较长时间

## 实现细节

- 使用正则表达式匹配多种 API 路径模式
- 支持处理动态加载的 JavaScript 文件
- 自动过滤静态资源路径
- 智能处理相对路径和绝对路径
- 支持多种字符编码

## 贡献指南

欢迎提交 Pull Requests 和 Issues！

1. Fork 该项目
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 许可证

该项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

如果您有任何问题或建议，请通过 Issues 与我们联系。

## 致谢

感谢所有为这个项目做出贡献的开发者！
