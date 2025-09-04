# Claude Messages API JSON 客户端

`claude_client.py` 提供两种使用方式：
- 交互模式：逐条输入问题，连续多轮对话；每条回复以JSON输出
- 单次调用：命令行`--prompt`或从stdin传入JSON，返回JSON

## 准备

1) 设置环境变量（Windows PowerShell）：
```powershell
$env:ANTHROPIC_API_KEY = "your_api_key_here"
```

2) 可选：指定模型/最大tokens/system提示词

## 交互模式

```bash
python claude_client.py --model claude-3-5-sonnet-20240620 --max_tokens 1024 --system "You are a helpful assistant"
```

输入问题（回车发送），输入 `exit` 结束。每条回复为：

```json
{"type":"message","answer":"...","raw":{}}
```

## 单次调用：命令行参数

```bash
python claude_client.py --prompt "介绍一下Python生成器" --model claude-3-5-sonnet-20240620 --max_tokens 512
```

输出为HTTP结果JSON：

```json
{
  "status": 200,
  "headers": {"content-type": "application/json"},
  "body": {"id": "msg_...", "content": [{"type": "text", "text": "..."}]}
}
```

## 单次调用：stdin传JSON

```bash
echo '{"prompt":"用三点说明Rust的优势","model":"claude-3-5-sonnet-20240620","max_tokens":400}' | python claude_client.py --stdin_json
```

或在PowerShell：

```powershell
'{"prompt":"用三点说明Rust的优势","model":"claude-3-5-sonnet-20240620","max_tokens":400}' | python claude_client.py --stdin_json
```

## 返回数据结构

- 交互模式：每条消息打印
  - `{"type":"message","answer":"纯文本答案","raw":Claude原始响应JSON}`
- 单次调用：返回HTTP包装
  - 成功：`{"status":200,"headers":{},"body":{...}}`
  - 失败：`{"status":<code>,"error":true,"body":{...}}`

## 备注

- 仅用标准库，不依赖第三方包
- `history`默认保留近20轮上下文，可按需调整
- 如需流式输出，可后续扩展为`/v1/messages?stream=true`


