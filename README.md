# A股趋势与资金观察看板（GitHub Pages）

## 当前版本说明
- 静态网页：`index.html`
- 自动更新脚本：`scripts/update_data.py`
- 定时任务：`.github/workflows/update.yml`
- 数据输出：`data/dashboard.json`
- 计划在工作日北京时间约 16:10 运行一次；也可在 Actions 中手动运行。
- 首版优先尝试指数日线和行业/概念板块资金流向。市场宽度、估值分位、股债利差暂不伪造，待数据源核验后接入。
- 公共数据接口可能变化、延迟或在 GitHub runner 网络环境下不可用，必须查看 Actions 日志验证结果。

## 最简单的部署步骤（建议电脑操作）
1. 下载并解压项目 ZIP。
2. 登录 GitHub，创建一个新仓库，例如 `ashare-dashboard`。建议设为 Public（GitHub Pages 免费使用最方便）。
3. 在仓库页面选择 **Add file → Upload files**，把解压后的所有项目文件和文件夹上传到仓库根目录。注意 `.github` 是隐藏目录；如果网页上传方式不方便上传隐藏目录，可以用 GitHub Desktop 上传整个文件夹。
4. 打开仓库 **Settings → Pages**。
5. 在 **Build and deployment** 中选择 **Deploy from a branch**，Branch 选 `main`，目录选 `/(root)`，点击 Save。
6. 打开 **Actions** 标签页，选择 **Update A-share dashboard data**，点击 **Run workflow → Run workflow**，等待结束。
7. 如果 Actions 成功，回到仓库查看 `data/dashboard.json` 是否更新；再访问 Pages 显示的网址。
8. Pages 首次发布可能需要几分钟。网址一般为 `https://你的GitHub用户名.github.io/仓库名/`。

## 如果 Actions 失败
1. 打开 **Actions → 最近一次运行 → 失败的步骤**。
2. 展开红色失败步骤，复制错误文字发给 ChatGPT。
3. 不要先让 Codex反复重写整个项目；先根据日志定位具体接口或依赖问题。

## 重要提醒
- GitHub Pages 只托管静态文件；行情由 GitHub Actions 预先获取并写入 JSON。
- 网页不是实时交易终端。自动任务受 GitHub 调度、公开数据源、网络与接口限制影响。
- 行业资金流是第三方估算指标，不是交易所披露的真实机构账户净买入。
- 请勿把空值当作 0，也不要用单一指标作出加仓/减仓决定。
