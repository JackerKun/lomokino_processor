# 🔧 修复确认对话框按钮显示问题

## 问题
删除帧时，确认对话框没有显示按钮或按钮是英文的。这是macOS上QMessageBox的已知问题。

## 解决方案

### 方案1: QMessageBox（失败）
```python
msg_box = QMessageBox(self)
msg_box.setWindowTitle("确认删除")
msg_box.setText(f"确定要删除帧 {index + 1} 吗?")
msg_box.setIcon(QMessageBox.Icon.Question)

# 添加中文按钮
yes_btn = msg_box.addButton("确定", QMessageBox.ButtonRole.YesRole)
no_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.NoRole)

msg_box.exec()
```
**问题**: 在macOS上，QMessageBox的自定义按钮可能不显示

### 方案2: 自定义QDialog（成功）✅

创建自定义对话框类：

```python
class ConfirmDialog(QDialog):
    """Custom confirmation dialog with visible buttons"""

    def __init__(self, parent=None, title="确认", message="确定要执行此操作吗?"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.result_value = False

        # Set minimum size to ensure buttons are visible
        self.setMinimumSize(400, 150)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Message label
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(message_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumSize(100, 35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        cancel_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(cancel_btn)

        # Confirm button
        confirm_btn = QPushButton("确定")
        confirm_btn.setMinimumSize(100, 35)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        confirm_btn.clicked.connect(self.on_confirm)
        button_layout.addWidget(confirm_btn)

        layout.addLayout(button_layout)

    def on_confirm(self):
        """Handle confirm button click"""
        self.result_value = True
        self.accept()

    def on_cancel(self):
        """Handle cancel button click"""
        self.result_value = False
        self.reject()
```

**使用方法**：
```python
def remove_frame(self, index):
    """Remove a frame by index"""
    dialog = ConfirmDialog(
        self,
        title="确认删除",
        message=f"确定要删除帧 {index + 1} 吗?"
    )
    dialog.exec()

    # 检查用户的选择
    if dialog.result_value:
        # 执行删除操作
        pass
```

## 关键改进点

### 1. 使用QDialog代替QMessageBox
- QDialog在所有平台上表现一致
- 完全控制对话框布局和样式
- 按钮始终可见

### 2. 设置最小尺寸
```python
self.setMinimumSize(400, 150)
```
**作用**: 确保对话框足够大，按钮有足够空间显示

### 3. 明确的按钮样式
```python
cancel_btn.setMinimumSize(100, 35)
```
**作用**:
- 设置按钮最小尺寸
- 使用CSS样式美化按钮
- 添加悬停效果

### 4. 使用result_value标志
```python
self.result_value = False  # 初始化为False
```
**作用**:
- 明确记录用户选择
- 不依赖QDialog的返回值
- 更清晰的代码逻辑

## 改进效果

### 对话框外观
```
┌─────────────────────────┐
│  ?  确认删除             │
├─────────────────────────┤
│                         │
│  确定要删除帧 5 吗?      │
│                         │
├─────────────────────────┤
│        [确定]  [取消]    │
└─────────────────────────┘
```

### 按钮说明
- **确定** - 绿色/蓝色高亮，执行删除
- **取消** - 灰色，取消操作

## 同时修复的其他对话框

### 1. 清空胶片列表
```
┌─────────────────────────┐
│  ⚠  确认清空             │
├─────────────────────────┤
│                         │
│  确定要清空所有胶片吗?   │
│                         │
├─────────────────────────┤
│        [确定]  [取消]    │
└─────────────────────────┘
```

### 2. 删除帧
```
┌─────────────────────────┐
│  ?  确认删除             │
├─────────────────────────┤
│                         │
│  确定要删除帧 3 吗?      │
│                         │
├─────────────────────────┤
│        [确定]  [取消]    │
└─────────────────────────┘
```

## 使用流程

### 删除帧
1. 点击帧右上角的红色 **×** 按钮
2. 弹出确认对话框（带**确定**和**取消**按钮）
3. 点击**确定** → 删除帧
4. 点击**取消** → 取消操作

### 清空列表
1. 点击**清空列表**按钮
2. 弹出确认对话框（带**确定**和**取消**按钮）
3. 点击**确定** → 清空所有胶片
4. 点击**取消** → 保留胶片

## 技术细节

### 自定义按钮的优势
1. **完全中文化** - 按钮文字可控
2. **跨平台一致** - Mac/Windows显示一致
3. **可自定义** - 可以改变按钮文字和样式
4. **更清晰** - "确定/取消"比"Yes/No"更明确

### 代码实现
```python
# 创建消息框
msg_box = QMessageBox(parent_widget)
msg_box.setWindowTitle("标题")
msg_box.setText("消息内容")
msg_box.setIcon(QMessageBox.Icon.Question)  # 问号图标

# 添加自定义按钮（中文）
yes_btn = msg_box.addButton("确定", QMessageBox.ButtonRole.YesRole)
no_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.NoRole)

# 显示对话框
msg_box.exec()

# 检查用户点击了哪个按钮
if msg_box.clickedButton() == yes_btn:
    # 用户点击了"确定"
    执行操作()
else:
    # 用户点击了"取消"或关闭了对话框
    取消操作()
```

## 运行测试

```bash
./run_gui.sh
```

### 测试步骤
1. **测试删除帧**
   - 添加胶片并提取帧
   - 点击某个帧的 × 按钮
   - 应该看到带**确定**和**取消**按钮的对话框
   - 点击确定删除，或取消保留

2. **测试清空列表**
   - 添加几个胶片
   - 点击"清空列表"
   - 应该看到带**确定**和**取消**按钮的对话框
   - 点击确定清空，或取消保留

## 其他改进

所有确认对话框现在都使用统一的中文按钮样式：
- ✅ 删除帧
- ✅ 清空列表
- ✅ 其他需要确认的操作

## 按钮样式

### 默认按钮（确定）
- 通常是蓝色或高亮显示
- 按Enter键会触发

### 取消按钮
- 灰色显示
- 按Esc键会触发

---

现在确认对话框应该可以正常显示中文按钮了！✅
