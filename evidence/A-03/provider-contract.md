# A-03 Provider 选型与契约

核对日期：2026-09-15。选择 **fal.ai**，模型 **Kling O3 Standard Reference-to-Video**。这是 fal 托管接口，不是可灵原生 API。只接一家，不增加备选 Adapter。

## 官方依据

- [模型官方 API](https://fal.ai/models/fal-ai/kling-video/o3/standard/reference-to-video/api)：多参考图 `image_urls`，提示词使用 `@Image1` 等引用；文件输入可使用 data URI。输入含 prompt、duration、aspect_ratio、generate_audio；输出为 video 文件对象。
- [官方异步队列](https://fal.ai/docs/documentation/model-apis/inference/queue)：提交返回 request_id、status_url、response_url；状态为 IN_QUEUE、IN_PROGRESS、COMPLETED。COMPLETED 可带 error / error_type，必须检查后再取结果。
- [官方请求错误](https://fal.ai/docs/documentation/model-apis/request-errors)：错误包含 detail / error_type；超时和运行器失败属于明确错误分支。

## 为什么选它

当前数据已经有角色身份图、Look 图、场景稳定图和 State 图。多参考图接口可以直接使用这些资源，不必增加云端 Character ID、上传资产注册流程或改变 Production Data。正式 REST 契约足以完成本轮零调用验证，不需要安装 SDK。

这证明接口具备参考图输入能力；尚未证明模型在真实视频中的角色一致性、场景一致性或画质。

## 本轮映射决定

| 项目数据 | Provider 请求 |
|---|---|
| Task.final_prompt | body.prompt 的生产描述主体 |
| Task.references | image_urls 前部；Character / Look 标注 |
| Task.scene_references | image_urls 后部；Scene / State 标注 |
| 每张 Reference | 校验 SHA-256 后编码为 data URI |
| Reference 顺序 | @ImageN 绑定附加到最终请求描述 |
| 最小视频设置 | duration="3"，aspect_ratio="16:9"，generate_audio=false，shot_type="customize" |

POST 的目标地址：`https://queue.fal.run/fal-ai/kling-video/o3/standard/reference-to-video`。Fixture 不添加 Authorization。未来线上调用需要官方鉴权头，但本轮没有 HTTP Transport、密钥读取、在线开关或自动联网降级。

本轮主动限制最多 4 张图、每张 10 MB、最终描述 2500 字符。它们是本地 V0 预算，不是宣称 Provider 的通用硬上限。超限明确失败，不截断、不丢图。暂不实现 elements、视频参考、多镜头、音频或不同生成参数 UI。

## Fixture 与生产事实

`app/fixtures/fal_queue.json` 是依照官方契约人工构造的响应样本，**不是线上调用录制结果**。URL 中 `fixture.invalid` 只匹配本地视频工厂，永不下载网络文件。

五步本地回放：提交响应 → IN_QUEUE → IN_PROGRESS → COMPLETED → video 响应。提交响应的任务 ID 和方便地址被保存，随后依照返回地址读取状态和结果。Fixture 使用执行 ID 作为确定性 request_id；不声称线上 ID 也这样产生。

本地 completed 只在取到结果、FFmpeg 产生实际 MP4、ffprobe 检查与入库完成后成立。错误、超时、缺失视频进入 failed，不自动再次提交。失败次数仍计入 Take 编号。

## 持久化和兼容

Character、Scene、Shot、GenerationTask 的模型和已有记录没有迁移。Execution 仅允许新增 fal Provider，model 改为字符串；旧值仍有效。

每份 fal Task 旁保存 provider_request.json 和 provider_exchange.json，分别记录最终 Provider 请求及本地响应过程。核心 Task 仍保留中立描述与资产快照。Retry 继承来源结果的 Provider，不受当前下拉框影响；Select 始终需要明确操作。

## 依赖判断与下一次真实验证边界

直接复用现有 Pydantic、Pillow、FFmpeg、FFplay；新逻辑使用 Python 标准库，无新增运行依赖。保留轻量 REST 映射，无 SDK 安装维护成本。

本轮未验证鉴权、额度、实际模型参数受理、外网传输、服务可用性、生成质量或实际费用。将来真实试调用应先重新核对契约并明确授权与费用上限，再实现 HTTP Transport、超时/恢复策略和真实下载；不能把当前 Fixture 切换成付费生成。
