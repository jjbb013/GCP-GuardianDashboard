#!/bin/bash

# 这是一个用于直接测试与 Google Cloud Monitoring API 连接的脚本。
# 它会执行以下操作：
# 1. 从 .env 文件中读取并解码服务账户凭证。
# 2. 使用凭证获取一个临时的 OAuth2 Access Token。
# 3. 使用该 Token 查询虚拟机的网络出口流量。

echo "--- GCP Monitoring API 连接测试脚本 ---"

# 步骤 1: 从 .env 文件中提取并解码凭证
echo "[1/4] 正在提取并解码 GCP 服务账户凭证..."
GCP_CREDS_BASE64=$(grep 'GCP_SERVICE_ACCOUNT_CREDENTIALS' .env | cut -d '=' -f2)
if [ -z "$GCP_CREDS_BASE64" ]; then
    echo "错误：在 .env 文件中未找到 GCP_SERVICE_ACCOUNT_CREDENTIALS。"
    exit 1
fi

# 创建一个临时的凭证文件
CREDS_FILE="temp_gcp_creds.json"
echo "$GCP_CREDS_BASE64" | sed 's/\\n/\\\\n/g' | base64 --decode > "$CREDS_FILE"
if [ $? -ne 0 ]; then
    echo "错误：解码凭证失败。请检查 .env 文件中的 base64 字符串是否正确。"
    exit 1
fi
echo "凭证已成功解码到 $CREDS_FILE。"

# 步骤 2: 获取 OAuth2 Access Token
echo "[2/4] 正在从 Google OAuth2 API 获取 Access Token..."
# 需要 gcloud SDK 已安装并认证，或者使用 oauth2l 工具
# 这里我们使用 gcloud 的方式
ACCESS_TOKEN=$(gcloud auth print-access-token --impersonate-service-account=$(jq -r .client_email $CREDS_FILE))

if [ -z "$ACCESS_TOKEN" ]; then
    echo "错误：获取 Access Token 失败。"
    echo "请确保您已登录 gcloud (gcloud auth login) 并且有权限模拟此服务账户 (roles/iam.serviceAccountTokenCreator)。"
    rm "$CREDS_FILE"
    exit 1
fi
echo "成功获取 Access Token。"

# 步骤 3: 准备 API 请求
echo "[3/4] 正在准备对 Cloud Monitoring API 的请求..."
PROJECT_ID=$(grep 'GCP_PROJECT_ID' .env | cut -d '=' -f2)
INSTANCE_ID=$(grep 'GCP_VM_INSTANCE_ID' .env | cut -d '=' -f2)

# 构建查询
QUERY="fetch gce_instance::compute.googleapis.com/instance/network/sent_bytes_count | filter resource.instance_id == '$INSTANCE_ID' | within 1h"

# 步骤 4: 发送请求到 Monitoring API
echo "[4/4] 正在向 Cloud Monitoring API 发送请求..."
API_URL="https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries:query"

curl -s -X POST "$API_URL" \
-H "Authorization: Bearer $ACCESS_TOKEN" \
-H "Content-Type: application/json" \
--data @- << EOF
{
  "query": "$QUERY"
}
EOF

# 清理临时文件
rm "$CREDS_FILE"
echo -e "\n\n--- 测试完成 ---"
echo "如果上面显示了 JSON 格式的 timeSeriesData，则表示 API 连接成功。"
echo "如果出现 'PERMISSION_DENIED' 或其他错误，请检查服务账户的 IAM 权限（需要 Monitoring Viewer 角色）。"
echo "如果请求超时，则可能是网络问题。"
