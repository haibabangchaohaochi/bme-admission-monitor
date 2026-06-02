# 2026 生物医学工程方向夏令营与预推免监控看板

这是一个面向生物医学工程保研场景的长期监控系统，使用 Python 定时抓取学校/研究所官网公告，并将结果生成到 GitHub Pages 静态看板中。

## 功能

系统支持夏令营、暑期学校、校园开放日、预推免、推免生接收通知的持续监控，自动生成状态页、历史记录和移动端友好的 PWA 页面。它也支持人工新增、人工修正、候选链接留痕和多种通知接口。

## 本地运行

先安装依赖：

```bash
pip install -r requirements.txt
```

然后依次执行：

```bash
python scripts/merge_schools.py
python scripts/check_updates.py
python scripts/build_dashboard.py
python -m http.server 8000 -d docs
```

打开浏览器访问 `http://localhost:8000` 即可查看看板。

## GitHub Pages 部署

1. 创建一个 GitHub 仓库。
2. 上传本项目代码。
3. 进入仓库 `Settings -> Pages`。
4. `Source` 选择 `Deploy from branch`。
5. `Branch` 选择 `main`。
6. `Folder` 选择 `/docs`。
7. 保存后等待 GitHub Pages 构建完成。

部署成功后，静态页面将从 `docs/` 目录提供服务。

## GitHub Actions

`monitor.yml` 会在北京时间每天 08:00、14:00、20:00 定时运行，并支持手动触发。流程会执行：

1. `python scripts/merge_schools.py`
2. `python scripts/check_updates.py`
3. `python scripts/build_dashboard.py`

如果 `data/status.json`、`data/history.csv`、`docs/status.json` 或 `docs/history.csv` 有变化，workflow 会自动提交并推送。

## 通知配置

你可以在仓库 Secrets 中配置以下环境变量：

1. `PUSHPLUS_TOKEN`
2. `BARK_KEY`
3. `WECOM_WEBHOOK`
4. `SMTP_HOST`
5. `SMTP_USER`
6. `SMTP_PASSWORD`
7. `NOTIFY_EMAIL_TO`

如果没有配置任何通知 token，脚本会只在控制台打印提醒，不会报错。

## 新增学校

### 本机临时新增

在首页或 `docs/add.html` 中填写表单后点击“本机临时加入”，数据会保存在当前浏览器的 `localStorage` 中，只对当前设备有效，并且会标记为“本机临时新增”。

### 永久新增

点击“生成 YAML 配置”后，把生成内容复制到 `data/extra_schools.yaml`，或者点击“提交到 GitHub Issue”创建一个带 `add-school` 标签的 issue。仓库配置了 `add-school-from-issue.yml`，当 issue 被打上标签后会自动解析 YAML 并写入仓库。

如果自动解析失败，workflow 会在 issue 中留言，提示你手动复制 YAML 到 `data/extra_schools.yaml`。

## 人工修正

`data/manual_overrides.yaml` 用于覆盖自动抓取结果。你可以手动指定：

1. 官方链接
2. 夏令营状态
3. 预推免状态
4. 报名截止时间
5. 活动时间
6. 备注

人工修正优先级高于自动识别。

## 手机添加到主屏幕

### iPhone

1. 用 Safari 打开 GitHub Pages 链接。
2. 点击底部分享按钮。
3. 选择“添加到主屏幕”。

### 安卓 Chrome

1. 用 Chrome 打开 GitHub Pages 链接。
2. 点击右上角菜单。
3. 选择“添加到主屏幕”或“安装应用”。

微信内置浏览器不一定支持完整 PWA，建议复制链接到 Safari 或 Chrome 打开。

## 导出数据

首页提供“导出数据”按钮，可导出当前视图对应的 CSV 和 JSON。历史记录保存在 `data/history.csv`，也会同步到 `docs/history.csv` 供静态页面查看。

## 目录说明

数据主入口在 `data/`，静态网页在 `docs/`，抓取和生成逻辑在 `scripts/`。