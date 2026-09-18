"""Concise user-facing messages for preparation asset status."""
from __future__ import annotations


def asset_message(report):
    status = report['status']
    reason = report['reason']
    if status in ('resolved', 'free'):
        return ''
    if status == 'changed':
        return '文件内容已变化 · 请确认新版'
    if status == 'missing':
        if '丢失' in reason:
            return '文件已丢失 · 请重新选择'
        if '解除' in reason:
            return '还没有选定素材'
        return '缺少素材'
    if '多个同名' in reason:
        return '找到多个同名素材 · 请选择'
    if '改名关系不唯一' in reason:
        return '找到相同内容的文件 · 请确认'
    if 'Candidate' in reason:
        return '当前素材审核已变化 · 请重新判断'
    return reason


def finishing_message(message):
    """Keep a useful warning while hiding backend naming."""
    import re
    message = re.sub(r'Shot (\d+):', r'镜头 \1：', message)
    for old, new in (
        ('没有正式 Current 视频', '还没有选定视频'),
        ('Current 与镜头不匹配', '选定视频与镜头不匹配'),
        ('Current 已不可用或审核状态改变', '选定视频已不可用，请重新判断'),
        ('Trim 范围无效或短于 0.05 秒', '裁切范围无效或短于 0.05 秒'),
        ('Trim Out 必须晚于 Trim In', '终点必须晚于起点'),
        ('Trim In 不能小于零', '起点不能小于零'),
        ('Split 点必须位于有效片段内部', '切分点必须位于片段内部'),
        ('Volume 只允许 0–200%', '音量只允许 0–200%'),
        ('Segment 不存在', '片段不存在'),
        ('装配没有启用的片段', '本章没有可用片段'),
        ('源视频无音轨；预览使用静音', '源视频无音轨 · 预览静音'),
    ):
        message = message.replace(old, new)
    return message


def operation_message(message):
    """Translate expected production failures at the GUI boundary."""
    for old, new in (
        ('请先应用有效的 Production Script', '请先应用剧本'),
        ('Draft 已存在；重建需要明确确认', '提示词已存在，请选择重新生成'),
        ('请先创建 Prompt Draft', '请先创建提示词'),
        ('Draft 所属项目与当前项目不一致', '提示词不属于当前项目'),
        ('目标需求不属于当前镜头或媒体类型', '当前镜头没有这个生成目标'),
        ('Candidate 需先审核为 Green，再明确绑定', '请先判断为可用，再设为当前'),
        ('仅可绑定当前需求下有效的 Green Candidate', '请先选用有效素材'),
        ('仅可绑定仍然有效的 Green Candidate', '请先选用有效素材'),
        ('仅可选用仍然有效的镜头视频 Candidate', '请先选用有效视频'),
        ('当前需求没有 Candidate 绑定', '当前没有选定素材'),
        ('Candidate 与当前项目镜头不匹配', '素材与当前镜头不匹配'),
        ('Candidate 不存在', '素材不存在'),
        ('当前本地 Fixture 仅支持图像；音频和视频可导入为 Candidate', '此处只能生成示例图片；声音和视频请导入文件'),
        ('Production Job 不存在', '生成任务不存在'),
        ('文件已变化，请先重新扫描', '文件已变化，请同步素材'),
        ('不可绑定：需求、素材类型或文件状态不匹配', '素材类型或文件状态不匹配'),
    ):
        message = message.replace(old, new)
    return message
