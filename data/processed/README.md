# 陕西传统村落数据说明

## 数据来源

- 来源网站：https://www.dmctv.cn/villages.aspx?lx=cl
- 采集范围：该网站陕西村落列表及各村详情数据
- 采集时间：2026-11-11
- 说明：该网站当前返回陕西村落 37 条，不代表陕西省全部传统村落名录。

## 城市分类结果

| 城市 | 村落数 |
|---|---:|
| 西安市 | 1 |
| 铜川市 | 0 |
| 宝鸡市 | 0 |
| 咸阳市 | 2 |
| 渭南市 | 1 |
| 延安市 | 7 |
| 汉中市 | 0 |
| 榆林市 | 13 |
| 安康市 | 13 |
| 商洛市 | 0 |

没有数据的城市保留为 0，不建议在前端显示为空页面。

## 输出文件

### data/processed/shanxi_cities.json

适合前端“城市 → 纵向村落图片长廊”页面使用。

每个城市包含：

- name：城市名称
- code：行政区划代码
- slug：URL 标识
- village_count：村落数量
- has_data：是否有数据
- villages：村落数组

每个村落包含：

- id
- name
- cover_image
- images：图片 URL 数组
- location
- source_url

这个文件不包含村落介绍，适合只展示“村落名称 + 自动轮播图片”的城市页。

### data/processed/shanxi_villages.json

全部村落详情数据，包含：

- 所属城市
- 地理位置
- 简介
- 村落属性
- 历史、建筑、环境、民俗、非遗、生产生活、旅游导览等内容模块
- 历史人物
- 历史环境要素
- 图片
- 视频
- 原始来源 URL

不同村落的内容模块数量不同，前端应按照 `sections` 动态渲染，没有内容的模块不要显示。

### data/processed/villages/{id}.json

单个村落详情数据，方便后端按村落 ID 查询。

### data/processed/knowledge_chunks.jsonl

用于后续 AI 问答和向量检索的知识片段。每行包含：

- village_id
- village_name
- city
- section_type
- title
- text
- source_url

### data/processed/knowledge/{id}.txt

按村落整理后的纯文本知识文件，适合人工检查或重新切片。

### data/processed/shanxi_villages.csv

便于 Excel 查看的村落索引表。

## 数据使用注意

1. 图片和文字均保留原始来源 URL，展示时应尽量注明来源。
2. 数据是网站公开展示内容，不等同于官方完整名录。
3. 某些村落没有非遗、保护现状、历史人物等模块，这是正常情况。
4. “没有采集到资料”不等于“该村落没有相关文化”，AI 回答时必须区分这两种情况。
5. 后续如果要正式上线，建议重新核对重点村落的行政归属、名录等级和资料更新时间。
