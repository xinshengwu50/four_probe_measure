# 屏端事件参考

保留当前42字节START及参数EEPROM校验。材料4=GaN，结构0/1/2与电流模式0..4含义不变。PS选档完成后的n0=1用于导航，不是整场完成。这里只是事件源码参考，未在IDE编译或下载TFT。

本版本不再上传图片；旧图片页入口应隐藏或标为不支持。离散色块页由同一测量服务回填，禁止另启服务占用UART。

## 01_start_release.txt

```text
repo 修改参数.x0.val,584
repo 修改参数.x1.val,588
repo 修改参数.x2.val,592
repo 修改参数.x4.val,1000
repo 修改参数.x5.val,1004
repo 修改参数.x6.val,1008
repo 修改参数.x7.val,1012
repo 修改参数.x3.val,1016
sys1=0
if(修改参数.x4.val!=2&&修改参数.x4.val!=3&&修改参数.x4.val!=4)
{
  sys1=1
}
if(修改参数.x5.val<1||修改参数.x5.val>3)
{
  sys1=2
}
if(修改参数.x3.val<0||修改参数.x3.val>4)
{
  sys1=3
}
if(修改参数.x7.val<0||修改参数.x7.val>2)
{
  sys1=4
}
if(修改参数.x0.val<0||修改参数.x0.val>1)
{
  sys1=5
}
if(修改参数.x1.val<=0||修改参数.x2.val<=0)
{
  sys1=6
}
if(修改参数.x5.val==1)
{
  if(修改参数.x6.val<1||修改参数.x6.val>25)
  {
    sys1=7
  }
}
if(sys1==0)
{
  // 先镜像参数，再发送唯一的42字节START帧；不读旧地址596。
  page0.x7.val=修改参数.x0.val
  page0.x6.val=修改参数.x1.val
  page0.x4.val=修改参数.x2.val
  // x85仅供旧数据页导航；发送帧x4仍保持真实材料编号。
  if(修改参数.x7.val==2)
  {
    page1.x85.val=1
  }else if(修改参数.x4.val==4)
  {
    page1.x85.val=2 // GaN复用AlGaN三代页；实际发送x4仍为4
  }else
  {
    page1.x85.val=修改参数.x4.val
  }
  // page0.x0是电流显示，不写入0..4量程模式编号，由PS选档后填写。
  page0.x0.val=0
  printh AA BB
  prints 修改参数.x0.val,0
  printh CC
  prints 修改参数.x1.val,0
  printh DD
  prints 修改参数.x2.val,0
  printh EE
  prints 修改参数.x3.val,0
  printh FF
  prints 修改参数.x4.val,0
  printh 66
  prints 修改参数.x5.val,0
  printh 77
  prints 修改参数.x6.val,0
  printh 88
  prints 修改参数.x7.val,0
  printh AA
  page 正在测量
}else
{
  prints "PARAM_REJECT code=",0
  prints sys1,0
  printh 0D 0A
  page 修改参数
}
```

## 02_change_product_release.txt

```text
repo 修改参数.x0.val,584
repo 修改参数.x1.val,588
repo 修改参数.x2.val,592
repo 修改参数.x4.val,1000
repo 修改参数.x5.val,1004
repo 修改参数.x6.val,1008
repo 修改参数.x7.val,1012
repo 修改参数.x3.val,1016
// 保留未支持选项的名称，但Confirm/START会拦截。
if(修改参数.x4.val==2)
{
  修改参数.cb0.txt="铝镓氮（AlGaN）"
}else if(修改参数.x4.val==3)
{
  修改参数.cb0.txt="单晶硅（Si）"
}else if(修改参数.x4.val==5)
{
  修改参数.cb0.txt="碳化硅（SiC）"
}else if(修改参数.x4.val==4)
{
  修改参数.cb0.txt="氮化镓（GaN）"
}else if(修改参数.x4.val==6)
{
  修改参数.cb0.txt="氧化锌（ZnO）"
}else if(修改参数.x4.val==7)
{
  修改参数.cb0.txt="添加+"
}else
{
  修改参数.cb0.txt="未设置"
}
if(修改参数.x5.val==1)
{
  修改参数.cb1.txt="自定义单点测量"
}else if(修改参数.x5.val==3)
{
  修改参数.cb1.txt="9点测量"
}else if(修改参数.x5.val==2)
{
  修改参数.cb1.txt="25点测量"
}else if(修改参数.x5.val==4)
{
  修改参数.cb1.txt="49点测量"
}else if(修改参数.x5.val==5)
{
  修改参数.cb1.txt="81点测量"
}else if(修改参数.x5.val==6)
{
  修改参数.cb1.txt="121点测量"
}else if(修改参数.x5.val==7)
{
  修改参数.cb1.txt="自定义二维平面扫描"
}else
{
  修改参数.cb1.txt="未设置"
}
if(修改参数.x0.val==0)
{
  修改参数.cb2.txt="P"
}else if(修改参数.x0.val==1)
{
  修改参数.cb2.txt="N"
}else
{
  修改参数.cb2.txt="未设置"
}
if(修改参数.x3.val==0)
{
  修改参数.cb3.txt="四档量程自动选择"
}else if(修改参数.x3.val==1)
{
  修改参数.cb3.txt="0.1mA"
}else if(修改参数.x3.val==2)
{
  修改参数.cb3.txt="1mA"
}else if(修改参数.x3.val==3)
{
  修改参数.cb3.txt="10mA"
}else if(修改参数.x3.val==4)
{
  修改参数.cb3.txt="100mA"
}else if(修改参数.x3.val==5)
{
  修改参数.cb3.txt="更换其他档位"
}else
{
  修改参数.cb3.txt="未设置"
}
if(修改参数.x7.val==0)
{
  修改参数.cb4.txt="外延片"
}else if(修改参数.x7.val==1)
{
  修改参数.cb4.txt="衬底片"
}else if(修改参数.x7.val==2)
{
  修改参数.cb4.txt="HEMT"
}else
{
  修改参数.cb4.txt="未设置"
}
page 修改参数
```

## 03_confirm_press.txt

```text
// 仅将下拉选项写入变量，不发送START、不在按下时切页。
if(修改参数.cb0.txt=="铝镓氮（AlGaN）")
{
  修改参数.x4.val=2
}else if(修改参数.cb0.txt=="单晶硅（Si）")
{
  修改参数.x4.val=3
}else if(修改参数.cb0.txt=="碳化硅（SiC）")
{
  修改参数.x4.val=5
}else if(修改参数.cb0.txt=="氮化镓（GaN）"||修改参数.cb0.txt=="GaN")
{
  修改参数.x4.val=4
}else if(修改参数.cb0.txt=="氧化锌（ZnO）")
{
  修改参数.x4.val=6
}else if(修改参数.cb0.txt=="添加+")
{
  修改参数.x4.val=7
}else
{
  修改参数.x4.val=255
}
if(修改参数.cb1.txt=="自定义单点测量")
{
  修改参数.x5.val=1
}else if(修改参数.cb1.txt=="9点测量")
{
  修改参数.x5.val=3
}else if(修改参数.cb1.txt=="25点测量")
{
  修改参数.x5.val=2
}else if(修改参数.cb1.txt=="49点测量")
{
  修改参数.x5.val=4
}else if(修改参数.cb1.txt=="81点测量")
{
  修改参数.x5.val=5
}else if(修改参数.cb1.txt=="121点测量")
{
  修改参数.x5.val=6
}else if(修改参数.cb1.txt=="自定义二维平面扫描")
{
  修改参数.x5.val=7
}else
{
  修改参数.x5.val=255
}
if(修改参数.cb2.txt=="P")
{
  修改参数.x0.val=0
}else if(修改参数.cb2.txt=="N")
{
  修改参数.x0.val=1
}else
{
  修改参数.x0.val=255
}
if(修改参数.cb3.txt=="四档量程自动选择")
{
  修改参数.x3.val=0
}else if(修改参数.cb3.txt=="0.1mA")
{
  修改参数.x3.val=1
}else if(修改参数.cb3.txt=="1mA")
{
  修改参数.x3.val=2
}else if(修改参数.cb3.txt=="10mA")
{
  修改参数.x3.val=3
}else if(修改参数.cb3.txt=="100mA")
{
  修改参数.x3.val=4
}else if(修改参数.cb3.txt=="更换其他档位")
{
  修改参数.x3.val=5
}else
{
  修改参数.x3.val=255
}
if(修改参数.cb4.txt=="外延片")
{
  修改参数.x7.val=0
}else if(修改参数.cb4.txt=="衬底片")
{
  修改参数.x7.val=1
}else if(修改参数.cb4.txt=="HEMT")
{
  修改参数.x7.val=2
}else
{
  修改参数.x7.val=255
}
```

## 04_confirm_release.txt

```text
sys1=0
if(修改参数.x4.val!=2&&修改参数.x4.val!=3&&修改参数.x4.val!=4)
{
  sys1=1
}
if(修改参数.x5.val<1||修改参数.x5.val>3)
{
  sys1=2
}
if(修改参数.x3.val<0||修改参数.x3.val>4)
{
  sys1=3
}
if(修改参数.x7.val<0||修改参数.x7.val>2)
{
  sys1=4
}
if(修改参数.x0.val<0||修改参数.x0.val>1)
{
  sys1=5
}
if(修改参数.x1.val<=0||修改参数.x2.val<=0)
{
  sys1=6
}
if(修改参数.x5.val==1)
{
  if(修改参数.x6.val<1||修改参数.x6.val>25)
  {
    sys1=7
  }
}
if(sys1==0)
{
  wepo 修改参数.x0.val,584
  wepo 修改参数.x1.val,588
  wepo 修改参数.x2.val,592
  wepo 修改参数.x4.val,1000
  wepo 修改参数.x5.val,1004
  wepo 修改参数.x6.val,1008
  wepo 修改参数.x7.val,1012
  wepo 修改参数.x3.val,1016
}else
{
  if(sys1==7)
  {
    keybdB.loadpageid.val=3
    keybdB.loadcmpid.val=14
    page keybdB
  }else
  {
    prints "PARAM_REJECT code=",0
    prints sys1,0
    printh 0D 0A
  }
}
```
