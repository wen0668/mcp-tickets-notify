帮我调通这个 http://192.168.0.4:31234/sse ,get-tickets 的接口,例子:
# 直接调用 get-tickets 工具
curl -X POST http://192.168.0.4:31234 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get-tickets",
      "arguments": {
        "date": "2026-06-21",
        "from_station": "茂名",
        "to_station": "广州南"
      }
    },
    "id": 1
  }'

# 一键查询脚本
请使用 `query_tickets.py` 先打开 `/sse`，再自动发送 `/message` 请求：

```bash
python3 mcp12306/query_tickets.py \
  --host http://192.168.0.4:31234 \
  --date 2026-06-21 \
  --from-station 茂名 \
  --to-station 广州南
```

# 该脚本会自动获取 `sessionId` 并打印 POST 响应与 SSE 返回结果。

# 使用这个命令查询 2026年6月18日 19:30后 广州南→茂名 的二等座：

参数说明：

--date — 出发日期（必需）
--from-station — 出发站（必需）
--to-station — 到达站（必需）
--after-time — 只显示某时间后的车次，如 19:30
--seat-type — 只显示指定座级，如 二等座 或 一等座

其他例子：

查询 6月21日 18:30后 茂名→广州南 的二等座：
```bash
python3 mcp12306/query_tickets.py --date 2026-06-21 --from-station 茂名 --to-station 广州南 --after-time 18:30 --seat-type 二等座
```

查询所有列车（不过滤）：

```bash
python3 mcp12306/query_tickets.py --date 2026-06-18 --from-station 广州南 --to-station 茂名
```