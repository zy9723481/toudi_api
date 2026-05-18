# boss_delivery_v2.py UI 优化设计

日期: 2026-05-18 | 状态: 待审批

## 一、移除活跃时间筛选

### 1.1 AutoDeliveryTab._init_ui（第3560-3576行）
**删除**整个"活跃时间筛选"行：
- QLabel("活跃时间不早于：")
- QDateEdit + QCheckBox("任意时间")
- 对应 time_row 布局

删除后 row 序号前移，后续参数行号相应调整。

### 1.2 AutoDeliveryTab._on_start（第3757-3765行）
**删除**：
```python
filter_date = self.filter_date_edit.date().toString("yyyy-MM-dd")  # 删除
filter_any_time = self.filter_any_time_check.isChecked()           # 删除
time_desc = "不筛选" if filter_any_time else f"≥{filter_date}"     # 删除
# 日志中的 活跃时间{time_desc} 部分删除
```

### 1.3 AutoDeliverWorker.__init__（第3140行）
**删除**参数：`filter_date: str = ""`, `filter_any_time: bool = False`
**删除**属性赋值：`self.filter_date`, `self.filter_any_time`

### 1.4 AutoDeliverWorker._run_api_delivery
**删除**时间筛选代码块（约22行：`if not self.filter_any_time and self.filter_date...` 整段）

### 1.5 Worker 实例化调用
**删除** `filter_date=filter_date, filter_any_time=filter_any_time` 传参

### 1.6 保留不变
- 表格列[4] "活跃时间"：显示 `active_time` 转换后的日期
- 表格列[5] "活跃描述"：显示 `active_time_desc` 原文
- `_fill_job_table_row` 中活跃时间列的填充逻辑
- `BOSSApiClient._get_job_detail_real` 返回的 `active_time/active_time_desc`
- `JobDatabase` 中 `active_time/active_time_desc` 字段

---

## 二、布局压缩修复

### 2.1 标签文字缩短

| 原文 | 改为 |
|------|------|
| "投递模式：" | "模式：" |
| "岗位关键字：" | "关键字：" |
| "工作地区：" | "地区：" |
| "最低匹配度：" | "匹配度：" |
| "目标投递数量：" | "目标数量：" |
| "投递延迟：" | "延迟：" |
| "招呼语：" | "招呼语："（不变） |
| "匹配度原因"（表头） | "原因" |

### 2.2 输入控件最小宽度
- `FIELD_MIN_W`：`160` → `180`
- 延迟 QSpinBox：`80` → `90`
- 日期编辑若保留则 `130` → `150`
- 所有 QLineEdit 设置 `setSizePolicy(Expanding, Fixed)`

### 2.3 表格列宽策略

列索引 | 列名 | 模式 | 最小宽度
---|---|---|---
0 | 岗位名称 | Stretch | -
1 | 公司 | Interactive | 100
2 | 地区 | Interactive | 60
3 | 薪资 | Interactive | 80
4 | 活跃时间 | Interactive | 80
5 | 活跃描述 | ResizeToContents | 70
6 | 匹配度 | ResizeToContents | 55
7 | 原因 | ResizeToContents | 100
8 | 岗位详情 | Stretch | -
9 | 投递模式 | ResizeToContents | 60
10 | 状态 | ResizeToContents | 65

关键改动：公司/地区/薪资/活跃时间列从 `ResizeToContents` → `Interactive`，允许用户拖拽但保留最小宽度。

---

## 三、全局 UI 美化

### 3.1 色彩体系

```python
COLORS = {
    "bg_main": "#f5f6fa",
    "bg_card": "#ffffff",
    "border": "#e2e8f0",
    "primary": "#4a6cf7",
    "primary_hover": "#3b5de7",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text_primary": "#1e293b",
    "text_secondary": "#64748b",
    "text_muted": "#94a3b8",
    "header_bg": "#f1f5f9",
}
```

### 3.2 全局 QSS 样式表

在 `main()` 中通过 `app.setStyleSheet()` 统一设置：

#### QGroupBox
```css
QGroupBox {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    color: #1e293b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
}
```

#### QPushButton
```css
QPushButton {
    background-color: #4a6cf7;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}
QPushButton:hover { background-color: #3b5de7; }
QPushButton:pressed { background-color: #2d4ecc; }
QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
```

绿色按钮（开始投递）：`#10b981`，hover `#059669`
红色按钮（停止投递）：`#ef4444`，hover `#dc2626`

#### QTableWidget
```css
QTableWidget {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    alternate-background-color: #f8fafc;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background: #eef2ff; color: #1e293b; }
QHeaderView::section {
    background: #f1f5f9;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    padding: 6px 8px;
    font-weight: bold;
    color: #475569;
}
```

#### QLineEdit / QSpinBox / QDateEdit
```css
QLineEdit, QSpinBox, QDateEdit {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 6px 10px;
    background: #ffffff;
    color: #1e293b;
}
QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {
    border-color: #4a6cf7;
}
```

#### QTabWidget
```css
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 0 0 8px 8px;
    background: #f5f6fa;
}
QTabBar::tab {
    background: #e2e8f0;
    color: #64748b;
    padding: 8px 20px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #f5f6fa;
    color: #4a6cf7;
    border-bottom: 2px solid #4a6cf7;
}
QTabBar::tab:hover { color: #4a6cf7; }
```

#### QProgressBar
```css
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #e2e8f0;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background: #4a6cf7;
    border-radius: 4px;
}
```

#### QCheckBox / QRadioButton
```css
QCheckBox, QRadioButton { color: #1e293b; spacing: 8px; }
```

### 3.3 各标签页美化

#### AccountTab（账号管理）
- 整体背景色 `#f5f6fa`，卡片区白底
- 用户状态 GroupBox：登录前灰色提示，登录后绿色"已登录"标识
- 按钮组统一风格：登录=主色、注册=灰色、激活=绿色

#### ResumeTab（简历管理）
- 上传按钮带图标效果（emoji 前缀）
- 分析结果区域白底卡片
- 分析按钮：未上传时禁用态灰色

#### AutoDeliveryTab（自动投递）
- 参数区：白底卡片，表单元素间距 10px
- 开始/停止按钮：绿/红区分
- 进度条：细条 8px 高，圆角
- 岗位列表：交替行色 `#ffffff` / `#f8fafc`
- 状态列着色：成功绿、失败红、跳过灰

#### RecordTab（投递记录）
- 统计数字用大字体 + 色彩强调
- 表格同上述 QSS 统一样式

### 3.4 主窗口
- 整体背景 `#f5f6fa`
- 日志区：深色终端风格（`#1e1e1e` 底 + `#d4d4d4` 字），最大高度 150px
- 窗口最小尺寸 `1000 x 680`

---

## 四、实施顺序

1. 移除活跃时间筛选（UI + Worker 逻辑）
2. 缩短标签 + 调整控件最小宽度
3. 表格列宽策略调整
4. 添加全局 QSS 样式表
5. 各标签页内联样式微调
6. 语法检查 → 启动验证

## 五、验证

```bash
python boss_delivery_v2.py
```

检查点：
- [ ] 参数区不再显示"活跃时间不早于"
- [ ] 表格仍有"活跃时间"、"活跃描述"列
- [ ] 窗口缩窄至 1000px 时，所有输入框可正常操作
- [ ] 表格列可拖拽调整宽度
- [ ] UI 风格统一（白底卡片 + 蓝紫主色调 + 圆角）
- [ ] 按钮 hover/pressed/disabled 三态正确
- [ ] 标签页切换流畅
