# Open-source Integration Map

| 对象 | 本轮决策 | 实际复用与原因 |
|---|---|---|
| DeepSeek Harness | INTEGRATE | 官方 CLI 0.1.5-rc.2、profile、工具注册/执行和结果事件；避免自建 Harness，未 fork |
| FFmpeg / ffprobe | USE | 复用已有 8.1 CLI 编码、媒体校验；新增 DSH 可调用探测边界，没有自研编码器 |
| ComfyUI | LATER / 契约学习 | 未实际接入；未发现可直接复用实例，不为本轮安装模型或 CUDA |
| WhisperX | LATER | 本轮无语音对齐需求，不安装、不宣称已集成 |
| OpenTimelineIO | LATER | 本轮无 Timeline 交换需求，不安装、不实现剪辑 |
| AI Movie Studio 2 | LATER / 后续参考 | 未运行、未抽取代码；不作为本轮已证明能力 |

DSH 安装来自官方 npm 包，MIT LICENSE 随包保留。FFmpeg 使用本机已有 Gyan essentials 8.1 构建，包含 GPL/version3 与 libx264；本轮未重新分发二进制。未增加 Python 运行依赖。完整 DSH npm 发行版约 213 MiB、518 包，隔离安装以便移除；并非声称上游依赖很小。

## ComfyUI Integration Note — 未实际接入

现场检查了进程、默认 8188 监听和常见安装目录，未发现可直接使用的运行实例；这不是全盘未安装证明。为避免扩展成模型部署，本轮只阅读官方契约。

后续若已有可用实例，可由外部工具把当前 Task 的引用映射到 **API format workflow**：节点 ID 对应 `class_type` 与 `inputs`，节点连接为节点 ID/输出索引。它不同于编辑器布局 JSON。通过 `/upload/image` 导入媒体、`POST /prompt` 提交，保存返回的 prompt_id；通过 `/history/{prompt_id}` 查询并按返回媒体信息调用 `/view`。结果仍由本项目校验入库，不把工作流 JSON 当 Production Truth。

以上仅为下一轮接入契约说明，未发送请求、未运行工作流、未生成 ComfyUI 图像。官方来源：[API workflow format](https://docs.comfy.org/development/api-development/workflow-api-format)、[服务端路由](https://docs.comfy.org/development/comfyui-server/comms_routes)。

DSH 来源：[官方仓库](https://github.com/deepseek-ai/deepseek-harness)、[官方工具开发](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/tool)、[无密钥工具执行](https://deepseek-harness.github.io/deepseek-harness/en/develop/cordis-tutorial/07-into-the-harness)、[CLI/profile 参考](https://deepseek-harness.github.io/deepseek-harness/en/reference/)。这些契约支持本轮集成方式，不代表已验证模型自主决策。
