#!/usr/bin/env python3
"""Deterministic, person-free scanner fixtures for detection regression experiments.

Procedural vector-style landscapes, not photographs. Every frame is 1008x360;
18-pixel separator bands provide known synthetic boundaries.
"""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np

WIDTH, HEIGHT, GAP = 1008, 360, 18
PALETTES = [((223,226,191),(187,208,175),(144,182,153),(121,161,142)),
            ((216,219,231),(188,195,218),(164,176,195),(136,164,176)),
            ((220,209,181),(188,190,150),(143,170,145),(112,148,137))]

def frame(index, palette):
    sky,far,near,water=palette
    canvas=np.empty((HEIGHT,WIDTH,3),np.uint8)
    canvas[:]=sky
    cv2.circle(canvas,(785,65),28,(154,196,238),-1,cv2.LINE_AA)
    cv2.fillPoly(canvas,[np.array([(0,166),(130,85),(255,142),(385,65),(550,151),(695,98),(860,160),(1008,110),(1008,248),(0,248)])],far,cv2.LINE_AA)
    cv2.fillPoly(canvas,[np.array([(0,201),(188,144),(337,194),(510,127),(685,192),(844,143),(1008,186),(1008,255),(0,255)])],near,cv2.LINE_AA)
    canvas[225:]=water
    for j in range(17):
        y=233+j*7
        x=(j*107+index*8)%970
        cv2.line(canvas,(x,y),(min(1007,x+65+j%4*16),y),tuple(min(255,c+22) for c in water),1,cv2.LINE_AA)
    # An unmanned toy sailboat moves across twelve consecutive synthetic frames.
    x=190+index*43; y=258+round(3*np.sin(index*.8))
    cv2.fillPoly(canvas,[np.array([(x-53,y),(x+55,y),(x+34,y+20),(x-35,y+20)])],(66,111,177),cv2.LINE_AA)
    cv2.line(canvas,(x,y),(x,y-115),(65,83,80),3,cv2.LINE_AA)
    cv2.fillPoly(canvas,[np.array([(x-6,y-109),(x-65,y-8),(x-6,y-8)])],(219,232,240),cv2.LINE_AA)
    cv2.fillPoly(canvas,[np.array([(x+5,y-88),(x+48,y-8),(x+5,y-8)])],(169,196,213),cv2.LINE_AA)
    for j in range(3): cv2.line(canvas,(x-45+j*9,y+26+j*5),(x+36-j*7,y+26+j*5),tuple(min(255,c+35) for c in water),1,cv2.LINE_AA)
    # Stable subtle grain makes the preview closer to a scanner texture.
    noise=np.random.default_rng(400+index).normal(0,1.1,canvas.shape)
    return np.clip(canvas.astype(float)+noise,0,255).astype(np.uint8)


def generate(destination):
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    records=[]
    for strip in range(3):
        frames=[frame(strip*4+i,PALETTES[strip]) for i in range(4)]
        image=np.full((4*HEIGHT+3*GAP,WIDTH,3),9,np.uint8)
        rects=[]
        for i,f in enumerate(frames):
            y=i*(HEIGHT+GAP); image[y:y+HEIGHT]=f
            rects.append({'x':0,'y':y,'width':WIDTH,'height':HEIGHT})
        name=f'synthetic_scan_{strip+1:02d}.png'
        ok,encoded=cv2.imencode('.png',image)
        if not ok: raise RuntimeError('PNG encoding failed')
        (destination/name).write_bytes(encoded.tobytes())
        records.append({'file':name,'frames':rects})
    (destination/'README.md').write_text('# 无人物公开示例\n\n程序绘制的山水与无人模型帆船，共 3 张长条 / 12 帧。用于界面演示，既非用户照片，也非真实扫描仪样本。\n\n生成：`python scripts/generate_public_demo.py`。原始 `demo/` 实拍数据继续供检测回归使用，不用于公开截图。\n',encoding='utf-8')
    (destination/'manifest.json').write_text(json.dumps({'synthetic':True,'people':False,'total_frames':12,'sources':records},indent=2),encoding='utf-8')
    return records

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'output/synthetic-fixtures')
    generate(parser.parse_args().output)
