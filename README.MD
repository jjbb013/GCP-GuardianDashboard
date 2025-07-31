---

### **项目需求文档 (PRD): GCP Guardian (V2.0 - 单管理员版)**

**版本:** 2.0
**日期:** 2023年10月28日
**项目负责人:** [你的名字]

---

### **1.0 项目概述 (Project Overview)**

"GCP Guardian" 是一个为个人开发者和小型团队设计的**自托管、单管理员** Web 应用。它通过 Docker Compose 进行部署，所有关键凭证均通过环境变量进行管理，以确保最高级别的安全性和部署简便性。

该应用的核心功能是为 Google Cloud Platform (GCP) 的虚拟机 (VM) 提供精细化的流量监控和自动化的成本控制。管理员可以通过一个简洁的仪表板，直观地监控 VM 流量消耗，并在流量接近或超出预设阈值时，自动执行关机操作，从而有效防止意外的云服务账单。

### **2.0 核心设计原则 (Core Design Principles)**

1.  **安全优先 (Security First):** **绝不**在数据库中存储任何云凭证或应用登录密码。所有敏感信息必须通过环境变量注入。
2.  **部署简单 (Simplicity in Deployment):** 提供 `docker-compose.yml` 和 `.env.example` 文件，实现一条命令完成部署。
3.  **单一职责 (Single Responsibility):** 专注于解决 GCP 流量超支这一个核心痛点，并做到极致。
4.  **架构可扩展 (Scalable Architecture):** 后端逻辑将设计为可插拔模式，为未来支持其他云服务（如 AWS）或新功能预留接口。

### **3.0 分阶段开发计划 (Phased Development Plan)**

我们将项目分为三个主要阶段，每个阶段都有明确的目标和可交付成果，以便逐一推进和验证。

---

### **第一阶段：核心引擎与基础部署 (Phase 1: Core Engine & Basic Deployment)**

**目标：** 交付一个可在后台可靠运行的、无 UI 的核心监控与自动化引擎。此阶段验证核心逻辑的正确性。

**功能需求 (Functional Requirements):**

*   **FR-P1-1: 基于 Docker Compose 的部署**
    *   提供 `docker-compose.yml` 文件，定义应用服务和数据库服务（如 SQLite）。
    *   提供 `.env.example` 文件，作为配置模板。

*   **FR-P1-2: 基于环境变量的配置**
    *   系统启动时从 `.env` 文件加载所有配置。
    *   **必需的环境变量包括：**
        *   `GCP_PROJECT_ID`: 你的 GCP 项目 ID。
        *   `GCP_VM_INSTANCE_ID`: 要监控的 VM 实例名称。
        *   `GCP_VM_ZONE`: VM 所在的区域。
        *   `GCP_SERVICE_ACCOUNT_CREDENTIALS`: GCP 服务账户的 JSON 密钥内容 (通常是 base64 编码后的字符串)。
        *   `TRAFFIC_THRESHOLD_GB`: 每月的流量阈值（单位：GB）。
        *   `ADMIN_USERNAME`: 仪表板的登录用户名。
        *   `ADMIN_PASSWORD`: 管理员的明文密码。
        *   `DATABASE_URL`: 数据库连接字符串。

*   **FR-P1-3: 后端调度器 (Scheduler)**
    *   实现一个定时任务（建议每小时执行一次）。
    *   任务流程：
        1. 调用 GCP API，获取指定 VM 当月的累计出站流量。
        2. 将获取到的流量数据记录到数据库中。
        3. 检查当前流量是否已超过 `TRAFFIC_THRESHOLD_GB`。
        4. 如果超过阈值，则调用 GCP API 执行**关机 (Shutdown)** 操作。
        5. 在关机后，将本次操作记录到日志中（可以是简单的控制台输出或数据库记录）。

*   **FR-P1-4: 最小化的数据库设计**
    *   **`traffic_logs` 表:** `id`, `timestamp`, `traffic_gb` (记录每次获取的流量数据)。
    *   **`action_logs` 表:** `id`, `timestamp`, `action_type` (e.g., 'SHUTDOWN'), `reason` (e.g., 'Threshold exceeded')。

**此阶段交付成果 (Deliverable):**
一套可以通过 `docker-compose up -d` 启动的后台服务。管理员配置好 `.env` 文件后，系统即可自动监控并保护指定的 GCP VM。所有状态通过查看容器日志来确认。

---
### **附录：GCP 服务账户配置指南**

为了让 GCP Guardian 能够访问您的虚拟机和监控数据，您需要创建一个服务账户 (Service Account) 并授予其必要的 IAM 权限。

**1. 创建服务账户**

1.  登录到您的 [GCP Console](https://console.cloud.google.com/)。
2.  导航到 **IAM & Admin** > **Service Accounts**。
3.  点击 **CREATE SERVICE ACCOUNT**。
4.  为服务账户命名（例如 `gcp-guardian-sa`），然后点击 **CREATE AND CONTINUE**。

**2. 授予 IAM 角色**

在 "Grant this service account access to project" 步骤中，添加以下两个角色：

*   **Compute Instance Admin (v1)** (`roles/compute.instanceAdmin.v1`)
    *   **理由:** 提供启动和停止虚拟机的权限。
*   **Monitoring Viewer** (`roles/monitoring.viewer`)
    *   **理由:** 提供读取虚拟机网络流量等监控指标的权限。

点击 **CONTINUE**，然后点击 **DONE** 完成创建。

**3. 生成并编码密钥**

1.  在服务账户列表中，找到您刚刚创建的账户，点击其电子邮件地址。
2.  切换到 **KEYS** 标签页。
3.  点击 **ADD KEY** > **Create new key**。
4.  选择 **JSON** 作为密钥类型，然后点击 **CREATE**。一个 JSON 密钥文件将自动下载到您的计算机。

**4. 配置环境变量**

您需要将下载的 JSON 密钥文件的**内容**进行 Base64 编码，并将其设置为 `GCP_SERVICE_ACCOUNT_CREDENTIALS` 环境变量。

*   **在 macOS 或 Linux 上:**
    ```bash
    # 将 "path/to/your-key-file.json" 替换为您的实际文件路径
    cat path/to/your-key-file.json | base64
    ```
*   **在 Windows (PowerShell) 上:**
    ```powershell
    # 将 "path/to/your-key-file.json" 替换为您的实际文件路径
    $json = Get-Content -Raw -Path "path/to/your-key-file.json"
    [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json))
    ```

将命令输出的**整段长字符串**复制并粘贴到您的 `.env` 文件中，作为 `GCP_SERVICE_ACCOUNT_CREDENTIALS` 的值。

**5. 配置安全密钥 (SECRET_KEY)**

`SECRET_KEY` 是一个用于保护用户会话（通过签发 JWT 令牌）的关键安全凭证。当您登录仪表板时，应用会使用此密钥生成一个加密的令牌。此后，您对需要认证的 API 的所有请求都必须包含此令牌，应用会使用相同的密钥来验证令牌的有效性。

**要求：**
这个密钥必须是**随机的、长且不可预测的**字符串。请**不要**使用容易猜到的短语，如 "password" 或 "secret"。

**如何生成：**
我们推荐使用 `openssl`（一个在大多数 Linux 和 macOS 系统上都可用的工具）来生成一个安全的随机密钥。

在您的终端中运行以下命令：
```bash
openssl rand -hex 32
```
该命令会生成一个 64 个字符的十六进制字符串，例如：
`e8a3f7a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4`

将生成的字符串复制并粘贴到您的 `.env` 文件中，作为 `SECRET_KEY` 的值。

---

### **第二阶段：Web 仪表板与通知系统 (Phase 2: Web Dashboard & Notifications)**

**目标：** 提供一个可视化的 Web 界面，方便管理员监控状态和手动干预，并集成基础的通知功能。

**功能需求 (Functional Requirements):**

*   **FR-P2-1: 用户认证与登录页**
    *   创建一个简单的登录页面，包含用户名和密码输入框。
    *   后端验证用户输入是否与环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 匹配。
    *   使用 JWT 或 Session 实现登录状态保持。

*   **FR-P2-2: 仪表板 (Dashboard)**
    *   **VM 状态卡片:**
        *   显示 VM 名称、当前运行状态（运行中/已停止）。
        *   显示一个清晰的流量进度条，格式为 `当前流量 / 阈值 GB (百分比%)`。
        *   **流量成本估算:** 基于当前消耗速率，提供一个**非精确**的月度流量成本估算值。**UI 上需明确标注“仅为估算值”**。
        *   **手动操作按钮:** "立即关机" 和 "立即启动"。

*   **FR-P2-3: 历史数据视图**
    *   提供一个简单的图表（如线形图），展示过去 30 天的每日流量消耗历史。数据源于 `traffic_logs` 表。

*   **FR-P2-4: 通知模块集成**
    *   在后端增加通知发送功能（初步支持 Email 和 Slack）。
    *   通知触发条件：
        *   **警告通知:** 当流量达到阈值的 **75%** 时，发送一次警告信息。
        *   **行动通知:** 当流量超出阈值并执行自动关机时，发送通知。
    *   **配置:** 通知服务的必要参数（如 SMTP 服务器信息、Slack Webhook URL）也通过环境变量进行配置。

**此阶段交付成果 (Deliverable):**
一个功能完整的 Web 仪表板。管理员可以登录查看实时状态、历史数据和手动启停 VM，并在关键事件发生时收到通知。

---

### **第三阶段：高级自动化与体验优化 (Phase 3: Advanced Automation & Polish)**

**目标：** 实现更智能的自动化规则，并对系统进行全面优化，使其更健壮、更“懂你”。

**功能需求 (Functional Requirements):**

*   **FR-P3-1: 每月自动启动功能**
    *   **核心逻辑:** 系统需要记录 VM 是被**用户手动关机**还是被**系统自动关机**。可以在 `action_logs` 或 VM 状态表中增加一个布尔字段 `is_auto_shutdown`。
    *   **调度器增强:** 新增一个每月任务，在**每月1号凌晨**（例如 01:00 UTC）自动执行。
    *   **任务流程:** 检查 VM 的 `is_auto_shutdown` 状态。如果为 `true`，则自动调用 GCP API 启动该 VM，并重置其状态，为新一个计费周期做准备。

*   **FR-P3-2: 详细的操作审计日志**
    *   在仪表板中增加一个“操作日志”页面。
    *   清晰地展示所有关键事件，包括：自动关机、警告通知、手动启动/停止、每月自动启动。

*   **FR-P3-3: 架构扩展性预留**
    *   **代码重构:** 审查后端的 GCP API 调用部分，将其封装到一个 `GcpProvider` 类中，该类实现一个通用的 `CloudProvider` 接口（`get_traffic()`, `shutdown_vm()`, `start_vm()` 等）。
    *   **目的:** 即使当前只支持GCP，这种设计能确保未来添加 AWS 或其他云服务时，只需实现一个新的 `AwsProvider` 类，而无需改动核心调度逻辑。

*   **FR-P3-4: 系统健康检查**
    *   提供一个无需登录即可访问的 API 端点，如 `/health`。
    *   该端点返回 `{"status": "ok"}` 表示应用运行正常，用于外部监控系统（如 Uptime Kuma）的集成。

**此阶段交付成果 (Deliverable):**
一个智能、健壮且具备未来扩展能力的 GCP Guardian V2.0 完整版。它不仅能保护你的账单，还能在新的计费周期自动恢复服务，真正成为一个可靠的“守护者”。
