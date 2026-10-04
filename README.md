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
| `worker2` | `123456` | 操作工（第二名浸胶工，用于交叉登记验证） |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

**日条数封顶**：按帆布间设置当天允许新登记浸渍的条数（`DailyDipCap`，与 `Loft` 一对一）。

- 仅拦截「新登记浸渍」（`POST /api/dips/`）；改卷态、标已固化不吃封顶。
- 已用数 = 当天该帆布间实际新插入的 `DipRun` 条数（以 `created_at` 写入时刻计，与手填开工时间无关），专页「已用」与右侧面板每次写入一一对应。
- 到顶后再登记返回 `403 {"detail": "「xx」今日浸渍登记已达封顶 N 条（已用 N 条），不能再登记新浸渍"}`。
- 写入在事务内对帆布间行 `select_for_update`，两名浸胶工并发交叉登记时两笔都会被挡，不会超登。
- 封顶可在专页随时改数字或关闭；关闭后立即可以再登记。

规则实现：`backend/core/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

顶栏可在两个主页面间切换，左侧栏另保留次要台账入口。

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`），架头显示今日浸渍已用/封顶；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/caps` 日条数封顶（主）**：按帆布间修改封顶数字、启用/停用，并显示当天已用（= 当天该间新插入浸渍条数，服务端实时口径）
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API：JWT；`/api/lofts|rolls|dips|dashboard/`，loft 响应附带 `capEnabled` / `capLimit` / `capUsedToday`；封顶设置经 `GET|PATCH /api/lofts/{id}/cap/`（字段 `enabled`、`limit`，回显 `usedToday`）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
