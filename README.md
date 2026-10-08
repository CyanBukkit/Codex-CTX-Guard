# Codex CTX Guard / 玄易插件商店

这是一个可公开拉取的自建 Codex 插件商店（plugin marketplace）。仓库根目录的 `.agents/plugins/marketplace.json` 是商店目录，插件源码放在 `plugins/` 下。

This repository is a self-hosted Codex plugin marketplace. The catalog lives at `.agents/plugins/marketplace.json`, and plugin packages live under `plugins/`.

## 安装商店 / Add the marketplace

GitHub 简写：

```bash
codex plugin marketplace add CyanBukkit/Codex-CTX-Guard --ref main
```

或使用 SSH URL：

```bash
codex plugin marketplace add git@github.com:CyanBukkit/Codex-CTX-Guard.git --ref main
```

查看商店中的插件：

```bash
codex plugin list --marketplace xuanyi-plugins --available
```

安装第一个插件：

```bash
codex plugin add input-token-guard --marketplace xuanyi-plugins
```

更新商店快照并重装插件：

```bash
codex plugin marketplace upgrade xuanyi-plugins
codex plugin add input-token-guard@xuanyi-plugins
```

> 说明：远程 Git 插件商店适用于 Codex CLI / Codex 桌面端。是否能在 ChatGPT 网页版展示，取决于当前账号和平台对自定义 marketplace 的支持范围。

## 当前插件 / Available plugins

### Input Token Guard

用于诊断和预防 Codex 输入上下文超限错误，例如：

```text
400 - upstream: Input tokens exceed the configured limit of 922000 tokens
```

能力：

- 保守估算文件、目录或标准输入的 token 规模；
- 默认以 922,000 为配置上限，并预留安全余量；
- 排除 `.git`、`node_modules`、`dist`、`build` 等低价值目录；
- 将超大日志或文档拆分为安全 chunk；
- 提供新线程交接摘要模板，避免旧上下文继续膨胀。

本地直接运行：

```bash
python3 plugins/input-token-guard/scripts/token_budget.py estimate --limit 922000 .
python3 plugins/input-token-guard/scripts/token_budget.py split path/to/large.log --max-tokens 80000 --output-dir work/token-chunks
```

> token 估算是保守的规划值，不是模型服务商的精确 tokenizer 结果。

## 仓库结构 / Repository layout

```text
.
├── .agents/plugins/marketplace.json      # 商店目录 / marketplace catalog
├── plugins/
│   └── input-token-guard/
│       ├── .codex-plugin/plugin.json     # 插件清单 / plugin manifest
│       ├── README.md
│       ├── scripts/token_budget.py
│       └── skills/input-token-guard/
└── LICENSE
```

## 添加新插件 / Add another plugin

1. 在 `plugins/<plugin-name>/` 中创建插件，并确保存在 `.codex-plugin/plugin.json`。
2. 在 `.agents/plugins/marketplace.json` 的 `plugins[]` 末尾追加条目。
3. 保留 `policy.installation`、`policy.authentication` 和 `category` 字段。
4. 提交并推送后，让用户运行 `codex plugin marketplace upgrade xuanyi-plugins`。

示例条目：

```json
{
  "name": "my-plugin",
  "source": {
    "source": "local",
    "path": "./plugins/my-plugin"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

## License

[MIT](./LICENSE)
