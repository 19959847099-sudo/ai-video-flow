# ComfyUI 接入判断 · A-06

审计日期：2026-09-16。当前接入的是官方开源 Server API 契约；没有连接远程实例，也没有运行 ComfyUI 模型。没有新增运行依赖、SDK、模型权重或 Custom Nodes。

## 官方依据与采用方式

- [API Workflow 格式](https://docs.comfy.org/development/api-development/workflow-api-format)：执行图采用节点 ID → class_type / inputs，连接用 [节点 ID, 输出序号]；不提交含 nodes / links / 布局坐标的 UI Workflow JSON。
- [官方基本 API 示例](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py)：在图的 inputs 注入文字、种子等参数，POST /prompt 的 JSON 包含 prompt。我们使用独立 client_id，服务端生成 prompt_id。
- [官方 Server 路由](https://docs.comfy.org/development/comfyui-server/comms_routes)：上传图片、提交、轮询 Queue / History、读取输出图。选择轮询，避免引入 WebSocket 依赖；/ws 可在后续确有进度需求时替换外围观察方式。
- [官方服务端实现](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py)：提交返回 prompt_id / number / node_errors；失败返回 error / node_errors。GET /queue 的 pending / running 条目按第二项 prompt_id 匹配；GET /history/{prompt_id} 按该 ID 查询。没有匹配任务时明确失败，不把“队列为空”当成成功，也不自动重复提交。
- [官方获取图片示例](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example.py)：History outputs 中按输出节点取得 filename / subfolder / type，经 GET /view 查询参数获得图片字节。结果必须先入本地库才判 completed。
- [官方内置节点](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py)：使用 CheckpointLoaderSimple、CLIPTextEncode、LoadImage、VAEEncode、KSampler、VAEDecode、SaveImage；没有参考图时用 EmptyLatentImage。
- [当前 fal / Kling O3 输入契约](https://fal.ai/models/fal-ai/kling-video/o3/standard/reference-to-video/api)：同一已接入 endpoint 提供 start_image_url，语义是视频首帧；image_urls 继续表达参考图。A-06 映射前者，不把普通 @Image 引用冒充首帧。

## 代码边界

ImageTask 是 Provider-independent 的生产快照。WorkflowBuilder 只负责执行表示和参考图拼板；ComfyAdapter 负责 API 路由、提交/状态/错误/结果解释；Transport 负责 I/O。当前唯一可用 Transport 是 FixtureTransport，无 HTTP 客户端、环境密钥读取或联网后备路径。

上传请求表示明确包含 multipart/form-data、fields(type/subfolder/overwrite)、files.image 的文件名、本地路径与哈希；Transport 负责把文件描述转换成 multipart 文件字节。图片读取采用 /view?filename=...&subfolder=...&type=output。首批 GUI 演示的 exchange 使用较早的本地上传描述与查询参数表示；dsh-final 的 exchange 和最终自动测试验证整理后的正式请求表示。没有把旧执行证据重写成新版本。

## 模板与真实能力边界

一个共享模板服务三个用途。按有效 Reference 顺序用现有 Pillow 合成参考图拼板，所有输入都记录来源、哈希与拼板区域；LoadImage → VAEEncode → KSampler 的连接保证图像输入确实参与执行图。文字包括角色、Look、场景、State、Shot 和生成描述。

这是最小 img2img 接口模板，**不是经过质量验证的角色一致性工作流**。拼板可能在真实生成中产生拼贴构图；没有声称具有 IP-Adapter、ControlNet 或原生角色条件能力。后续质量实验可更换外围模板，无需迁移 Character / Scene / Shot。

默认模型槽为 REMOTE_CHECKPOINT_REQUIRED.safetensors，并标记 checkpoint_configured=false。参数和节点图结构可检查，但模型是否存在、节点版本与服务端执行校验均未验证。真实接入前必须选择远程实例已有的兼容 checkpoint，并确认 object_info；当前不能把占位模型的结构验证称为服务端执行成功。

现有 fal V0 仍保留最多 4 张有效 Reference、单张 10 MB、最终 Prompt 2500 字符的本地预算，首帧另映射 start_image_url。新 Reference 采纳可能使参考图数超限；系统报错，用户决定精简，不静默丢弃。费用、实际兼容性与视觉效果均未进行线上实验。
