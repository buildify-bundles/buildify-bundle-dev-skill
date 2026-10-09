# 三方接口的通用调用

对接三方 HTTP API 时，除了常用操作的专用节点，还要有一个通用调用节点。
厂商文档里有、但还没做成节点的接口，Agent 读文档后用这个节点调用，不要为每个接口新写一个节点。

## 生成

类名以 `ApiCall` 结尾，并同时提供凭证（鉴权来自凭证，不写进节点参数）：

```bash
python3 <skill-root>/scripts/scaffold_bundle.py \
  --dir ./my-api \
  --group-id com.example --artifact-id my-api \
  --bundle-name example/my-api --package com.example.api \
  --credential MyApiCredential \
  --generic-api ApiCall
```

常用操作仍用 `--node` 做专用节点。通用节点只承接文档中还没有专用节点的接口。

## Agent 怎么填

读厂商文档的某一个接口，把字段填进通用节点：

| 参数 | 来源 |
|---|---|
| `method` | 文档中的 HTTP 方法 |
| `path` | 文档中的路径，以 `/` 开头，不含域名。路径参数写成 `={{ msg.xxx }}` |
| `query` | 文档中的查询参数，一项一行（可增删） |
| `headers` | 文档要求的额外请求头。不要把 API Key 写在这里 |
| `body` | 文档中的 JSON 正文。GET 不显示此项 |

域名、端口、密钥来自凭证的 `host`、`port`、`apiKey`。
未填写 `Authorization`、`X-Api-Key`、`Api-Key` 时，节点自动加上 `Authorization: Bearer <apiKey>`。
文档要求别的鉴权头时，写在 `headers` 里，节点就不再加 Bearer。

`path` 以 `http://` 或 `https://` 开头时当作完整地址，不再拼接凭证里的 host。

文档示例：`POST /v1/users?page=1`，正文 `{ "name": "..." }`。对应填法：

```json
{
  "method": "POST",
  "path": "/v1/users",
  "query": [{ "key": "page", "value": "1" }],
  "body": { "name": "={{ msg.name }}" }
}
```

## 输出

成功（含 HTTP 4xx / 5xx）走 Success：

```json
{ "output": { "statusCode": 200, "body": {} } }
```

下游用 `={{ msg.output.statusCode }}` 与 `={{ msg.output.body }}`。
连接失败、超时、地址无效走 Failure，这时通常没有 `msg.output.statusCode`。

脚手架写入的 README「通用调用」一节要保留。编排时 Agent 靠这一节和节点表单决定怎么填，不要改字段名。
