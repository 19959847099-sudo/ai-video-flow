"""Original vector study assets. Illustrations, never AI generation evidence."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from .workspace import Workspace

SOURCE = '''雨停之前/名称
01/章节/一把没有主人的伞

001/雨夜，推门进入
【林夏/-/深色雨衣】/低声
【便利店/雨夜】/雨声、冰柜低鸣

镜头：
【门内后退跟拍】 保持中景，随着推门轻轻后移。

动作：
林夏推开玻璃门，停在暖光边缘。
右手的【红伞.破损】还在滴水。

表演：
她想说些什么，却先望了一眼窗外。

对白：
林夏：这把伞，是不是有人来找过？

连续性：
雨衣肩部潮湿，伞柄朝向右侧。

002/柜台后的目光
【林夏/-/深色雨衣】/低声
店员/-/米色围裙/-
【便利店/雨夜】/冰柜低鸣

镜头：
越过林夏的肩膀，缓慢推向柜台后的店员。

动作：
店员看向【红伞.破损】，把手里的纸杯放下。

表演：
目光停顿，不急于回答。

003/玻璃上的雨痕
【便利店/雨夜】/雨声

镜头：
雨滴沿玻璃向下滑落，店内倒影渐渐模糊。

备注：
无人镜头，不需要人物或 Voice。

02/章节/天亮以后

001/街角的空位
【林夏/-/深色雨衣】/-
清晨的街角/远处车声

镜头：
固定远景，保留环境的空旷感。

动作：
林夏把【红伞.破损】留在门边，走出画面。
'''

SCENE = '''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">
<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#172c34"/><stop offset="1" stop-color="#465451"/></linearGradient><linearGradient id="glass" x2="0" y2="1"><stop stop-color="#e5b979"/><stop offset="1" stop-color="#8d9678"/></linearGradient></defs>
<rect width="960" height="600" fill="url(#sky)"/><path d="M0 430L960 380V600H0Z" fill="#243c40"/>
<path d="M160 160L820 140V435L160 465Z" fill="#263b3c"/><path d="M145 160L835 140V195L145 215Z" fill="#d9d4ad"/>
<text x="205" y="190" fill="#3b4d47" font-size="25" letter-spacing="15" font-family="sans-serif">NIGHT STORE</text>
<path d="M190 230L790 210V415L190 440Z" fill="url(#glass)"/>
<path d="M215 285L765 266M210 341L763 320M211 396L765 375" stroke="#6c7661" stroke-width="15"/>
<g stroke="#364944" stroke-width="12"><path d="M390 220V432M590 216V424M700 213V421"/></g>
<path d="M450 232L565 229V425L450 430Z" fill="#263e3f" opacity=".7"/><path d="M547 310V346" stroke="#e4d09a" stroke-width="5"/>
<g stroke="#a4b9b3" stroke-width="2" opacity=".32"><path d="M40 20L-5 170M140 0L50 290M245 0L205 125M367 0L322 130M475 0L438 123M603 0L565 120M755 0L716 115M905 0L860 126M912 248L865 389M129 332L55 547M882 427L832 591M644 475L609 593M346 481L322 585"/></g>
<path d="M196 466L770 437L848 527L129 558Z" fill="#c5b47e" opacity=".15"/>
<text x="40" y="553" fill="#d3dfd4" font-size="16" font-family="sans-serif" letter-spacing="3">VISUAL STUDY / ORIGINAL VECTOR / NOT GENERATED FOOTAGE</text></svg>'''

CHARACTER = '''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="760" viewBox="0 0 600 760">
<rect width="600" height="760" fill="#c2c5b2"/><rect x="32" y="32" width="536" height="696" fill="#d7d8c8"/>
<path d="M32 565L568 470V728H32Z" fill="#afb7a5"/>
<circle cx="301" cy="241" r="75" fill="#354842"/><path d="M241 232Q259 169 312 179Q369 183 369 236L351 299L270 300Z" fill="#424f46"/>
<path d="M264 223Q294 207 335 229L328 290L275 290Z" fill="#d1ab84"/>
<path d="M267 287L241 323L186 383L153 614L451 614L410 381L344 315L327 289L296 326Z" fill="#354d48"/>
<path d="M241 323L299 387L344 315M299 387V611" stroke="#758675" stroke-width="4" fill="none"/>
<path d="M211 397L178 561M390 393L423 570" stroke="#2b3e3b" stroke-width="18"/>
<path d="M219 614L214 699M381 614L392 699" stroke="#273937" stroke-width="39"/>
<text x="61" y="90" fill="#4e5c4b" font-size="15" font-family="sans-serif" letter-spacing="3">CHARACTER / VISUAL STUDY</text>
<text x="61" y="126" fill="#405044" font-size="26" font-family="sans-serif">01 - RAINCOAT</text>
<text x="61" y="679" fill="#e2e4d1" font-size="12" font-family="sans-serif">ILLUSTRATIVE REFERENCE / NOT MODEL OUTPUT</text></svg>'''

UMBRELLA = '''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="540" viewBox="0 0 720 540">
<rect width="720" height="540" fill="#dddaca"/><circle cx="357" cy="263" r="187" fill="#e9e5d8"/>
<path d="M360 173V403Q360 457 406 444Q434 435 431 406" stroke="#444e48" stroke-width="12" fill="none"/>
<path d="M139 267Q178 117 360 110Q544 119 582 267Q526 242 481 275Q428 247 360 276Q300 249 244 275Q185 242 139 267Z" fill="#a34d40"/>
<path d="M360 110Q269 149 244 275M360 110V276M360 110Q452 152 481 275" stroke="#c57a61" stroke-width="3" fill="none"/>
<path d="M520 212L555 241L528 247L542 259L516 251Z" fill="#e9e5d8"/><path d="M360 110V91" stroke="#47514a" stroke-width="6"/>
<text x="35" y="49" fill="#65705f" font-size="16" font-family="sans-serif" letter-spacing="3">PROP / THE RED UMBRELLA</text>
<text x="35" y="504" fill="#65705f" font-size="12" font-family="sans-serif">ORIGINAL VECTOR STUDY / ILLUSTRATIVE ASSET</text></svg>'''


def render_svg(source, target):
    renderer = QSvgRenderer(QByteArray(source.encode('utf-8')))
    image = QImage(renderer.defaultSize(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target)): raise OSError('无法保存示意资产')


def create_example(root):
    workspace = Workspace(root)
    if workspace.state['draft']: return workspace
    workspace.state['is_example'] = True
    workspace.apply(SOURCE)
    for source, relative in [(CHARACTER, 'character_visual/林夏/-/深色雨衣.png'),
                             (SCENE, 'environment/便利店/雨夜.png'), (UMBRELLA, 'prop/红伞.破损.png')]:
        render_svg(source, workspace.root / 'library' / relative)
    workspace.scan()
    return workspace
