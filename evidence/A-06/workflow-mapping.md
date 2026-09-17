# Workflow Mapping 与三种 Dry Run

| 用途 | Task | Result | 人工结果 |
|---|---|---|---|
| CHARACTER_REFERENCE | [task](gui-data/image_tasks/dbfff949506441f8b525128de56d3fc4/task.json) / [workflow](gui-data/image_tasks/dbfff949506441f8b525128de56d3fc4/workflow.json) | [PNG](gui-data/image_results/20fc42cd38f14606ac84de5f55c56f49/image.png) | variant |
| SCENE_REFERENCE | [task](gui-data/image_tasks/49689fe4488f4c8b866589ad8c867532/task.json) / [workflow](gui-data/image_tasks/49689fe4488f4c8b866589ad8c867532/workflow.json) | [PNG](gui-data/image_results/5502ea8911234d9e8e7cf0a8298867ff/image.png) | variant |
| SHOT_FIRST_FRAME | [task](gui-data/image_tasks/6ea017c47b714b2f95e31f7a06074da4/task.json) / [workflow](gui-data/image_tasks/6ea017c47b714b2f95e31f7a06074da4/workflow.json) | [PNG](gui-data/image_results/f663c7effadf44d2be15e1d0f3fcbac7/image.png) | Rejected |
| SHOT_FIRST_FRAME | [task](gui-data/image_tasks/a6fca7a7fa734d208f73f0a917956993/task.json) / [workflow](gui-data/image_tasks/a6fca7a7fa734d208f73f0a917956993/workflow.json) | [PNG](gui-data/image_results/2892d2e785254fc694fc5f754f5a496d/image.png) | first_frame |
| SHOT_FIRST_FRAME | [task](gui-data/image_tasks/9733b06f652e4b569f7371fa3ce5a2b6/task.json) / [workflow](gui-data/image_tasks/9733b06f652e4b569f7371fa3ce5a2b6/workflow.json) | [PNG](gui-data/image_results/5e0b895931a2442ba6ac600b9fd13485/image.png) | 待审核 |
| SHOT_FIRST_FRAME | [task](gui-data/image_tasks/bb48365ec8414a3aa6d6b3fae7030675/task.json) / [workflow](gui-data/image_tasks/bb48365ec8414a3aa6d6b3fae7030675/workflow.json) | [PNG](gui-data/image_results/f76003314d9141629ec23274d867b804/image.png) | 待审核 |

角色稳定信息、Look、场景稳定信息、State、Shot 要求和最终描述进入节点 6 的 CLIPTextEncode；有效参考图按顺序进入 reference-board.png，reference_bindings 保留角色/场景角色标签、来源 ID、哈希、区域；节点 10 LoadImage → 5 VAEEncode → 3 KSampler → 8 VAEDecode → 9 SaveImage。模型名和节点 ID 只在 workflow.json。

最终协议留痕见 dsh-final 对应任务的 exchange.json：multipart 上传描述、POST /prompt、GET /history/{prompt_id}、GET /queue、GET /view 查询参数与图片字节长度。实际网络请求为 0。