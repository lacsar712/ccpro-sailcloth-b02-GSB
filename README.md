# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

每个帆布间设有**日条数封顶**：当天该间允许新登记浸渍的条数到顶后，再登会被拒绝并给出中文原因；改卷态、标已固化不占条数。封顶数字与是否启用可在「日条数封顶」专页调整，页上「今日已用」= 当天该间新插入的浸渍条数。

规则实现：`backend/core/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- 完整顶栏：**晾晒架**、**日条数封顶**、布卷台账、浸渍台账、退出
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/caps` 日条数封顶（专页）**：按帆布间查看/修改当日新登记浸渍条数封顶与是否启用，并显示今日已用与剩余
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，非主路径

API 契约不变（JWT、`/api/lofts|rolls|dips|caps|dashboard/`）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
