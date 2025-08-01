# GCP Guardian Dashboard (中文版)

GCP Guardian Dashboard 是一款自托管、支持多服务器的监控工具，旨在帮助您控制 Google Cloud Platform (GCP) 的服务成本。它提供了一个简洁的 Web 界面，用于监控您虚拟机实例的每月出口流量，并在流量超出预设阈值时自动将其关闭，从而有效防止意外账单。

![Screenshot Placeholder](https://via.placeholder.com/800x400.png?text=GCP+Guardian+Dashboard+截图)
*(您可以将上方的占位符图片替换为您应用的实际运行截图。)*

---

## 核心功能

- **多服务器监控**: 在单个仪表盘中监控多个 GCP 项目和虚拟机实例。
- **独立认证**: 每个服务器均使用其独立的服务账户密钥进行配置，以增强安全性与灵活性。
- **流量监控**: 跟踪每个虚拟机的每月累计出口流量。
- **自动关机**: 当虚拟机流量超过您定义的阈值时，自动执行关机操作。
- **手动控制**: 直接从仪表盘启动、停止和刷新每个虚拟机的数据。
- **操作日志**: 为所有自动化和手动操作保留日志，便于审计。
- **自托管**: 您对自己的数据和基础设施拥有完全控制权。
- **配置简单**: 所有设置均通过一个简单的 `.env` 文件进行管理。
- **现代化前端**: 采用响应式设计，并包含一个可定制的动态粒子背景，以提供更佳的视觉体验。
- **分级预警系统**:
    - **75% 流量预警**: 当服务器流量达到总阈值的 75% 时，通过 Bark 发送预警通知。
    - **95% 自动关机**: 当流量达到 95% 时，自动关闭虚拟机以防止超额，并发送通知。
- **每月自动重启**: 在每个月的第一天中午 12 点，自动重启所有因流量超限而被关闭的虚拟机，并发送通知。

---

## 安装与使用

请按照以下步骤来启动并运行您的 GCP Guardian Dashboard。

### 先决条件

- Git
- Python 3.8+
- 一个已启用结算功能的 Google Cloud Platform 账户。

### 第一步：克隆仓库

```bash
git clone https://github.com/jjbb013/GCP-GuardianDashboard.git
cd GCP-GuardianDashboard
```

### 第二步：配置 GCP 服务账户

对于您希望监控的每一个 GCP 项目/服务器，您都需要一个拥有适当权限的服务账户 (Service Account)。

1.  **访问 GCP 控制台**: 前往 **IAM 和管理** > **服务账户**。
2.  **创建服务账户**:
    - 点击 **创建服务账户**。
    - 为其命名 (例如 `gcp-guardian-sa`)。
3.  **授予权限**: 为该服务账户授予以下两个角色：
    - `Compute Instance Admin (v1)`: 允许启动和停止虚拟机实例。
    - `Monitoring Viewer`: 允许读取虚拟机的流量监控数据。
4.  **创建并下载密钥**:
    - 打开新创建的服务账户。
    - 前往 **密钥** 标签页。
    - 点击 **添加密钥** > **创建新密钥**。
    - 选择 **JSON** 作为密钥类型，然后点击 **创建**。一个 JSON 密钥文件将被下载。

如果您打算为不同的服务器使用不同的服务账户，请重复此过程。

### 第三步：配置 `.env` 文件

这是最关键的一步。请复制配置示例文件，然后用您的信息进行编辑。

```bash
cp .env.example .env
```

现在，打开 `.env` 文件，并根据以下说明填写变量。

```env
# --- 应用设置 ---
TRAFFIC_THRESHOLD_GB=100
DATABASE_URL=sqlite:///data/gcp_guardian.db

# --- 通知与预警 (可选) ---
# 你的 Bark URL，用于接收通知。留空则禁用通知功能。
# 示例: https://api.day.app/your_bark_key
BARK_URL=
# 发送预警通知的流量使用百分比阈值。
WARNING_THRESHOLD_PERCENT=75
# 自动关闭虚拟机的流量使用百分比阈值。
SHUTDOWN_THRESHOLD_PERCENT=95

# --- 管理员凭证与安全 ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=your_randomly_generated_32_byte_hex_secret

# --- 服务器配置 ---
# 通过递增数字 (1, 2, 3, ...) 来定义一个或多个服务器。

# --- 服务器 1 ---
GCP_SERVER_1_PROJECT_ID=your-gcp-project-id-1
GCP_SERVER_1_VM_INSTANCE_NAME=your-vm-instance-name-1
GCP_SERVER_1_VM_ZONE=us-central1-a
GCP_SERVER_1_SA_KEY=... (服务器1的 base64 编码密钥)

# --- 服务器 2 (示例) ---
GCP_SERVER_2_PROJECT_ID=your-gcp-project-id-2
GCP_SERVER_2_VM_INSTANCE_NAME=your-vm-instance-name-2
GCP_SERVER_2_VM_ZONE=europe-west1-b
GCP_SERVER_2_SA_KEY=... (服务器2的 base64 编码密钥)
```

**如何获取 `SA_KEY` 的值：**

`GCP_SERVER_..._SA_KEY` 的值必须是您在第二步中下载的 JSON 密钥文件的**内容的 base64 编码字符串**。

-   **在 macOS 或 Linux 上:**
    ```bash
    # 将路径替换为您的密钥文件的实际路径
    base64 -i /path/to/your-key-file.json
    ```
-   **在 Windows (PowerShell) 上:**
    ```powershell
    # 将路径替换为您的密钥文件的实际路径
    $json = Get-Content -Raw -Path "path/to/your-key-file.json"
    [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json))
    ```

复制完整的输出字符串，并将其粘贴为相应 `GCP_SERVER_..._SA_KEY` 的值。

### 第四步：运行应用

本项目包含一个辅助脚本，可以自动安装依赖并运行服务器。

```bash
python run_local.py
```

应用将在 **http://127.0.0.1:8001** 上可用。

---

## 技术栈

- **后端**: FastAPI, SQLAlchemy, APScheduler
- **前端**: 原生 JavaScript, HTML, CSS
- **数据库**: SQLite (默认)

---
<br>

# GCP Guardian Dashboard (English Version)

GCP Guardian Dashboard is a self-hosted, multi-server monitoring tool designed to help you keep your Google Cloud Platform (GCP) costs in check. It provides a clean web interface to monitor the monthly egress traffic of your virtual machine instances and automatically shuts them down if a predefined threshold is exceeded, preventing unexpected bills.

![Screenshot Placeholder](https://via.placeholder.com/800x400.png?text=GCP+Guardian+Dashboard+Screenshot)
*(Feel free to replace the placeholder above with a screenshot of your running dashboard.)*

---

## Core Features

- **Multi-Server Monitoring**: Monitor multiple GCP projects and VM instances from a single dashboard.
- **Independent Authentication**: Each server is configured with its own Service Account Key for enhanced security and flexibility.
- **Traffic Monitoring**: Tracks the cumulative monthly egress traffic for each VM.
- **Automatic Shutdown**: Automatically shuts down a VM when its traffic exceeds your defined threshold.
- **Manual Controls**: Start, stop, and refresh data for each VM directly from the dashboard.
- **Action Logs**: Keeps a log of all automated and manual actions for auditing.
- **Self-Hosted**: You have full control over your data and infrastructure.
- **Easy Configuration**: All settings are managed through a simple `.env` file.
- **Tiered Alerting System**:
    - **75% Traffic Warning**: Sends a warning notification via Bark when a server's traffic reaches 75% of its total threshold.
    - **95% Auto-Shutdown**: Automatically shuts down the VM at 95% traffic usage to prevent overages and sends a notification.
- **Monthly Auto-Restart**: Automatically restarts all VMs that were shut down due to traffic limits at 12:00 PM on the first day of each month and sends a notification.

---

## Installation & Usage

Follow these steps to get your GCP Guardian Dashboard up and running.

### Prerequisites

- Git
- Python 3.8+
- A Google Cloud Platform account with billing enabled.

### Step 1: Clone the Repository

```bash
git clone https://github.com/jjbb013/GCP-GuardianDashboard.git
cd GCP-GuardianDashboard
```

### Step 2: Configure GCP Service Accounts

For each GCP project/server you want to monitor, you need a Service Account with the appropriate permissions.

1.  **Navigate to GCP Console**: Go to **IAM & Admin** > **Service Accounts**.
2.  **Create Service Account**:
    - Click **CREATE SERVICE ACCOUNT**.
    - Give it a name (e.g., `gcp-guardian-sa`).
3.  **Grant Permissions**: Grant the following two roles to the service account:
    - `Compute Instance Admin (v1)`: Allows starting and stopping VM instances.
    - `Monitoring Viewer`: Allows reading VM traffic monitoring data.
4.  **Create and Download Key**:
    - Open the newly created service account.
    - Go to the **KEYS** tab.
    - Click **ADD KEY** > **Create new key**.
    - Select **JSON** as the key type and click **CREATE**. A JSON key file will be downloaded.

Repeat this process for each server if you intend to use different service accounts.

### Step 3: Configure the `.env` File

This is the most crucial step. Copy the example configuration file and then edit it with your details.

```bash
cp .env.example .env
```

Now, open the `.env` file and fill in the variables according to the instructions below.

```env
# --- Application Settings ---
TRAFFIC_THRESHOLD_GB=100
DATABASE_URL=sqlite:///data/gcp_guardian.db

# --- Admin Credentials & Security ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=your_randomly_generated_32_byte_hex_secret

# --- Server Configurations ---
# Define one or more servers by incrementing the number (1, 2, 3, ...).

# --- Server 1 ---
GCP_SERVER_1_PROJECT_ID=your-gcp-project-id-1
GCP_SERVER_1_VM_INSTANCE_NAME=your-vm-instance-name-1
GCP_SERVER_1_VM_ZONE=us-central1-a
GCP_SERVER_1_SA_KEY=... (base64 encoded key for server 1)

# --- Server 2 (Example) ---
GCP_SERVER_2_PROJECT_ID=your-gcp-project-id-2
GCP_SERVER_2_VM_INSTANCE_NAME=your-vm-instance-name-2
GCP_SERVER_2_VM_ZONE=europe-west1-b
GCP_SERVER_2_SA_KEY=... (base64 encoded key for server 2)
```

**How to get the `SA_KEY` value:**

The `GCP_SERVER_..._SA_KEY` must be the **base64 encoded content** of the JSON key file you downloaded in Step 2.

-   **On macOS or Linux:**
    ```bash
    # Replace with the actual path to your key file
    base64 -i /path/to/your-key-file.json
    ```
-   **On Windows (PowerShell):**
    ```powershell
    # Replace with the actual path to your key file
    $json = Get-Content -Raw -Path "path/to/your-key-file.json"
    [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json))
    ```

Copy the entire output string and paste it as the value for the corresponding `GCP_SERVER_..._SA_KEY`.

### Step 4: Run the Application

The project includes a helper script that installs dependencies and runs the server.

```bash
python run_local.py
```

The application will be available at **http://127.0.0.1:8001**.

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, APScheduler
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Database**: SQLite (default)

---

## 高级功能

### 测试通知

应用提供了一个 API 端点，用于测试您的 Bark 通知是否配置正确。在登录后，您可以使用 `curl` 或其他工具向以下地址发送 `POST` 请求：

- **发送通用测试消息**:
  ```bash
  curl -X POST "http://127.0.0.1:8001/api/v1/notifications/test-bark" -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  ```

- **模拟 75% 预警通知**:
  ```bash
  curl -X POST "http://127.0.0.1:8001/api/v1/notifications/test-bark?scenario=warning" -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  ```

- **模拟 95% 关机通知**:
  ```bash
  curl -X POST "http://127.0.0.1:8001/api/v1/notifications/test-bark?scenario=shutdown" -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  ```
*请将 `YOUR_ACCESS_TOKEN` 替换为您从浏览器获取的有效令牌。*

---
