# API 测试指南

这是一个用于调试 GCP Guardian API 的指南。请在终端中按顺序执行以下命令。

## 步骤 1: 获取认证 Token

此命令将使用在 `.env` 文件中配置的管理员凭证登录，并返回一个 JWT Token。

**注意**: 请确保 `jq` 已安装 (`brew install jq`)，以便自动提取 token。如果未安装，请手动复制响应中的 `access_token` 值。

```bash
# 使用您的管理员用户名和密码
ADMIN_USERNAME="will"
ADMIN_PASSWORD="333333"

# 发送登录请求并提取 Token
TOKEN=$(curl -s -X POST "http://127.0.0.1:8001/api/v1/auth/login" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=$ADMIN_USERNAME&password=$ADMIN_PASSWORD" | jq -r .access_token)

# 检查 Token 是否已获取
if [ -z "$TOKEN" ]; then
  echo "错误：未能获取 Token。请检查您的用户名和密码以及服务器是否正在运行。"
else
  echo "成功获取 Token: $TOKEN"
fi
```

## 步骤 2: 测试 Dashboard Status 端点

获取 Token 后，使用以下命令测试 `/api/v1/dashboard/status` 端点。此命令将在 Authorization 头中包含上一步获取的 Token。

```bash
# 确保您已在步骤 1 中成功获取 Token
if [ -z "$TOKEN" ]; then
  echo "错误：Token 未设置。请先执行步骤 1。"
else
  curl -X GET "http://127.0.0.1:8001/api/v1/dashboard/status" \
  -H "Authorization: Bearer $TOKEN"
fi
```

## 预期输出

如果一切正常，步骤 2 的命令应返回一个 JSON 对象，其中包含虚拟机的状态信息，例如：

```json
{
  "instance_name": "instance-20250730-083312",
  "status": "RUNNING",
  "current_traffic_gb": 0.1234,
  "traffic_threshold_gb": 100,
  "traffic_usage_percent": 0.12
}
```

如果仍然出现超时错误，则问题可能与 GCP 服务账户凭证或网络连接有关。
