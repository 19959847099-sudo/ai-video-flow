from pathlib import Path
from PIL import Image,ImageDraw
p=Path('examples/reference-fixtures');p.mkdir(parents=True,exist_ok=True)
for name,color,label in [('01-identity','#ccbba7','TEST IDENTITY'),('02-daily','#8baaaa','TEST DAILY LOOK'),('03-rain','#556980','TEST RAIN LOOK')]:
 im=Image.new('RGB',(480,360),color); d=ImageDraw.Draw(im); d.text((40,140),label,fill='white',font_size=28);d.text((40,190),'FIXTURE ONLY / NOT PRODUCTION',fill='white',font_size=18);im.save(p/(name+'.png'))
