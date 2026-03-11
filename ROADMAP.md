# 小红书功能扩展规划

  当前功能

  - ✅ 笔记信息采集 — 标题、描述、互动数据
  - ✅ 评论信息采集 — 评论者、内容、互动数据
  - ✅ 用户信息提取 — 从笔记/评论提取用户到用户库

  ---
  新增功能规划

  1. 视频采集模块

  功能描述
  - 解析视频笔记，提取多画质 CDN 直链
  - 支持下载到本地或返回链接

  数据模型 (xhs_videos 表)
  id, note_id, title
  video_url_1080p, video_url_720p, video_url_480p
  cover_url, duration, size
  download_status, local_path
  source_task_id, created_at

  API 接口

  ┌─────────────────────────────────┬──────┬──────────────────────┐
  │              接口               │ 方法 │         功能         │
  ├─────────────────────────────────┼──────┼──────────────────────┤
  │ /api/collect/xhs-video-info     │ POST │ 解析视频笔记获取直链 │
  ├─────────────────────────────────┼──────┼──────────────────────┤
  │ /api/collect/xhs-video-download │ POST │ 下载视频到服务器     │
  ├─────────────────────────────────┼──────┼──────────────────────┤
  │ /api/collect/xhs-videos         │ GET  │ 列出已采集的视频     │
  └─────────────────────────────────┴──────┴──────────────────────┘

  ---
  2. 图片采集模块

  功能描述
  - 解析图文笔记，获取所有图片
  - 返回有水印/无水印两个版本
  - 支持批量下载

  数据模型 (xhs_images 表)
  id, note_id, image_index
  url_watermark, url_original
  width, height, format
  download_status, local_path
  source_task_id, created_at

  API 接口

  ┌─────────────────────────────────┬──────┬──────────────────────────┐
  │              接口               │ 方法 │           功能           │
  ├─────────────────────────────────┼──────┼──────────────────────────┤
  │ /api/collect/xhs-image-info     │ POST │ 解析图文笔记获取图片链接 │
  ├─────────────────────────────────┼──────┼──────────────────────────┤
  │ /api/collect/xhs-image-download │ POST │ 下载图片到服务器         │
  ├─────────────────────────────────┼──────┼──────────────────────────┤
  │ /api/collect/xhs-images         │ GET  │ 列出已采集的图片         │
  └─────────────────────────────────┴──────┴──────────────────────────┘

  ---
  3. 创作者中心模块

  功能描述
  - 素材管理：整理采集的视频/图片素材
  - 二次创作：去水印、裁剪、拼接
  - 内容发布：一键发布到多平台（需登录）

  数据模型

  creator_projects 表（创作项目）
  id, name, description
  source_note_ids (JSON), source_type
  status (draft/processing/done)
  created_at, updated_at

  creator_assets 表（素材资源）
  id, project_id
  asset_type (video/image)
  original_url, processed_url
  local_path, status
  created_at

  API 接口

  ┌───────────────────────────────┬──────────┬──────────────┐
  │             接口              │   方法   │     功能     │
  ├───────────────────────────────┼──────────┼──────────────┤
  │ /api/creator/projects         │ GET/POST │ 创作项目管理 │
  ├───────────────────────────────┼──────────┼──────────────┤
  │ /api/creator/assets           │ GET/POST │ 素材管理     │
  ├───────────────────────────────┼──────────┼──────────────┤
  │ /api/creator/remove-watermark │ POST     │ 去水印处理   │
  ├───────────────────────────────┼──────────┼──────────────┤
  │ /api/creator/merge-video      │ POST     │ 视频拼接     │
  ├───────────────────────────────┼──────────┼──────────────┤
  │ /api/creator/publish          │ POST     │ 发布内容     │
  └───────────────────────────────┴──────────┴──────────────┘

  前端页面
  - CreatorCenter.vue — 创作者中心主页
  - ProjectEdit.vue — 项目编辑页（素材选择、编辑预览）

  ---
  技术要点

  ┌────────────┬───────────────────────────────────────────────────────┐
  │    功能    │                       技术实现                        │
  ├────────────┼───────────────────────────────────────────────────────┤
  │ 视频解析   │ 解析 window.__INITIAL_STATE__ 获取 video.media.stream │
  ├────────────┼───────────────────────────────────────────────────────┤
  │ 无水印图片 │ 替换 URL 中的 sns-webpic-qc 为 ci                     │
  ├────────────┼───────────────────────────────────────────────────────┤
  │ 去水印处理 │ FFmpeg 裁剪 / OpenCV 图像修复                         │
  ├────────────┼───────────────────────────────────────────────────────┤
  │ 视频拼接   │ FFmpeg concat                                         │
  ├────────────┼───────────────────────────────────────────────────────┤
  │ 异步处理   │ Celery / BackgroundTasks                              │
  └────────────┴───────────────────────────────────────────────────────┘

  ---
  实现优先级

  ┌────────┬─────────────────────┬────────┐
  │ 优先级 │        功能         │ 工作量 │
  ├────────┼─────────────────────┼────────┤
  │ P0     │ 视频/图片链接解析   │ 1天    │
  ├────────┼─────────────────────┼────────┤
  │ P1     │ 下载到服务器        │ 0.5天  │
  ├────────┼─────────────────────┼────────┤
  │ P2     │ 创作者中心-素材管理 │ 1天    │
  ├────────┼─────────────────────┼────────┤
  │ P3     │ 去水印/二次编辑     │ 2天    │
  ├────────┼─────────────────────┼────────┤
  │ P4     │ 多平台发布          │ 3天    │
  └────────┴─────────────────────┴────────┘


# Media Ops Platform 开发规划

## 项目概述

媒体运营平台，支持小红书、B站等平台的内容采集、用户触达和二次创作。

---

## 当前已完成功能

### 采集任务模块
- ✅ 小红书关键词搜索笔记
- ✅ 小红书笔记评论采集
- ✅ B站关键词搜索视频
- ✅ B站视频评论采集
- ✅ B站用户粉丝列表采集

### 用户库模块
- ✅ 从笔记/评论提取用户
- ✅ 获取用户详细信息（粉丝、关注、获赞等）
- ✅ 用户状态管理

### 触达任务模块
- ✅ AI 生成评论回复
- ✅ 小红书评论发送
- ✅ B站评论发送
- ✅ 批量发送 + 多账号轮换

### 账号管理模块
- ✅ 多平台账号管理
- ✅ Cookie 存储
- ✅ 每日限额控制

---

## 小红书功能扩展规划

### 1. 视频采集模块 (P0)

**功能描述**
- 解析视频笔记，提取多画质 CDN 直链（1080p/720p/480p）
- 支持下载到本地或返回链接

**数据模型** (`xhs_videos` 表)
```
id              - 主键
note_id         - 笔记ID
title           - 标题
video_url_1080p - 1080p 直链
video_url_720p  - 720p 直链
video_url_480p  - 480p 直链
cover_url       - 封面图
duration        - 时长（秒）
size            - 文件大小
download_status - 下载状态 (pending/downloading/done/failed)
local_path      - 本地路径
source_task_id  - 来源任务ID
created_at      - 创建时间
```

**API 接口**
| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/collect/xhs-video-info` | POST | 解析视频笔记获取直链 |
| `/api/collect/xhs-video-download` | POST | 下载视频到服务器 |
| `/api/collect/xhs-videos` | GET | 列出已采集的视频 |

---

### 2. 图片采集模块 (P0)

**功能描述**
- 解析图文笔记，获取所有图片
- 返回有水印/无水印两个版本
- 支持批量下载

**数据模型** (`xhs_images` 表)
```
id              - 主键
note_id         - 笔记ID
image_index     - 图片序号
url_watermark   - 有水印 URL
url_original    - 无水印 URL
width           - 宽度
height          - 高度
format          - 格式 (jpg/png/webp)
download_status - 下载状态
local_path      - 本地路径
source_task_id  - 来源任务ID
created_at      - 创建时间
```

**API 接口**
| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/collect/xhs-image-info` | POST | 解析图文笔记获取图片链接 |
| `/api/collect/xhs-image-download` | POST | 下载图片到服务器 |
| `/api/collect/xhs-images` | GET | 列出已采集的图片 |

---

### 3. 创作者中心模块 (P2-P4)

**功能描述**
- 素材管理：整理采集的视频/图片素材
- 二次创作：去水印、裁剪、拼接
- 内容发布：一键发布到多平台

**数据模型**

`creator_projects` 表（创作项目）
```
id              - 主键
name            - 项目名称
description     - 描述
source_note_ids - 来源笔记IDs (JSON)
source_type     - 类型 (video/image/mixed)
status          - 状态 (draft/processing/done)
created_at      - 创建时间
updated_at      - 更新时间
```

`creator_assets` 表（素材资源）
```
id              - 主键
project_id      - 项目ID
asset_type      - 类型 (video/image)
original_url    - 原始URL
processed_url   - 处理后URL
local_path      - 本地路径
status          - 状态
created_at      - 创建时间
```

**API 接口**
| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/creator/projects` | GET/POST | 创作项目管理 |
| `/api/creator/assets` | GET/POST | 素材管理 |
| `/api/creator/remove-watermark` | POST | 去水印处理 |
| `/api/creator/merge-video` | POST | 视频拼接 |
| `/api/creator/publish` | POST | 发布内容 |

**前端页面**
- `CreatorCenter.vue` — 创作者中心主页
- `ProjectEdit.vue` — 项目编辑页

---

## 技术要点

| 功能 | 技术实现 |
|------|----------|
| 视频解析 | 解析 `window.__INITIAL_STATE__` 获取 `video.media.stream` |
| 无水印图片 | 替换 URL 参数，移除水印标记 |
| 去水印处理 | FFmpeg 裁剪 / OpenCV 图像修复 |
| 视频拼接 | FFmpeg `concat` |
| 异步处理 | Celery / BackgroundTasks |

---

## 开发优先级

| 优先级 | 功能 | 状态 | 预估工作量 |
|--------|------|------|------------|
| P0 | 视频/图片链接解析 | 🔄 进行中 | 1天 |
| P1 | 下载到服务器 | ⏳ 待开始 | 0.5天 |
| P2 | 创作者中心-素材管理 | ⏳ 待开始 | 1天 |
| P3 | 去水印/二次编辑 | ⏳ 待开始 | 2天 |
| P4 | 多平台发布 | ⏳ 待开始 | 3天 |

---

## 更新日志

### 2026-03-03
- 创建开发规划文档
- 开始 P0：视频/图片链接解析功能

### 2026-03-02
- 完成小红书评论发送功能
- 完成用户信息获取功能
- 推送代码到 GitHub
