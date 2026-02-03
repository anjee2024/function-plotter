import sys
import numpy as np
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QSplitter, QFrame, QCheckBox, QComboBox, QTabWidget,
    QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox, QListWidget,
    QListWidgetItem, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QDate
from PyQt6.QtGui import QFont
import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import re
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
import os

# 设置matplotlib使用SimHei字体支持中文
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.use('QtAgg')

# 颜色列表用于多曲线显示
LINE_COLORS = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

try:
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    from pymodbus.exceptions import ModbusException
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False


class FunctionPlotter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("函数曲线绘制器 - 支持Modbus")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Modbus相关变量
        self.modbus_client = None
        self.is_connected = False
        self.is_collecting = False
        
        # 多曲线支持
        self.data_channels = {}  # 格式: {channel_name: {'buffer': deque, 'time': deque, 'line': line, 'color': color}}
        self.active_channels = []  # 活动的通道名称列表
        self.channel_configs = []  # 通道配置列表
        
        # 预定义颜色列表，用于自动分配通道颜色
        self.channel_colors = [
            '蓝色', '红色', '绿色', '橙色', '紫色', '棕色', '粉色', '灰色',
            '橄榄色', '青色', '黑色', '深蓝色', '深红色', '深绿色', '金色', '银色'
        ]

        # 兼容旧的单通道模式
        self.data_buffer = deque(maxlen=1000)
        self.time_buffer = deque(maxlen=1000)

        self.collect_timer = QTimer()
        self.collect_timer.timeout.connect(self.collect_data)

        # 数据库文件路径
        self.db_file = os.path.join(os.path.dirname(__file__), 'modbus_data.db')
        self.init_database()

        # 自定义函数库
        self.custom_functions = []
        self.load_custom_functions()

        # Modbus寄存器配置
        self.register_configs = []
        self.load_register_configs()

        # 存储定时器
        self.storage_timer = QTimer()
        self.storage_timer.timeout.connect(self.save_to_database)
        self.storage_interval = 5000  # 默认5秒
        self.save_to_db = True

        # 曲线样式设置
        self.realtime_style_settings = {
            'line_color': '蓝色',
            'line_width': 2.0,
            'line_style': 0,
            'alpha': 0.8,
            'show_grid': True,
            'show_legend': True,
            'show_marker': True,
            'marker_style': 'o'
        }
        self.history_style_settings = {
            'line_color': '红色',
            'line_width': 2.0,
            'line_style': 0,
            'alpha': 0.7,
            'show_grid': True,
            'show_legend': True,
            'show_marker': True,
            'marker_style': 'o'
        }

        self.init_ui()
        
    def init_database(self):
        """初始化数据库"""
        try:
            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS modbus_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        slave_id INTEGER,
                        address INTEGER,
                        function_code TEXT,
                        value REAL,
                        unit TEXT
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS custom_functions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        expression TEXT NOT NULL,
                        description TEXT
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS register_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        slave_id INTEGER NOT NULL,
                        address INTEGER NOT NULL,
                        count INTEGER NOT NULL,
                        function_code INTEGER NOT NULL,
                        unit TEXT,
                        scale REAL DEFAULT 1.0,
                        offset REAL DEFAULT 0.0
                    )
                ''')

                # 添加可能缺失的列（用于旧版本数据库）
                try:
                    cursor.execute("ALTER TABLE register_configs ADD COLUMN scale REAL DEFAULT 1.0")
                except sqlite3.OperationalError:
                    pass  # 列已存在
                
                try:
                    cursor.execute("ALTER TABLE register_configs ADD COLUMN offset REAL DEFAULT 0.0")
                except sqlite3.OperationalError:
                    pass  # 列已存在

                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            QMessageBox.warning(self, "数据库错误", f"初始化数据库失败: {str(e)}")
    
    def positioned_question(self, title, message, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, default_button=QMessageBox.StandardButton.No):
        """显示定位在界面左侧中部的确认对话框"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(buttons)
        msg_box.setDefaultButton(default_button)
        
        # 计算对话框位置：主窗口左侧中部
        main_geometry = self.geometry()
        dialog_width = 500  # 估计对话框宽度
        dialog_height = 400  # 估计对话框高度
        
        # 计算左侧中部位置
        x = main_geometry.x() + 50  # 左侧偏移50像素
        y = main_geometry.y() + (main_geometry.height() - dialog_height) // 2
        
        msg_box.move(x, y)
        
        return msg_box.exec()
    
    def load_custom_functions(self):
        """加载自定义函数"""
        try:
            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT name, expression, description FROM custom_functions")
                rows = cursor.fetchall()
                self.custom_functions = [{"name": r[0], "expression": r[1], "description": r[2]} for r in rows]
            finally:
                conn.close()
        except Exception as e:
            print(f"加载自定义函数失败: {str(e)}")
            self.custom_functions = []
    
    def load_register_configs(self):
        """加载寄存器配置"""
        try:
            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            
            # 先尝试完整查询（包含scale、offset和color）
            try:
                cursor.execute("SELECT name, slave_id, address, count, function_code, unit, scale, offset, color FROM register_configs")
                rows = cursor.fetchall()
                self.register_configs = [{
                    "name": r[0],
                    "slave_id": r[1],
                    "address": r[2],
                    "count": r[3],
                    "function_code": r[4],
                    "unit": r[5],
                    "scale": r[6] if r[6] is not None else 1.0,
                    "offset": r[7] if r[7] is not None else 0.0,
                    "color": r[8] if r[8] is not None else '蓝色'
                } for r in rows]
            except sqlite3.OperationalError:
                # 如果失败，尝试包含scale和offset但不包含color的查询
                try:
                    cursor.execute("SELECT name, slave_id, address, count, function_code, unit, scale, offset FROM register_configs")
                    rows = cursor.fetchall()
                    self.register_configs = [{
                        "name": r[0],
                        "slave_id": r[1],
                        "address": r[2],
                        "count": r[3],
                        "function_code": r[4],
                        "unit": r[5],
                        "scale": r[6] if r[6] is not None else 1.0,
                        "offset": r[7] if r[7] is not None else 0.0,
                        "color": '蓝色'  # 默认值
                    } for r in rows]
                except sqlite3.OperationalError:
                    # 如果还是失败，尝试基本查询
                    cursor.execute("SELECT name, slave_id, address, count, function_code, unit FROM register_configs")
                    rows = cursor.fetchall()
                    self.register_configs = [{
                        "name": r[0],
                        "slave_id": r[1],
                        "address": r[2],
                        "count": r[3],
                        "function_code": r[4],
                        "unit": r[5],
                        "scale": 1.0,  # 默认值
                        "offset": 0.0,  # 默认值
                        "color": '蓝色'  # 默认值
                    } for r in rows]
            
            conn.close()
        except Exception as e:
            print(f"加载寄存器配置失败: {str(e)}")
            self.register_configs = []
    
    def save_to_database(self):
        """保存数据到数据库"""
        if not self.save_to_db:
            return

        try:
            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            try:
                # 如果有配置的通道,保存所有通道的最新数据
                if self.channel_configs:
                    for config in self.channel_configs:
                        name = config['name']
                        if name in self.data_channels and len(self.data_channels[name]['buffer']) > 0:
                            value = self.data_channels[name]['buffer'][-1]
                            timestamp = self.data_channels[name]['time'][-1].strftime('%Y-%m-%d %H:%M:%S.%f')

                            cursor.execute('''
                                INSERT INTO modbus_data (timestamp, slave_id, address, function_code, value, unit)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (timestamp, config['slave_id'], config['address'],
                                  f"0x{config['function_code']:02X}", float(value), ""))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"保存数据库失败: {str(e)}")
    
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 函数绘制标签页
        func_tab = QWidget()
        func_layout = QHBoxLayout(func_tab)
        
        control_panel = self.create_control_panel()
        func_layout.addWidget(control_panel, 2)
        
        plot_panel = self.create_plot_panel()
        func_layout.addWidget(plot_panel, 4)
        
        self.tab_widget.addTab(func_tab, "函数绘制")
        
        # Modbus实时数据标签页
        if MODBUS_AVAILABLE:
            modbus_tab = self.create_modbus_tab()
            self.tab_widget.addTab(modbus_tab, "Modbus实时数据")
        else:
            no_modbus_tab = QWidget()
            no_modbus_layout = QVBoxLayout(no_modbus_tab)
            msg = QLabel("Modbus功能不可用\n\n请安装pymodbus包:\npip install pymodbus")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setFont(QFont("Arial", 12))
            no_modbus_layout.addWidget(msg)
            self.tab_widget.addTab(no_modbus_tab, "Modbus实时数据")
        
        # 历史数据查询标签页
        history_tab = self.create_history_tab()
        self.tab_widget.addTab(history_tab, "历史数据查询")

        # 连接标签页切换事件，自动应用样式
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # 程序启动时，自动应用样式到当前标签页
        QTimer.singleShot(100, lambda: self.on_tab_changed(self.tab_widget.currentIndex()))
        
    def create_control_panel(self):
        # 创建主容器
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 标题
        title = QLabel("函数绘制器")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(title)
        
        # 函数输入组
        func_group = QGroupBox("函数设置")
        func_layout = QFormLayout()
        
        self.function_input = QLineEdit()
        self.function_input.setPlaceholderText("例如: sin(x), x**2, log(x)")
        self.function_input.setText("sin(x)")
        func_layout.addRow("函数 f(x):", self.function_input)
        
        self.x_min_input = QLineEdit()
        self.x_min_input.setText("-10")
        func_layout.addRow("X 最小值:", self.x_min_input)
        
        self.x_max_input = QLineEdit()
        self.x_max_input.setText("10")
        func_layout.addRow("X 最大值:", self.x_max_input)
        
        self.points_input = QLineEdit()
        self.points_input.setText("1000")
        func_layout.addRow("采样点数:", self.points_input)
        
        func_group.setLayout(func_layout)
        scroll_layout.addWidget(func_group)
        
        # 自定义函数库
        custom_func_group = QGroupBox("自定义函数库")
        custom_func_layout = QVBoxLayout()
        
        self.custom_func_list = QListWidget()
        self.custom_func_list.setMaximumHeight(120)
        for func in self.custom_functions:
            item = QListWidgetItem(f"{func['name']}: {func['expression']}")
            item.setData(Qt.ItemDataRole.UserRole, func['expression'])
            self.custom_func_list.addItem(item)
        
        custom_func_layout.addWidget(self.custom_func_list)
        
        # 自定义函数按钮
        custom_btn_layout = QHBoxLayout()
        
        add_func_btn = QPushButton("添加函数")
        add_func_btn.clicked.connect(self.add_custom_function)
        custom_btn_layout.addWidget(add_func_btn)
        
        del_func_btn = QPushButton("删除函数")
        del_func_btn.clicked.connect(self.delete_custom_function)
        custom_btn_layout.addWidget(del_func_btn)
        
        use_func_btn = QPushButton("使用选中")
        use_func_btn.clicked.connect(self.use_custom_function)
        custom_btn_layout.addWidget(use_func_btn)
        
        custom_func_layout.addLayout(custom_btn_layout)
        custom_func_group.setLayout(custom_func_layout)
        scroll_layout.addWidget(custom_func_group)
        







        
        # 快速函数按钮
        quick_funcs = QGroupBox("快速函数")
        quick_layout = QVBoxLayout()
        
        buttons = [
            ("sin(x)", lambda: self.function_input.setText("sin(x)")),
            ("cos(x)", lambda: self.function_input.setText("cos(x)")),
            ("x²", lambda: self.function_input.setText("x**2")),
            ("x³", lambda: self.function_input.setText("x**3")),
            ("exp(x)", lambda: self.function_input.setText("exp(x)")),
            ("log(x)", lambda: self.function_input.setText("log(x)")),
            ("sqrt(x)", lambda: self.function_input.setText("sqrt(x)")),
            ("tan(x)", lambda: self.function_input.setText("tan(x)")),
        ]
        
        for i, (text, handler) in enumerate(buttons):
            row = QHBoxLayout()
            for j in range(4):
                idx = i * 4 + j
                if idx < len(buttons):
                    btn = QPushButton(buttons[idx][0])
                    btn.clicked.connect(buttons[idx][1])
                    row.addWidget(btn)
            quick_layout.addLayout(row)
            if i == 1:
                break
        
        quick_funcs.setLayout(quick_layout)
        scroll_layout.addWidget(quick_funcs)
        
        # 绘图按钮
        self.plot_button = QPushButton("绘制曲线")
        self.plot_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.plot_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.plot_button.clicked.connect(self.plot_function)
        scroll_layout.addWidget(self.plot_button)
        
        # 清除按钮
        self.clear_button = QPushButton("清除图像")
        self.clear_button.setFont(QFont("Arial", 12))
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.clear_button.clicked.connect(self.clear_plot)
        scroll_layout.addWidget(self.clear_button)
        
        scroll_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        return main_widget
    
    def create_plot_panel(self):
        plot_frame = QFrame()
        plot_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        plot_layout = QVBoxLayout(plot_frame)

        self.figure = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        # 添加导航工具栏(支持拖动、缩放等功能)
        self.func_toolbar = NavigationToolbar(self.canvas, self)
        plot_layout.addWidget(self.func_toolbar)
        plot_layout.addWidget(self.canvas)

        return plot_frame
    
    def add_custom_function(self):
        """添加自定义函数"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加自定义函数")
        layout = QFormLayout()
        
        name_input = QLineEdit()
        expr_input = QLineEdit()
        desc_input = QLineEdit()
        
        layout.addRow("函数名称:", name_input)
        layout.addRow("函数表达式:", expr_input)
        layout.addRow("描述:", desc_input)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            expr = expr_input.text().strip()
            desc = desc_input.text().strip()
            
            if name and expr:
                try:
                    conn = sqlite3.connect(self.db_file, timeout=10.0)
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO custom_functions (name, expression, description)
                            VALUES (?, ?, ?)
                        ''', (name, expr, desc))
                        conn.commit()
                    finally:
                        conn.close()
                    
                    self.load_custom_functions()
                    self.custom_func_list.clear()
                    for func in self.custom_functions:
                        item = QListWidgetItem(f"{func['name']}: {func['expression']}")
                        item.setData(Qt.ItemDataRole.UserRole, func['expression'])
                        self.custom_func_list.addItem(item)
                    
                    QMessageBox.information(self, "成功", "自定义函数添加成功!")
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"添加失败: {str(e)}")
            else:
                QMessageBox.warning(self, "错误", "请输入函数名称和表达式!")
    
    def delete_custom_function(self):
        """删除自定义函数"""
        current_item = self.custom_func_list.currentItem()
        if not current_item:
            return
        
        text = current_item.text()
        name = text.split(":")[0].strip()
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除函数 '{name}' 吗?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_file, timeout=10.0)
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM custom_functions WHERE name = ?", (name,))
                    conn.commit()
                finally:
                    conn.close()
                
                self.load_custom_functions()
                self.custom_func_list.clear()
                for func in self.custom_functions:
                    item = QListWidgetItem(f"{func['name']}: {func['expression']}")
                    item.setData(Qt.ItemDataRole.UserRole, func['expression'])
                    self.custom_func_list.addItem(item)
                
                QMessageBox.information(self, "成功", "自定义函数删除成功!")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {str(e)}")
    
    def use_custom_function(self):
        """使用选中的自定义函数"""
        current_item = self.custom_func_list.currentItem()
        if current_item:
            expr = current_item.data(Qt.ItemDataRole.UserRole)
            self.function_input.setText(expr)
    
    def create_modbus_tab(self):
        modbus_tab = QWidget()
        modbus_layout = QHBoxLayout(modbus_tab)

        modbus_control = self.create_modbus_control_panel()
        modbus_layout.addWidget(modbus_control, 2)

        realtime_plot = self.create_realtime_plot_panel()
        modbus_layout.addWidget(realtime_plot, 4)

        return modbus_tab

    def on_realtime_right_click(self, event):
        """实时曲线右键点击事件"""
        if event.button != 3:  # 右键
            return
        
        # 显示样式设置对话框
        dialog = self.StyleSettingsDialog(self, is_realtime=True)
        # 设置当前值
        dialog.line_color_input.setCurrentText(self.realtime_style_settings['line_color'])
        dialog.line_width_input.setText(str(self.realtime_style_settings['line_width']))
        dialog.line_style_input.setCurrentIndex(self.realtime_style_settings['line_style'])
        dialog.alpha_input.setValue(int(self.realtime_style_settings['alpha'] * 100))
        dialog.grid_checkbox.setChecked(self.realtime_style_settings['show_grid'])
        dialog.legend_checkbox.setChecked(self.realtime_style_settings['show_legend'])
        dialog.marker_checkbox.setChecked(self.realtime_style_settings.get('show_marker', True))
        # 设置标记样式
        marker_style_map = {'o': 0, 's': 1, '^': 2, 'v': 3, 'D': 4, '*': 5, '+': 6, 'x': 7, '.': 8}
        current_marker = self.realtime_style_settings.get('marker_style', 'o')
        dialog.marker_style_input.setCurrentIndex(marker_style_map.get(current_marker, 0))
        
        # 如果有多通道，禁用颜色设置并添加提示
        if len(self.data_channels) > 1:
            dialog.line_color_input.setEnabled(False)
            # 在颜色输入框上方添加提示标签
            from PyQt6.QtWidgets import QLabel
            color_label = dialog.findChild(QLabel, "line_color_label")
            if not color_label:
                # 如果没有标签，在颜色输入框旁边添加提示
                hint_label = QLabel("(多通道模式下，每个通道使用独立的颜色)")
                hint_label.setStyleSheet("color: gray; font-style: italic;")
                dialog.layout().insertRow(4, "", hint_label)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 保存新的样式设置
            settings = dialog.get_settings()
            self.realtime_style_settings.update(settings)
            # 应用样式到实时曲线
            self.apply_style_to_realtime()

    def on_history_right_click(self, event):
        """历史曲线右键点击事件"""
        if event.button != 3:  # 右键
            return
        
        # 显示样式设置对话框
        dialog = self.StyleSettingsDialog(self, is_realtime=False)
        # 设置当前值
        dialog.line_color_input.setCurrentText(self.history_style_settings['line_color'])
        dialog.line_width_input.setText(str(self.history_style_settings['line_width']))
        dialog.line_style_input.setCurrentIndex(self.history_style_settings['line_style'])
        dialog.alpha_input.setValue(int(self.history_style_settings['alpha'] * 100))
        dialog.grid_checkbox.setChecked(self.history_style_settings['show_grid'])
        dialog.legend_checkbox.setChecked(self.history_style_settings['show_legend'])
        dialog.marker_checkbox.setChecked(self.history_style_settings.get('show_marker', True))
        # 设置标记样式
        marker_style_map = {'o': 0, 's': 1, '^': 2, 'v': 3, 'D': 4, '*': 5, '+': 6, 'x': 7, '.': 8}
        current_marker = self.history_style_settings.get('marker_style', 'o')
        dialog.marker_style_input.setCurrentIndex(marker_style_map.get(current_marker, 0))
        
        # 如果有多条历史曲线，禁用颜色设置并添加提示
        if hasattr(self, 'history_ax') and len(self.history_ax.lines) > 1:
            dialog.line_color_input.setEnabled(False)
            # 在颜色输入框上方添加提示标签
            from PyQt6.QtWidgets import QLabel
            hint_label = QLabel("(多通道模式下，每个通道使用独立的颜色)")
            hint_label.setStyleSheet("color: gray; font-style: italic;")
            dialog.layout().insertRow(4, "", hint_label)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 保存新的样式设置
            settings = dialog.get_settings()
            self.history_style_settings.update(settings)
            # 应用样式到历史曲线
            self.apply_style_to_history()

    def apply_style_to_realtime(self):
        """应用样式设置到实时曲线"""
        try:
            if not hasattr(self, 'realtime_ax') or not self.realtime_ax:
                print("警告: realtime_ax 不存在")
                return

            # 获取实时曲线样式设置
            settings = self.realtime_style_settings

            line_width = settings['line_width']

            # 线条样式映射
            line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
            line_style = line_styles[settings['line_style']]

            alpha = settings['alpha']
            show_grid = settings['show_grid']
            show_legend = settings['show_legend']
            show_marker = settings.get('show_marker', True)
            marker_style = settings.get('marker_style', 'o')

            print(f"应用样式到实时曲线: 线宽={line_width}, 样式={line_style}, 透明度={alpha}, 网格={show_grid}, 图例={show_legend}, 标记={show_marker}, 标记样式={marker_style}")

            # 颜色映射
            color_map = {
                '蓝色': 'blue', '红色': 'red', '绿色': 'green', '橙色': 'orange',
                '紫色': 'purple', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
                '橄榄色': 'olive', '青色': 'cyan', '黑色': 'black',
                '深蓝色': 'navy', '深红色': 'darkred', '深绿色': 'darkgreen',
                '金色': 'gold', '银色': 'silver'
            }

            # 更新现有线条样式
            line_count = 0
            for line in self.realtime_ax.lines:
                # 判断是单通道还是多通道模式
                if len(self.data_channels) <= 1:
                    # 单通道模式：应用全局颜色设置
                    line_color = color_map.get(settings.get('line_color', '蓝色'), 'blue')
                    line.set_color(line_color)
                else:
                    # 多通道模式：保留通道的原始颜色
                    pass

                line.set_linewidth(line_width)
                line.set_linestyle(line_style)
                line.set_alpha(alpha)
                if show_marker:
                    line.set_marker(marker_style)
                    line.set_markersize(5)
                else:
                    line.set_marker(None)
                line_count += 1
            print(f"更新了 {line_count} 条线条的样式")

            # 更新网格
            self.realtime_ax.grid(show_grid)

            # 更新图例
            if show_legend:
                legend = self.realtime_ax.get_legend()
                if legend:
                    legend.remove()
                self.realtime_ax.legend()
            else:
                legend = self.realtime_ax.get_legend()
                if legend:
                    legend.remove()

            # 刷新实时曲线
            self.realtime_canvas.draw_idle()
            print("实时曲线已刷新")

        except Exception as e:
            print(f"应用样式到实时曲线时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def create_modbus_control_panel(self):
        # 创建主容器
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 标题
        title = QLabel("Modbus设备")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(title)
        
        # 连接类型选择
        conn_group = QGroupBox("连接方式")
        conn_layout = QFormLayout()
        
        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems(["TCP", "RTU"])
        self.conn_type_combo.currentTextChanged.connect(self.on_conn_type_changed)
        conn_layout.addRow("连接类型:", self.conn_type_combo)
        
        conn_group.setLayout(conn_layout)
        scroll_layout.addWidget(conn_group)
        
        # TCP参数组
        self.tcp_group = QGroupBox("TCP参数")
        tcp_layout = QFormLayout()
        
        self.tcp_host_input = QLineEdit()
        self.tcp_host_input.setText("127.0.0.1")
        tcp_layout.addRow("主机地址:", self.tcp_host_input)
        
        self.tcp_port_input = QLineEdit()
        self.tcp_port_input.setText("502")
        tcp_layout.addRow("端口:", self.tcp_port_input)
        
        self.tcp_group.setLayout(tcp_layout)
        scroll_layout.addWidget(self.tcp_group)
        
        # RTU参数组
        self.rtu_group = QGroupBox("RTU参数")
        rtu_layout = QFormLayout()
        
        rtu_port_layout = QHBoxLayout()
        self.rtu_port_input = QComboBox()
        self.rtu_port_input.setEditable(True)
        self.rtu_port_input.addItem("COM1")
        rtu_port_layout.addWidget(self.rtu_port_input)
        
        search_com_btn = QPushButton("搜索")
        search_com_btn.setMaximumWidth(60)
        search_com_btn.clicked.connect(self.search_serial_ports)
        rtu_port_layout.addWidget(search_com_btn)
        
        rtu_layout.addRow("串口:", rtu_port_layout)
        
        self.rtu_baudrate_input = QComboBox()
        self.rtu_baudrate_input.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.rtu_baudrate_input.setCurrentText("9600")
        rtu_layout.addRow("波特率:", self.rtu_baudrate_input)
        
        self.rtu_databits_input = QComboBox()
        self.rtu_databits_input.addItems(["7", "8"])
        self.rtu_databits_input.setCurrentText("8")
        rtu_layout.addRow("数据位:", self.rtu_databits_input)
        
        self.rtu_stopbits_input = QComboBox()
        self.rtu_stopbits_input.addItems(["1", "2"])
        self.rtu_stopbits_input.setCurrentText("1")
        rtu_layout.addRow("停止位:", self.rtu_stopbits_input)
        
        self.rtu_parity_input = QComboBox()
        self.rtu_parity_input.addItems(["N", "E", "O"])
        self.rtu_parity_input.setCurrentText("N")
        rtu_layout.addRow("校验位:", self.rtu_parity_input)
        
        self.rtu_group.setLayout(rtu_layout)
        self.rtu_group.setVisible(False)
        scroll_layout.addWidget(self.rtu_group)
        
        # 通道配置管理
        channel_config_group = QGroupBox("通道配置管理")
        channel_config_layout = QVBoxLayout()

        # 使用选项卡来区分两种配置方式
        config_tabs = QTabWidget()

        # 配置库标签页
        config_lib_tab = QWidget()
        config_lib_layout = QVBoxLayout(config_lib_tab)

        config_lib_layout.addWidget(QLabel("<b>已保存的配置库</b>"))

        self.reg_config_list = QListWidget()
        self.reg_config_list.setMaximumHeight(120)
        self.reg_config_list.itemDoubleClicked.connect(self.add_config_to_channel)
        self.refresh_register_configs()
        config_lib_layout.addWidget(self.reg_config_list)

        reg_btn_layout = QHBoxLayout()
        add_reg_btn = QPushButton("添加通道配置")
        add_reg_btn.clicked.connect(self.add_register_config)
        reg_btn_layout.addWidget(add_reg_btn)

        edit_reg_btn = QPushButton("修改配置")
        edit_reg_btn.clicked.connect(self.edit_register_config)
        reg_btn_layout.addWidget(edit_reg_btn)

        del_reg_btn = QPushButton("删除配置")
        del_reg_btn.clicked.connect(self.delete_register_config)
        reg_btn_layout.addWidget(del_reg_btn)

        add_to_channel_btn = QPushButton("添加到活动通道")
        add_to_channel_btn.clicked.connect(self.add_config_to_channel)
        reg_btn_layout.addWidget(add_to_channel_btn)

        config_lib_layout.addLayout(reg_btn_layout)

        # 导入导出按钮
        io_btn_layout = QHBoxLayout()
        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self.import_channel_configs)
        io_btn_layout.addWidget(import_btn)

        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self.export_channel_configs)
        io_btn_layout.addWidget(export_btn)

        config_lib_layout.addLayout(io_btn_layout)

        # 添加说明文字
        help_label = QLabel("提示: 选中配置后点击\"添加到活动通道\"即可使用")
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        config_lib_layout.addWidget(help_label)

        config_tabs.addTab(config_lib_tab, "配置库")


        channel_config_layout.addWidget(config_tabs)
        channel_config_group.setLayout(channel_config_layout)
        scroll_layout.addWidget(channel_config_group)

        # 当前活动通道列表
        active_channel_group = QGroupBox("活动通道列表")
        active_channel_layout = QVBoxLayout()

        active_channel_layout.addWidget(QLabel("<b>当前活动的通道 (用于实时采集)</b>"))

        self.channel_list = QListWidget()
        self.channel_list.setMaximumHeight(120)
        active_channel_layout.addWidget(self.channel_list)

        # 显示通道数量
        self.channel_count_label = QLabel("活动通道数: 0")
        self.channel_count_label.setStyleSheet("color: blue; font-weight: bold;")
        active_channel_layout.addWidget(self.channel_count_label)

        channel_action_layout = QHBoxLayout()
        del_channel_btn = QPushButton("删除选中")
        del_channel_btn.clicked.connect(self.delete_channel)
        channel_action_layout.addWidget(del_channel_btn)

        clear_all_btn = QPushButton("清空所有")
        clear_all_btn.clicked.connect(self.clear_all_channels)
        channel_action_layout.addWidget(clear_all_btn)

        active_channel_layout.addLayout(channel_action_layout)
        active_channel_group.setLayout(active_channel_layout)
        scroll_layout.addWidget(active_channel_group)

        # 采集设置组
        collect_group = QGroupBox("采集与存储")
        collect_layout = QFormLayout()
        
        self.sample_interval = QSpinBox()
        self.sample_interval.setRange(10, 60000)
        self.sample_interval.setValue(1000)
        self.sample_interval.setSuffix(" ms")
        collect_layout.addRow("采集间隔:", self.sample_interval)
        
        self.storage_interval_input = QSpinBox()
        self.storage_interval_input.setRange(1, 3600)
        self.storage_interval_input.setValue(5)
        self.storage_interval_input.setSuffix(" 秒")
        collect_layout.addRow("存储间隔:", self.storage_interval_input)

        self.display_time_range = QSpinBox()
        self.display_time_range.setRange(10, 3600)
        self.display_time_range.setValue(60)
        self.display_time_range.setSuffix(" 秒")
        self.display_time_range.setToolTip("设置实时曲线X轴显示的时间范围")
        collect_layout.addRow("显示时间范围:", self.display_time_range)

        self.save_db_checkbox = QCheckBox("保存到数据库")
        self.save_db_checkbox.setChecked(True)
        self.save_db_checkbox.stateChanged.connect(self.toggle_db_save)
        collect_layout.addRow(self.save_db_checkbox)
        
        collect_group.setLayout(collect_layout)
        scroll_layout.addWidget(collect_group)
        
        # 连接/断开按钮
        self.connect_button = QPushButton("连接设备")
        self.connect_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.connect_button.clicked.connect(self.toggle_connection)
        scroll_layout.addWidget(self.connect_button)
        
        # 开始/停止采集按钮
        self.collect_button = QPushButton("开始采集")
        self.collect_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.collect_button.setEnabled(False)
        self.collect_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.collect_button.clicked.connect(self.toggle_collection)
        scroll_layout.addWidget(self.collect_button)
        

        
        # 状态显示
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("QLabel { padding: 10px; background-color: #f0f0f0; border-radius: 5px; }")
        scroll_layout.addWidget(self.status_label)
        
        # 当前值显示
        self.value_label = QLabel("当前值: --")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("QLabel { padding: 10px; background-color: #e3f2fd; border-radius: 5px; font-size: 14px; font-weight: bold; }")
        scroll_layout.addWidget(self.value_label)
        
        scroll_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        return main_widget
    
    def create_realtime_plot_panel(self):
        plot_frame = QFrame()
        plot_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        plot_layout = QVBoxLayout(plot_frame)

        self.realtime_figure = Figure(figsize=(10, 8))
        self.realtime_canvas = FigureCanvas(self.realtime_figure)
        self.realtime_ax = self.realtime_figure.add_subplot(111)
        # 调整顶部边距，为实时数据显示文本留出空间
        self.realtime_figure.subplots_adjust(top=0.85)
        self.realtime_line, = self.realtime_ax.plot([], [], 'b-', linewidth=2, label='通道1')

        # 初始化图表
        self.realtime_ax.set_xlabel('时间')
        self.realtime_ax.set_ylabel('数值')
        self.realtime_ax.set_title('实时数据曲线')
        self.realtime_ax.grid(True)
        self.realtime_ax.legend()

        # 添加导航工具栏(支持拖动、缩放等功能)
        self.realtime_toolbar = NavigationToolbar(self.realtime_canvas, self)
        plot_layout.addWidget(self.realtime_toolbar)
        plot_layout.addWidget(self.realtime_canvas)

        # 添加鼠标移动事件处理
        self.realtime_canvas.mpl_connect('motion_notify_event', self.on_realtime_plot_hover)
        # 添加右键点击事件处理
        self.realtime_canvas.mpl_connect('button_press_event', self.on_realtime_right_click)


        return plot_frame
    
    def refresh_register_configs(self):
        """刷新寄存器配置列表"""
        self.reg_config_list.clear()
        for config in self.register_configs:
            item_text = f"{config['name']} - ID:{config['slave_id']} Addr:{config['address']} F:{config['function_code']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.reg_config_list.addItem(item)
    
    def add_register_config(self):
        """添加寄存器配置"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加寄存器配置")
        layout = QFormLayout()
        
        name_input = QLineEdit()
        slave_id_input = QLineEdit("1")
        addr_input = QLineEdit("0")
        count_input = QLineEdit("1")
        func_code_input = QComboBox()
        func_code_input.addItems(["3", "4", "1", "2"])
        unit_input = QLineEdit()
        scale_input = QLineEdit("1.0")
        offset_input = QLineEdit("0.0")
        color_input = QComboBox()
        color_input.addItems(self.channel_colors)
        color_input.setCurrentText("蓝色")
        
        layout.addRow("配置名称:", name_input)
        layout.addRow("从站ID:", slave_id_input)
        layout.addRow("起始地址:", addr_input)
        layout.addRow("寄存器数量:", count_input)
        layout.addRow("功能码:", func_code_input)
        layout.addRow("单位:", unit_input)
        layout.addRow("曲线颜色:", color_input)
        
        # 添加转化参数组
        transform_group = QGroupBox("数值转化 (原始值 × 比例 + 偏移量)")
        transform_layout = QFormLayout()
        transform_layout.addRow("比例:", scale_input)
        transform_layout.addRow("偏移量:", offset_input)
        transform_group.setLayout(transform_layout)
        layout.addRow(transform_group)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                name = name_input.text().strip()
                slave_id = int(slave_id_input.text())
                addr = int(addr_input.text())
                count = int(count_input.text())
                func_code = int(func_code_input.currentText())
                unit = unit_input.text().strip()
                scale = float(scale_input.text()) if scale_input.text().strip() else 1.0
                offset = float(offset_input.text()) if offset_input.text().strip() else 0.0
                color = color_input.currentText()
                
                if name:
                    conn = sqlite3.connect(self.db_file, timeout=10.0)
                    cursor = conn.cursor()
                    try:
                        # 首先检查表结构，确保所需列存在
                        cursor.execute("PRAGMA table_info(register_configs)")
                        columns = cursor.fetchall()
                        column_names = [col[1] for col in columns]
                        
                        # 如果缺少scale列，添加它
                        if 'scale' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN scale REAL DEFAULT 1.0")
                            print("已添加 scale 列")
                        
                        # 如果缺少offset列，添加它
                        if 'offset' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN offset REAL DEFAULT 0.0")
                            print("已添加 offset 列")
                        
                        # 如果缺少color列，添加它
                        if 'color' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN color TEXT DEFAULT '蓝色'")
                            print("已添加 color 列")
                        
                        # 现在执行插入
                        cursor.execute('''
                            INSERT INTO register_configs (name, slave_id, address, count, function_code, unit, scale, offset, color)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (name, slave_id, addr, count, func_code, unit, scale, offset, color))
                        conn.commit()
                    finally:
                        conn.close()
                    
                    self.load_register_configs()
                    self.refresh_register_configs()
                    
                    QMessageBox.information(self, "成功", "寄存器配置添加成功!")
                else:
                    QMessageBox.warning(self, "错误", "请输入配置名称!")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"添加失败: {str(e)}")

    def edit_register_config(self):
        """修改寄存器配置"""
        current_item = self.reg_config_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个要修改的配置")
            return

        old_config = current_item.data(Qt.ItemDataRole.UserRole)
        old_name = old_config['name']

        dialog = QDialog(self)
        dialog.setWindowTitle("修改寄存器配置")
        layout = QFormLayout()

        name_input = QLineEdit(old_name)
        slave_id_input = QLineEdit(str(old_config['slave_id']))
        addr_input = QLineEdit(str(old_config['address']))
        count_input = QLineEdit(str(old_config['count']))
        func_code_input = QComboBox()
        func_code_input.addItems(["3", "4", "1", "2"])
        func_code_input.setCurrentText(str(old_config['function_code']))
        unit_input = QLineEdit(old_config.get('unit', ''))
        scale_input = QLineEdit(str(old_config.get('scale', 1.0)))
        offset_input = QLineEdit(str(old_config.get('offset', 0.0)))
        color_input = QComboBox()
        color_input.addItems(self.channel_colors)
        # 设置当前颜色，如果没有则默认为蓝色
        current_color = old_config.get('color', '蓝色')
        if current_color in self.channel_colors:
            color_input.setCurrentText(current_color)
        else:
            color_input.setCurrentText("蓝色")

        layout.addRow("配置名称:", name_input)
        layout.addRow("从站ID:", slave_id_input)
        layout.addRow("起始地址:", addr_input)
        layout.addRow("寄存器数量:", count_input)
        layout.addRow("功能码:", func_code_input)
        layout.addRow("单位:", unit_input)
        layout.addRow("曲线颜色:", color_input)
        
        # 添加转化参数组
        transform_group = QGroupBox("数值转化 (原始值 × 比例 + 偏移量)")
        transform_layout = QFormLayout()
        transform_layout.addRow("比例:", scale_input)
        transform_layout.addRow("偏移量:", offset_input)
        transform_group.setLayout(transform_layout)
        layout.addRow(transform_group)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new_name = name_input.text().strip()
                slave_id = int(slave_id_input.text())
                addr = int(addr_input.text())
                count = int(count_input.text())
                func_code = int(func_code_input.currentText())
                unit = unit_input.text().strip()
                scale = float(scale_input.text()) if scale_input.text().strip() else 1.0
                offset = float(offset_input.text()) if offset_input.text().strip() else 0.0
                color = color_input.currentText()

                if new_name:
                    conn = sqlite3.connect(self.db_file, timeout=10.0)
                    cursor = conn.cursor()
                    try:
                        # 首先检查表结构，确保所需列存在
                        cursor.execute("PRAGMA table_info(register_configs)")
                        columns = cursor.fetchall()
                        column_names = [col[1] for col in columns]

                        # 如果缺少scale列，添加它
                        if 'scale' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN scale REAL DEFAULT 1.0")
                            print("已添加 scale 列")

                        # 如果缺少offset列，添加它
                        if 'offset' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN offset REAL DEFAULT 0.0")
                            print("已添加 offset 列")

                        # 如果缺少color列，添加它
                        if 'color' not in column_names:
                            cursor.execute("ALTER TABLE register_configs ADD COLUMN color TEXT DEFAULT '蓝色'")
                            print("已添加 color 列")

                        # 如果名称改变了,先检查新名称是否已存在
                        if new_name != old_name:
                            cursor.execute("SELECT COUNT(*) FROM register_configs WHERE name = ?", (new_name,))
                            if cursor.fetchone()[0] > 0:
                                QMessageBox.warning(self, "错误", f"配置名称 '{new_name}' 已存在!")
                                return

                        # 更新配置
                        cursor.execute('''
                            UPDATE register_configs
                            SET name = ?, slave_id = ?, address = ?, count = ?, function_code = ?, unit = ?, scale = ?, offset = ?, color = ?
                            WHERE name = ?
                        ''', (new_name, slave_id, addr, count, func_code, unit, scale, offset, color, old_name))
                        conn.commit()
                    finally:
                        conn.close()

                    # 更新正在运行的数据通道颜色
                    if hasattr(self, 'data_channels'):
                        # 如果名称未改变，直接更新颜色
                        if new_name == old_name:
                            if old_name in self.data_channels:
                                self.data_channels[old_name]['color'] = color
                        else:
                            # 名称改变，需要重命名通道
                            if old_name in self.data_channels:
                                self.data_channels[new_name] = self.data_channels.pop(old_name)
                                self.data_channels[new_name]['color'] = color

                    # 更新channel_configs中的配置
                    for config in self.channel_configs:
                        if config['name'] == old_name:
                            config['name'] = new_name
                            config['color'] = color
                            break

                    self.load_register_configs()
                    self.refresh_register_configs()

                    # 如果正在采集数据,立即刷新实时曲线以显示新颜色
                    if self.is_collecting and hasattr(self, 'realtime_canvas'):
                        self.update_realtime_plot()

                    QMessageBox.information(self, "成功", "寄存器配置修改成功!")
                else:
                    QMessageBox.warning(self, "错误", "请输入配置名称!")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"修改失败: {str(e)}")

    def delete_register_config(self):
        """删除寄存器配置"""
        current_item = self.reg_config_list.currentItem()
        if not current_item:
            return
        
        config = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = self.positioned_question("确认删除", f"确定要删除配置 '{config['name']}' 吗?")
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_file, timeout=10.0)
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM register_configs WHERE name = ?", (config['name'],))
                    conn.commit()
                finally:
                    conn.close()
                
                self.load_register_configs()
                self.refresh_register_configs()
                
                QMessageBox.information(self, "成功", "寄存器配置删除成功!")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {str(e)}")
    
    def add_config_to_channel(self):
        """将选中的寄存器配置添加到通道列表"""
        current_item = self.reg_config_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个配置")
            return

        config = current_item.data(Qt.ItemDataRole.UserRole)

        # 检查是否已存在同名通道
        if config['name'] in self.data_channels:
            QMessageBox.warning(self, "错误", f"通道 '{config['name']}' 已存在")
            return

        self.channel_configs.append(config)

        # 更新通道列表显示
        item = QListWidgetItem(f"{config['name']} - ID:{config['slave_id']} Addr:{config['address']}")
        item.setData(Qt.ItemDataRole.UserRole, config)
        self.channel_list.addItem(item)

        # 为新通道初始化数据缓冲区
        # 使用配置中指定的颜色，如果没有则按顺序分配
        channel_color = config.get('color', '蓝色')
        
        self.data_channels[config['name']] = {
            'buffer': deque(maxlen=1000),
            'time': deque(maxlen=1000),
            'line': None,
            'color': channel_color,
            'config': config
        }

        # 更新通道计数
        self.update_channel_count()




    def update_channel_count(self):
        """更新通道计数显示"""
        self.channel_count_label.setText(f"活动通道数: {len(self.channel_configs)}")

    def export_channel_configs(self):
        """导出通道配置到JSON文件"""
        try:
            # 获取所有已保存的配置
            self.load_register_configs()

            if not self.register_configs:
                QMessageBox.warning(self, "提示", "没有可导出的配置")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出通道配置", "", "JSON文件 (*.json);;所有文件 (*)"
            )

            if file_path:
                # 确保文件扩展名为.json
                if not file_path.lower().endswith('.json'):
                    file_path += '.json'

                # 导出到JSON文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.register_configs, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "导出成功", f"已导出 {len(self.register_configs)} 个配置到:\n{file_path}")

        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出配置失败:\n{str(e)}")

    def import_channel_configs(self):
        """从JSON文件导入通道配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入通道配置", "", "JSON文件 (*.json);;所有文件 (*)"
            )

            if file_path:
                # 从JSON文件读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_configs = json.load(f)

                if not isinstance(imported_configs, list):
                    QMessageBox.warning(self, "错误", "配置文件格式错误")
                    return

                if not imported_configs:
                    QMessageBox.warning(self, "提示", "配置文件为空")
                    return

                # 保存到数据库
                conn = sqlite3.connect(self.db_file, timeout=10.0)
                cursor = conn.cursor()

                try:
                    # 检查并创建表
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS register_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            slave_id INTEGER,
                            address INTEGER,
                            count INTEGER,
                            function_code INTEGER,
                            unit TEXT,
                            scale REAL DEFAULT 1.0,
                            offset REAL DEFAULT 0.0
                        )
                    ''')

                    success_count = 0
                    error_count = 0

                    for config in imported_configs:
                        try:
                            cursor.execute('''
                                INSERT OR REPLACE INTO register_configs
                                (name, slave_id, address, count, function_code, unit, scale, offset)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                config.get('name', ''),
                                config.get('slave_id', 1),
                                config.get('address', 0),
                                config.get('count', 1),
                                config.get('function_code', 3),
                                config.get('unit', ''),
                                config.get('scale', 1.0),
                                config.get('offset', 0.0)
                            ))
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f"导入配置失败: {config.get('name', '未知')}, 错误: {str(e)}")

                    conn.commit()

                    # 重新加载配置
                    self.load_register_configs()
                    self.refresh_register_configs()

                    if error_count == 0:
                        QMessageBox.information(self, "导入成功", f"成功导入 {success_count} 个配置!")
                    else:
                        QMessageBox.information(self, "导入完成", f"成功导入 {success_count} 个配置，失败 {error_count} 个")

                finally:
                    conn.close()

        except FileNotFoundError:
            QMessageBox.warning(self, "错误", "文件不存在")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "错误", "JSON文件格式错误")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"导入配置失败:\n{str(e)}")

    def toggle_db_save(self, state):
        """切换数据库保存"""
        self.save_to_db = (state == Qt.CheckState.Checked.value)
        
        if self.save_to_db:
            self.storage_interval_input.setEnabled(True)
        else:
            self.storage_interval_input.setEnabled(False)
            self.storage_timer.stop()
    
    def on_conn_type_changed(self, conn_type):
        """连接类型改变时更新界面"""
        if conn_type == "TCP":
            self.tcp_group.setVisible(True)
            self.rtu_group.setVisible(False)
        else:
            self.tcp_group.setVisible(False)
            self.rtu_group.setVisible(True)
            # 切换到RTU时自动搜索串口
            self.search_serial_ports()
    
    def search_serial_ports(self):
        """搜索可用的串口"""
        try:
            import serial.tools.list_ports
            
            # 清空当前列表
            self.rtu_port_input.clear()
            
            # 获取所有可用串口
            ports = serial.tools.list_ports.comports()
            
            if ports:
                for port in ports:
                    # 添加串口信息
                    display_text = f"{port.device}"
                    if port.description:
                        display_text += f" - {port.description}"
                    self.rtu_port_input.addItem(display_text, port.device)
                
                # 默认选中第一个
                if self.rtu_port_input.count() > 0:
                    self.rtu_port_input.setCurrentIndex(0)
                
                QMessageBox.information(self, "搜索结果", f"找到 {len(ports)} 个可用串口")
            else:
                self.rtu_port_input.addItem("COM1")
                QMessageBox.warning(self, "搜索结果", "未找到可用串口")
                
        except ImportError:
            QMessageBox.warning(self, "错误", "pyserial未安装，无法搜索串口")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"搜索串口失败: {str(e)}")
    
    def delete_channel(self):
        """删除数据通道"""
        current_item = self.channel_list.currentItem()
        if not current_item:
            return

        config = current_item.data(Qt.ItemDataRole.UserRole)
        name = config['name']

        reply = self.positioned_question("确认删除", f"确定要删除通道 '{name}' 吗?")

        if reply == QMessageBox.StandardButton.Yes:
            # 从列表中移除
            self.channel_list.takeItem(self.channel_list.row(current_item))

            # 从配置中移除
            self.channel_configs = [c for c in self.channel_configs if c['name'] != name]

            # 从数据通道中移除
            if name in self.data_channels:
                # 移除对应的线条
                if self.data_channels[name]['line'] and self.data_channels[name]['line'] in self.realtime_ax.lines:
                    self.data_channels[name]['line'].remove()
                del self.data_channels[name]

            # 更新通道计数
            self.update_channel_count()

            QMessageBox.information(self, "成功", f"通道 '{name}' 删除成功!")

    def clear_all_channels(self):
        """清空所有通道"""
        if not self.channel_configs:
            QMessageBox.information(self, "提示", "当前没有活动通道")
            return

        reply = self.positioned_question("确认清空", "确定要清空所有通道吗?")

        if reply == QMessageBox.StandardButton.Yes:
            # 清空列表
            self.channel_list.clear()

            # 移除所有线条
            for name, channel in self.data_channels.items():
                if channel['line'] and channel['line'] in self.realtime_ax.lines:
                    channel['line'].remove()

            # 清空配置和数据
            self.channel_configs.clear()
            self.data_channels.clear()

            # 更新通道计数
            self.update_channel_count()

            QMessageBox.information(self, "成功", "所有通道已清空!")
    
    def toggle_connection(self):
        """连接/断开Modbus设备"""
        if self.is_connected:
            self.disconnect_modbus()
        else:
            self.connect_modbus()
    
    def connect_modbus(self):
        """连接Modbus设备"""
        try:
            conn_type = self.conn_type_combo.currentText()
            
            if conn_type == "TCP":
                host = self.tcp_host_input.text().strip()
                port = int(self.tcp_port_input.text())
                self.modbus_client = ModbusTcpClient(host, port=port)
            else:
                port = self.rtu_port_input.currentData() or self.rtu_port_input.currentText().strip()
                baudrate = int(self.rtu_baudrate_input.currentText())
                bytesize = int(self.rtu_databits_input.currentText())
                stopbits = int(self.rtu_stopbits_input.currentText())
                parity = self.rtu_parity_input.currentText()
                
                self.modbus_client = ModbusSerialClient(
                    port=port,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    stopbits=stopbits,
                    parity=parity,
                    timeout=1
                )
            
            if self.modbus_client.connect():
                self.is_connected = True
                self.connect_button.setText("断开设备")
                self.connect_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                        border: none;
                        padding: 10px;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #da190b;
                    }
                """)
                self.collect_button.setEnabled(True)
                self.status_label.setText(f"状态: 已连接 ({conn_type})")
                self.status_label.setStyleSheet("QLabel { padding: 10px; background-color: #c8e6c9; border-radius: 5px; }")
            else:
                QMessageBox.warning(self, "连接失败", "无法连接到Modbus设备，请检查参数")
                
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接失败: {str(e)}")
    
    def disconnect_modbus(self):
        """断开Modbus连接"""
        if self.is_collecting:
            self.toggle_collection()
        
        self.storage_timer.stop()
        
        if self.modbus_client:
            self.modbus_client.close()
            self.modbus_client = None
        
        self.is_connected = False
        self.connect_button.setText("连接设备")
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.collect_button.setEnabled(False)
        self.status_label.setText("状态: 未连接")
        self.status_label.setStyleSheet("QLabel { padding: 10px; background-color: #f0f0f0; border-radius: 5px; }")
    
    def toggle_collection(self):
        """开始/停止数据采集"""
        if self.is_collecting:
            self.stop_collection()
        else:
            self.start_collection()
    
    def start_collection(self):
        """开始数据采集"""
        try:
            self.data_buffer.clear()
            self.time_buffer.clear()
            
            interval = self.sample_interval.value()
            self.collect_timer.start(interval)
            
            # 启动数据库存储定时器
            if self.save_to_db:
                storage_interval_sec = self.storage_interval_input.value() * 1000
                self.storage_timer.start(storage_interval_sec)
            
            self.is_collecting = True
            self.collect_button.setText("停止采集")
            self.collect_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            self.status_label.setText("状态: 正在采集数据...")
            self.status_label.setStyleSheet("QLabel { padding: 10px; background-color: #fff3e0; border-radius: 5px; }")
            
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动采集: {str(e)}")
    
    def stop_collection(self):
        """停止数据采集"""
        self.collect_timer.stop()
        self.storage_timer.stop()
        self.is_collecting = False
        self.collect_button.setText("开始采集")
        self.collect_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self.status_label.setText("状态: 已停止采集")
        self.status_label.setStyleSheet("QLabel { padding: 10px; background-color: #e1f5fe; border-radius: 5px; }")
        
        # 保存最后一次数据
        if self.save_to_db:
            self.save_to_database()
    
    def collect_data(self):
        """采集Modbus数据"""
        try:
            current_time = datetime.now()
            
            # 如果有配置的通道，采集多通道数据
            if self.channel_configs:
                for config in self.channel_configs:
                    name = config['name']
                    
                    try:
                        func_code = config['function_code']
                        
                        if func_code == 3:
                            result = self.modbus_client.read_holding_registers(
                                config['address'], config['count'], slave=config['slave_id'])
                        elif func_code == 4:
                            result = self.modbus_client.read_input_registers(
                                config['address'], config['count'], slave=config['slave_id'])
                        elif func_code == 1:
                            result = self.modbus_client.read_coils(
                                config['address'], config['count'], slave=config['slave_id'])
                        else:
                            result = self.modbus_client.read_discrete_inputs(
                                config['address'], config['count'], slave=config['slave_id'])
                        
                        if result.isError():
                            continue
                        
                        if hasattr(result, 'registers'):
                            values = result.registers
                        elif hasattr(result, 'bits'):
                            values = [int(bit) for bit in result.bits[:config['count']]]
                        else:
                            values = [result.value] if hasattr(result, 'value') else [0]
                        
                        if len(values) >= 1:
                            raw_value = values[0]
                            
                            # 应用比例和偏移量转化
                            scale = config.get('scale', 1.0)
                            offset = config.get('offset', 0.0)
                            value = raw_value * scale + offset

                            # 保存到通道数据缓冲区
                            if name in self.data_channels:
                                self.data_channels[name]['buffer'].append(value)
                                self.data_channels[name]['time'].append(current_time)
                    except Exception as e:
                        # 单个通道采集失败，继续采集其他通道
                        continue

                # 更新显示
                if self.data_channels:
                    self.value_label.setText(f"活动通道数: {len(self.data_channels)}")

                self.update_realtime_plot()
            else:
                # 没有配置通道,提示用户
                QMessageBox.warning(self, "提示", "请先在\"通道配置管理\"中添加通道!")
                self.stop_collection()
        except ModbusException as e:
            QMessageBox.warning(self, "Modbus错误", f"读取数据失败: {str(e)}")
            self.stop_collection()
        except Exception as e:
            QMessageBox.critical(self, "采集错误", f"采集数据时发生错误: {str(e)}")
            self.stop_collection()
    
    def update_realtime_plot(self):
        """更新实时曲线"""
        import matplotlib.dates as mdates

        # 如果有多通道配置，显示多曲线
        if self.data_channels:
            # 清除所有现有线条和标注（跳过实时数据显示文本）
            for line in self.realtime_ax.lines:
                line.remove()
            texts_to_remove = []
            for text in self.realtime_ax.texts:
                # 跳过实时数据显示文本
                if not hasattr(text, '_realtime_data_text'):
                    texts_to_remove.append(text)
            for text in texts_to_remove:
                text.remove()

            # 获取设置的时间范围
            time_range_seconds = self.display_time_range.value()

            # 为每个通道创建或更新曲线
            # 计算实时数据显示的位置
            num_channels = len(self.data_channels)
            start_y = 0.95  # 轴域坐标顶部
            step_y = -0.05  # 向下步长
            y_pos = start_y
            
            # 获取实时曲线样式设置（统一使用用户设置的持久化样式）
            settings = self.realtime_style_settings
            line_width = settings.get('line_width', 1.5)
            line_style_index = settings.get('line_style', 0)
            alpha = settings.get('alpha', 0.8)
            show_marker = settings.get('show_marker', True)
            marker_style = settings.get('marker_style', 'o')
            
            # 颜色映射 - 将中文颜色名称转换为matplotlib颜色代码
            color_map = {
                '蓝色': 'blue', '红色': 'red', '绿色': 'green', '橙色': 'orange',
                '紫色': 'purple', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
                '橄榄色': 'olive', '青色': 'cyan', '黑色': 'black',
                '深蓝色': 'navy', '深红色': 'darkred', '深绿色': 'darkgreen',
                '金色': 'gold', '银色': 'silver'
            }
            
            # 线条样式映射
            line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
            line_style = line_styles[line_style_index]
            
            # 设置marker
            marker = marker_style if show_marker else None
            markersize = 5 if show_marker else None


            for idx, (name, channel) in enumerate(self.data_channels.items()):
                buffer = channel['buffer']
                time_buffer = channel['time']
                
                # 获取通道配置中的颜色
                channel_color_name = None
                
                # 优先使用通道字典中保存的颜色
                if 'color' in channel:
                    channel_color_name = channel['color']
                else:
                    # 如果通道字典中没有颜色，从channel_configs中查找对应的配置
                    for config in self.channel_configs:
                        if config['name'] == name:
                            channel_color_name = config.get('color', '蓝色')
                            # 保存到通道字典中
                            channel['color'] = channel_color_name
                            break
                    
                    # 如果还没找到，按顺序自动分配颜色
                    if channel_color_name is None:
                        if idx < len(self.channel_colors):
                            channel_color_name = self.channel_colors[idx]
                        else:
                            channel_color_name = self.channel_colors[idx % len(self.channel_colors)]
                        # 保存到通道字典中
                        channel['color'] = channel_color_name
                
                line_color = color_map.get(channel_color_name, 'blue')

                if len(buffer) > 0:
                    # 只显示最近时间范围内的数据
                    if len(time_buffer) > 0:
                        current_time = time_buffer[-1]
                        min_display_time = current_time - timedelta(seconds=time_range_seconds)


                        # 筛选在显示范围内的数据点
                        filtered_indices = [i for i, t in enumerate(time_buffer) if t >= min_display_time]
                        if filtered_indices:
                            x_data = [time_buffer[i] for i in filtered_indices]
                            y_data = [buffer[i] for i in filtered_indices]
                        else:
                            x_data = list(time_buffer)
                            y_data = list(buffer)
                    else:
                        x_data = list(time_buffer)
                        y_data = list(buffer)

                    # 创建线条 - 使用通道自己的颜色和其他样式参数
                    line, = self.realtime_ax.plot(x_data, y_data, color=line_color, linewidth=line_width,
                                                 linestyle=line_style, label=name, alpha=alpha, marker=marker, markersize=markersize)
                    channel['line'] = line
                    # 保存数据用于tooltip
                    channel['display_x'] = x_data
                    channel['display_y'] = y_data
                    
                    # 创建或更新实时数据显示文本
                    current_y = start_y + idx * step_y
                    latest_value = buffer[-1] if len(buffer) > 0 else None
                    latest_time = time_buffer[-1] if len(time_buffer) > 0 else None
                    
                    if latest_value is not None:
                        time_str = latest_time.strftime('%H:%M:%S') if latest_time else 'N/A'
                        text_content = f'{name}: {latest_value:.2f} ({time_str})'
                        
                        if 'data_text' in channel:
                            # 更新现有文本
                            text_obj = channel['data_text']
                            text_obj.set_text(text_content)
                            text_obj.set_position((0.02, current_y))
                            text_obj.set_color(line_color)
                        else:
                            # 创建新文本
                            text_obj = self.realtime_ax.text(0.02, current_y, text_content,
                                                           transform=self.realtime_ax.transAxes,
                                                           fontsize=10, color=line_color,
                                                           verticalalignment='top',
                                                           horizontalalignment='left')
                            text_obj._realtime_data_text = True  # 标记为实时数据显示文本
                            channel['data_text'] = text_obj

            # 调整坐标轴
            all_x = []
            all_y = []
            for channel in self.data_channels.values():
                if 'display_x' in channel:
                    all_x.extend(channel['display_x'])
                    all_y.extend(channel['display_y'])

            if all_x and all_y:
                # 自动格式化x轴为日期时间格式
                self.realtime_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M:%S'))
                self.realtime_ax.xaxis.set_major_locator(mdates.AutoDateLocator())

                # 设置X轴范围为固定时间跨度
                current_time = max(all_x)
                min_display_time = current_time - timedelta(seconds=time_range_seconds)
                self.realtime_ax.set_xlim(min_display_time, current_time + timedelta(seconds=time_range_seconds * 0.1))

                min_y, max_y = min(all_y), max(all_y)
                y_range = max_y - min_y if max_y != min_y else 1
                self.realtime_ax.set_ylim(min_y - y_range * 0.1, max_y + y_range * 0.1)

            # 根据实时曲线样式设置网格和图例
            settings = self.realtime_style_settings
            show_grid = settings.get('show_grid', True)
            show_legend = settings.get('show_legend', True)
            self.realtime_ax.grid(show_grid)

            if show_legend:
                # 为多通道模式创建图例,确保图例颜色与通道配置一致
                if self.realtime_ax.get_legend():
                    self.realtime_ax.get_legend().remove()
                self.realtime_ax.legend()
            else:
                legend = self.realtime_ax.get_legend()
                if legend:
                    legend.remove()

        else:
            # 单通道模式（兼容旧版本）
            # 重新创建line对象（如果已被清除）
            if not self.realtime_ax.lines:
                # 获取实时曲线样式设置
                settings = self.realtime_style_settings
                line_width = settings.get('line_width', 2.0)
                line_style_index = settings.get('line_style', 0)
                alpha = settings.get('alpha', 1.0)
                show_marker = settings.get('show_marker', True)
                marker_style = settings.get('marker_style', 'o')
                
                # 颜色映射 - 将中文颜色名称转换为matplotlib颜色代码
                color_map = {
                    '蓝色': 'blue', '红色': 'red', '绿色': 'green', '橙色': 'orange',
                    '紫色': 'purple', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
                    '橄榄色': 'olive', '青色': 'cyan', '黑色': 'black',
                    '深蓝色': 'navy', '深红色': 'darkred', '深绿色': 'darkgreen',
                    '金色': 'gold', '银色': 'silver'
                }
                line_color = color_map.get(settings.get('line_color', '蓝色'), 'blue')

                # 线条样式映射
                line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
                line_style = line_styles[line_style_index]

                marker = marker_style if show_marker else None
                markersize = 5 if show_marker else None
                self.realtime_line, = self.realtime_ax.plot([], [], color=line_color, linewidth=line_width,
                                                           linestyle=line_style, label='实时数据', alpha=alpha, marker=marker, markersize=markersize)
                self.realtime_ax.legend()

            if len(self.data_buffer) < 1:
                return

            # 直接使用datetime对象作为x轴
            x_data = list(self.time_buffer)
            y_data = list(self.data_buffer)

            self.realtime_line.set_data(x_data, y_data)
            
            # 更新实时数据显示文本
            if len(y_data) > 0:
                latest_value = y_data[-1]
                latest_time = x_data[-1] if len(x_data) > 0 else None
                time_str = latest_time.strftime('%H:%M:%S') if latest_time else 'N/A'
                text_content = f'实时数据: {latest_value:.2f} ({time_str})'
                
                if hasattr(self, 'realtime_data_text'):
                    # 更新现有文本
                    self.realtime_data_text.set_text(text_content)
                    self.realtime_data_text.set_position((0.02, 0.95))
                else:
                    # 创建新文本
                    self.realtime_data_text = self.realtime_ax.text(0.02, 0.95, text_content,
                                                                   transform=self.realtime_ax.transAxes,
                                                                   fontsize=10, color='blue',
                                                                   verticalalignment='top',
                                                                   horizontalalignment='left')
                    self.realtime_data_text._realtime_data_text = True

            # 自动格式化x轴为日期时间格式
            self.realtime_ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M:%S'))
            self.realtime_ax.xaxis.set_major_locator(mdates.AutoDateLocator())

            # 设置X轴范围为固定时间跨度
            time_range_seconds = self.display_time_range.value()
            if len(x_data) > 0:
                current_time = x_data[-1]
                min_display_time = current_time - timedelta(seconds=time_range_seconds)
                self.realtime_ax.set_xlim(min_display_time, current_time + timedelta(seconds=time_range_seconds * 0.1))
            else:
                self.realtime_ax.set_xlim(datetime.now() - timedelta(seconds=time_range_seconds),
                                      datetime.now() + timedelta(seconds=time_range_seconds))



            min_y, max_y = min(y_data), max(y_data)
            y_range = max_y - min_y if max_y != min_y else 1
            self.realtime_ax.set_ylim(min_y - y_range * 0.1, max_y + y_range * 0.1)

            # 根据实时曲线样式设置线条属性（单通道模式）
            settings = self.realtime_style_settings
            line_width = settings.get('line_width', 2.0)
            line_style_index = settings.get('line_style', 0)
            alpha = settings.get('alpha', 1.0)
            show_marker = settings.get('show_marker', True)
            marker_style = settings.get('marker_style', 'o')

            # 颜色映射
            color_map = {
                '蓝色': 'blue', '红色': 'red', '绿色': 'green', '橙色': 'orange',
                '紫色': 'purple', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
                '橄榄色': 'olive', '青色': 'cyan', '黑色': 'black',
                '深蓝色': 'navy', '深红色': 'darkred', '深绿色': 'darkgreen',
                '金色': 'gold', '银色': 'silver'
            }
            line_color = color_map.get(settings.get('line_color', '蓝色'), 'blue')

            line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
            line_style = line_styles[line_style_index]

            self.realtime_line.set_linewidth(line_width)
            self.realtime_line.set_linestyle(line_style)
            self.realtime_line.set_alpha(alpha)
            self.realtime_line.set_color(line_color)
            if show_marker:
                self.realtime_line.set_marker(marker_style)
                self.realtime_line.set_markersize(5)
            else:
                self.realtime_line.set_marker(None)

        self.realtime_ax.set_xlabel('时间')
        self.realtime_ax.set_ylabel('数值')
        self.realtime_ax.set_title('实时数据曲线')

        # 根据实时曲线样式设置网格和图例
        settings = self.realtime_style_settings
        show_grid = settings.get('show_grid', True)
        show_legend = settings.get('show_legend', True)
        self.realtime_ax.grid(show_grid)
        
        if show_legend:
            if not self.realtime_ax.get_legend():
                self.realtime_ax.legend()
        else:
            legend = self.realtime_ax.get_legend()
            if legend:
                legend.remove()

        self.realtime_canvas.draw()

    def on_realtime_plot_hover(self, event):
        """鼠标在实时曲线上悬停时显示数据"""
        if event.inaxes != self.realtime_ax or event.xdata is None or event.ydata is None:
            return

        import math
        import matplotlib.dates as mdates

        # 清除旧的标注（保留图例和实时数据显示文本）
        texts_to_remove = []
        for text in self.realtime_ax.texts:
            # 跳过图例文字和实时数据显示文本
            if not hasattr(text, '_legend_text') and not hasattr(text, '_realtime_data_text'):
                texts_to_remove.append(text)
        for text in texts_to_remove:
            text.remove()

        # 将event.xdata从matplotlib日期格式转换为datetime
        try:
            if isinstance(event.xdata, (int, float)):
                event_x_time = mdates.num2date(event.xdata)
                # 如果返回的是带时区的datetime，需要转换为无时区的
                if hasattr(event_x_time, 'tzinfo') and event_x_time.tzinfo is not None:
                    event_x_time = event_x_time.replace(tzinfo=None)
            else:
                event_x_time = event.xdata
        except:
            return

        if self.data_channels:
            # 多通道模式
            min_time_diff = float('inf')
            closest_point = None
            closest_channel = None

            for name, channel in self.data_channels.items():
                if 'display_x' not in channel or not channel['display_x']:
                    continue

                x_data = channel['display_x']
                y_data = channel['display_y']

                for i in range(len(x_data)):
                    x_time = x_data[i]
                    y_point = y_data[i]

                    # 计算时间差（秒）
                    time_diff = abs((event_x_time - x_time).total_seconds())
                    value_diff = abs(event.ydata - y_point)

                    # 使用简单的距离计算（归一化）
                    dist = math.sqrt(time_diff**2 + value_diff**2)

                    if dist < min_time_diff:
                        min_time_diff = dist
                        closest_point = (x_time, y_point)
                        closest_channel = name

            # 如果找到足够近的点，显示tooltip
            if closest_point and min_time_diff < 5:  # 距离阈值（5秒或数值单位）
                x_time, y_value = closest_point
                time_str = x_time.strftime('%m-%d %H:%M:%S')

                # 在鼠标位置右侧显示标注，跟随鼠标移动
                annotation = self.realtime_ax.annotate(
                    f'{closest_channel}\n时间: {time_str}\n数值: {y_value:.2f}',
                    xy=(event.xdata, event.ydata),
                    xytext=(20, 0),
                    textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.7', facecolor='wheat', alpha=0.95, edgecolor='darkorange', linewidth=1.5),
                    fontsize=10,
                    fontweight='normal',
                    ha='left',
                    va='center'
                )
                self.realtime_canvas.draw_idle()

        elif len(self.data_buffer) > 0:
            # 单通道模式
            x_data = list(self.time_buffer)
            y_data = list(self.data_buffer)

            min_time_diff = float('inf')
            closest_point = None

            for i in range(len(x_data)):
                x_time = x_data[i]
                y_point = y_data[i]

                # 计算时间差（秒）
                time_diff = abs((event_x_time - x_time).total_seconds())
                value_diff = abs(event.ydata - y_point)

                # 使用简单的距离计算（归一化）
                dist = math.sqrt(time_diff**2 + value_diff**2)

                if dist < min_time_diff:
                    min_time_diff = dist
                    closest_point = (x_time, y_point)

            # 如果找到足够近的点，显示tooltip
            if closest_point and min_time_diff < 5:  # 距离阈值（5秒或数值单位）
                x_time, y_value = closest_point
                time_str = x_time.strftime('%m-%d %H:%M:%S')

                # 在鼠标位置右侧显示标注，跟随鼠标移动
                annotation = self.realtime_ax.annotate(
                    f'实时数据\n时间: {time_str}\n数值: {y_value:.2f}',
                    xy=(event.xdata, event.ydata),
                    xytext=(20, 0),
                    textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.7', facecolor='wheat', alpha=0.95, edgecolor='darkorange', linewidth=1.5),
                    fontsize=10,
                    fontweight='normal',
                    ha='left',
                    va='center'
                )
                self.realtime_canvas.draw_idle()

    def apply_style_to_history(self):
        """应用样式设置到历史曲线"""
        try:
            if not hasattr(self, 'history_ax') or not self.history_ax:
                return

            # 获取历史曲线样式设置
            settings = self.history_style_settings
            
            line_width = settings['line_width']
            
            # 线条样式映射
            line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
            line_style = line_styles[settings['line_style']]
            
            alpha = settings['alpha']
            show_grid = settings['show_grid']
            show_legend = settings['show_legend']
            show_marker = settings.get('show_marker', True)
            marker_style = settings.get('marker_style', 'o')

            print(f"应用样式到历史曲线: 线宽={line_width}, 样式={line_style}, 透明度={alpha}, 网格={show_grid}, 图例={show_legend}, 标记={show_marker}, 标记样式={marker_style}")

            # 更新现有线条样式（保留通道的原始颜色）
            line_count = 0
            for line in self.history_ax.lines:
                # 保留原始颜色，只更新其他样式属性
                line.set_linewidth(line_width)
                line.set_linestyle(line_style)
                line.set_alpha(alpha)
                
                # 更新marker
                if show_marker:
                    line.set_marker(marker_style)
                    line.set_markersize(5)
                else:
                    line.set_marker(None)
                line_count += 1
            print(f"更新了 {line_count} 条线条的样式（保留通道颜色）")

            # 更新网格
            self.history_ax.grid(show_grid)

            # 更新图例
            if show_legend:
                if not self.history_ax.get_legend():
                    self.history_ax.legend()
            else:
                legend = self.history_ax.get_legend()
                if legend:
                    legend.remove()

            # 刷新历史曲线
            self.history_canvas.draw_idle()
            print("历史曲线已刷新")

        except Exception as e:
            print(f"应用样式到历史曲线时出错: {e}")
            import traceback
            traceback.print_exc()

    def on_rt_style_changed(self):
        """实时曲线样式控件改变时，只应用到实时曲线"""
        self.apply_style_to_realtime()

    def on_his_style_changed(self):
        """历史曲线样式控件改变时，只应用到历史曲线"""
        self.apply_style_to_history()

    def on_history_plot_hover(self, event):
        """鼠标在历史曲线上悬停时显示数据"""
        if event.inaxes != self.history_ax or event.xdata is None or event.ydata is None:
            return

        import math
        import matplotlib.dates as mdates

        # 清除旧的tooltip标注
        texts_to_remove = []
        for text in self.history_ax.texts:
            if hasattr(text, '_history_tooltip'):
                texts_to_remove.append(text)
        for text in texts_to_remove:
            text.remove()

        # 清除旧的annotation
        if hasattr(self, '_history_hover_annotation') and self._history_hover_annotation:
            try:
                self._history_hover_annotation.remove()
            except:
                pass
            self._history_hover_annotation = None

        # 将鼠标x坐标转换为datetime
        try:
            mouse_x = mdates.num2date(event.xdata)
            mouse_y = event.ydata
        except:
            return

        # 查找最近的数据点
        closest_point = None
        closest_channel = None
        min_distance = float('inf')

        # 遍历所有历史曲线数据
        for label, data in self.history_plot_data.items():
            x_data = data['x']
            y_data = data['y']

            if not x_data or not y_data:
                continue

            # 查找最近的时间点
            for i, (x_time, y_val) in enumerate(zip(x_data, y_data)):
                # 计算x轴距离（时间差，转换为秒）
                time_diff = abs((x_time - mouse_x.replace(tzinfo=None)).total_seconds())
                # 计算y轴距离
                y_diff = abs(y_val - mouse_y)

                # 综合距离（归一化）
                x_range = self.history_ax.get_xlim()
                y_range = self.history_ax.get_ylim()
                x_span = (mdates.num2date(x_range[1]) - mdates.num2date(x_range[0])).total_seconds()
                y_span = y_range[1] - y_range[0] if y_range[1] != y_range[0] else 1

                # 归一化距离
                norm_x_dist = time_diff / x_span if x_span > 0 else time_diff
                norm_y_dist = y_diff / y_span if y_span > 0 else y_diff
                distance = math.sqrt(norm_x_dist**2 + norm_y_dist**2)

                # 如果距离更近，更新最近点
                if distance < min_distance:
                    min_distance = distance
                    closest_point = (x_time, y_val)
                    closest_channel = label

        # 如果找到足够近的点，显示tooltip
        if closest_point and min_distance < 0.05:  # 距离阈值
            x_time, y_value = closest_point
            time_str = x_time.strftime('%m-%d %H:%M:%S')

            # 在鼠标位置右侧显示标注
            self._history_hover_annotation = self.history_ax.annotate(
                f'{closest_channel}\n时间: {time_str}\n数值: {y_value:.2f}',
                xy=(event.xdata, event.ydata),
                xytext=(20, 0),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.7', facecolor='lightyellow', alpha=0.95, edgecolor='orange', linewidth=1.5),
                fontsize=10,
                fontweight='normal',
                ha='left',
                va='center'
            )
            self._history_hover_annotation._history_tooltip = True

            self.history_canvas.draw_idle()

    def on_tab_changed(self, index):
        """标签页切换时自动应用样式"""
        # 获取当前标签页名称
        tab_name = self.tab_widget.tabText(index)

        # 切换到Modbus实时数据标签页时，应用样式
        if tab_name == "Modbus实时数据":
            try:
                self.apply_style_to_realtime()
            except Exception as e:
                print(f"应用样式到实时曲线时出错: {e}")

        # 切换到历史数据查询标签页时，应用样式
        elif tab_name == "历史数据查询":
            try:
                self.apply_style_to_history()
            except Exception as e:
                print(f"应用样式到历史曲线时出错: {e}")








    

    
    def create_history_tab(self):
        """创建历史数据查询标签页"""
        history_tab = QWidget()
        history_layout = QHBoxLayout(history_tab)

        # 左侧查询控制
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)

        # 查询条件区域
        query_group = QGroupBox("查询条件")
        query_layout = QFormLayout()

        query_layout.addWidget(QLabel("开始时间:"))
        self.start_datetime = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.start_datetime.setCalendarPopup(True)
        self.start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        query_layout.addWidget(self.start_datetime)

        query_layout.addWidget(QLabel("结束时间:"))
        self.end_datetime = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_datetime.setCalendarPopup(True)
        self.end_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        query_layout.addWidget(self.end_datetime)

        # 添加快速时间范围选择
        quick_time_layout = QHBoxLayout()
        quick_time_label = QLabel("快速选择:")
        quick_time_layout.addWidget(quick_time_label)

        hour_btn = QPushButton("近1小时")
        hour_btn.clicked.connect(lambda: self.set_time_range(1))
        quick_time_layout.addWidget(hour_btn)

        day_btn = QPushButton("近1天")
        day_btn.clicked.connect(lambda: self.set_time_range(24))
        quick_time_layout.addWidget(day_btn)

        week_btn = QPushButton("近7天")
        week_btn.clicked.connect(lambda: self.set_time_range(24 * 7))
        quick_time_layout.addWidget(week_btn)

        month_btn = QPushButton("近30天")
        month_btn.clicked.connect(lambda: self.set_time_range(24 * 30))
        quick_time_layout.addWidget(month_btn)

        query_layout.addRow(quick_time_layout)

        query_layout.addWidget(QLabel("从站ID (选填):"))
        self.history_slave_id = QLineEdit()
        self.history_slave_id.setPlaceholderText("留空表示全部")
        query_layout.addWidget(self.history_slave_id)

        query_layout.addWidget(QLabel("寄存器地址 (选填):"))
        self.history_address = QLineEdit()
        self.history_address.setPlaceholderText("留空表示全部")
        query_layout.addWidget(self.history_address)

        query_layout.addWidget(QLabel("通道筛选 (选填):"))
        self.history_channel_combo = QComboBox()
        self.history_channel_combo.addItem("全部通道")
        # 从数据库加载可用通道
        self.load_history_channels()
        self.history_channel_combo.setMinimumWidth(200)
        query_layout.addWidget(self.history_channel_combo)

        # 按钮布局
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setSpacing(10)
        
        # 第一行：主要操作按钮
        primary_btn_layout = QHBoxLayout()
        query_btn = QPushButton("查询")
        query_btn.setMinimumWidth(120)
        query_btn.clicked.connect(self.query_history_data)
        primary_btn_layout.addWidget(query_btn)
        
        primary_btn_layout.addStretch()
        
        export_btn = QPushButton("导出CSV")
        export_btn.clicked.connect(self.export_history_data)
        primary_btn_layout.addWidget(export_btn)
        
        plot_btn = QPushButton("显示曲线")
        plot_btn.clicked.connect(self.plot_history_data)
        primary_btn_layout.addWidget(plot_btn)
        
        # 第二行：危险操作按钮
        danger_btn_layout = QHBoxLayout()
        danger_btn_layout.addStretch()
        
        delete_query_btn = QPushButton("删除查询结果")
        delete_query_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        delete_query_btn.clicked.connect(self.delete_query_results)
        danger_btn_layout.addWidget(delete_query_btn)
        
        button_layout.addLayout(primary_btn_layout)
        button_layout.addLayout(danger_btn_layout)
        
        query_layout.addRow(button_container)

        query_group.setLayout(query_layout)
        control_layout.addWidget(query_group)

        # 数据表格
        table_group = QGroupBox("数据表格")
        table_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels(["ID", "时间戳", "从站ID", "地址", "功能码", "数值", "通道名称"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.history_table)
        
        # 删除按钮
        delete_btn_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("删除选中数据")
        self.delete_selected_btn.setFont(QFont("Arial", 10))
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.delete_selected_btn.clicked.connect(self.delete_selected_history_data)
        delete_btn_layout.addWidget(self.delete_selected_btn)
        delete_btn_layout.addStretch()
        
        table_layout.addLayout(delete_btn_layout)

        table_group.setLayout(table_layout)
        control_layout.addWidget(table_group)

        control_layout.addStretch()

        # 右侧曲线显示
        plot_widget = QWidget()
        plot_widget_layout = QVBoxLayout(plot_widget)

        self.history_figure = Figure(figsize=(10, 8))
        self.history_canvas = FigureCanvas(self.history_figure)
        self.history_ax = self.history_figure.add_subplot(111)

        # 初始化历史图表
        self.history_ax.set_xlabel('时间')
        self.history_ax.set_ylabel('数值')
        self.history_ax.set_title('历史数据曲线')
        self.history_ax.grid(True)
        self.history_ax.legend()

        # 添加导航工具栏(支持拖动、缩放等功能)
        self.history_toolbar = NavigationToolbar(self.history_canvas, self)
        plot_widget_layout.addWidget(self.history_toolbar)
        plot_widget_layout.addWidget(self.history_canvas)
        
        # 添加鼠标移动事件处理（悬停显示数值）
        self.history_canvas.mpl_connect('motion_notify_event', self.on_history_plot_hover)
        # 添加右键点击事件处理
        self.history_canvas.mpl_connect('button_press_event', self.on_history_right_click)
        
        # 初始化历史曲线数据存储
        self.history_plot_data = {}

        # 添加到主布局
        history_layout.addWidget(control_widget, 1)
        history_layout.addWidget(plot_widget, 2)

        return history_tab

    def load_history_channels(self):
        """从数据库加载可用的通道列表"""
        try:
            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            try:
                # 获取所有唯一的 (slave_id, address, function_code) 组合
                cursor.execute('''
                    SELECT DISTINCT slave_id, address, function_code
                    FROM modbus_data
                    ORDER BY slave_id, address
                ''')
                rows = cursor.fetchall()
            finally:
                conn.close()

            # 保存通道信息
            self.history_channels = []
            for row in rows:
                self.history_channels.append({
                    'slave_id': row[0],
                    'address': row[1],
                    'function_code': row[2]
                })

            # 更新下拉列表
            current_text = self.history_channel_combo.currentText()
            self.history_channel_combo.clear()
            self.history_channel_combo.addItem("全部通道")

            for channel in self.history_channels:
                # 尝试匹配寄存器配置中的通道名称
                channel_name = None
                # 首先从register_configs中查找
                for config in self.register_configs:
                    # 将整数function_code转换为十六进制字符串进行比较
                    config_func_str = f"0x{config['function_code']:02X}"
                    if (config['slave_id'] == channel['slave_id'] and
                        config['address'] == channel['address'] and
                        config_func_str == channel['function_code']):
                        channel_name = config['name']
                        break
                
                # 如果没有找到，再从channel_configs中查找
                if not channel_name:
                    for config in self.channel_configs:
                        # channel_configs中的function_code可能是整数或字符串，需要统一处理
                        config_func = config['function_code']
                        if isinstance(config_func, int):
                            config_func_str = f"0x{config_func:02X}"
                        else:
                            config_func_str = config_func
                        if (config['slave_id'] == channel['slave_id'] and
                            config['address'] == channel['address'] and
                            config_func_str == channel['function_code']):
                            channel_name = config['name']
                            break

                if channel_name:
                    display_text = f"{channel_name} (ID:{channel['slave_id']} Addr:{channel['address']})"
                else:
                    display_text = f"ID:{channel['slave_id']} Addr:{channel['address']} F:{channel['function_code']}"

                self.history_channel_combo.addItem(display_text, channel)

            # 恢复之前的选择
            index = self.history_channel_combo.findText(current_text)
            if index >= 0:
                self.history_channel_combo.setCurrentIndex(index)

        except Exception as e:
            print(f"加载历史通道失败: {str(e)}")

    def set_time_range(self, hours):
        """快速设置时间范围"""
        from datetime import timedelta
        end_time = QDateTime.currentDateTime()
        start_time = end_time.addSecs(-hours * 3600)
        self.start_datetime.setDateTime(start_time)
        self.end_datetime.setDateTime(end_time)

    def query_history_data(self):
        """查询历史数据"""
        try:
            start_time = self.start_datetime.dateTime().toString('yyyy-MM-dd HH:mm:ss')
            end_time = self.end_datetime.dateTime().toString('yyyy-MM-dd HH:mm:ss')
            slave_id = self.history_slave_id.text().strip()
            address = self.history_address.text().strip()
            channel_data = self.history_channel_combo.currentData()

            conn = sqlite3.connect(self.db_file, timeout=10.0)
            cursor = conn.cursor()
            try:
                # 构建查询条件
                conditions = ["timestamp >= ?", "timestamp <= ?"]
                params = [start_time, end_time]

                if slave_id:
                    conditions.append("slave_id = ?")
                    params.append(int(slave_id))

                if address:
                    conditions.append("address = ?")
                    params.append(int(address))

                # 如果选择了特定历史通道,根据通道数据筛选
                if channel_data:
                    conditions.append("slave_id = ? AND address = ? AND function_code = ?")
                    params.extend([channel_data['slave_id'], channel_data['address'], channel_data['function_code']])

                query = f'''
                    SELECT id, timestamp, slave_id, address, function_code, value
                    FROM modbus_data
                    WHERE {' AND '.join(conditions)}
                    ORDER BY timestamp DESC
                    LIMIT 1000
                '''

                cursor.execute(query, params)
                rows = cursor.fetchall()
            finally:
                conn.close()

            self.history_table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                # 填充前6列数据
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.history_table.setItem(row_idx, col_idx, item)

                # 添加通道名称列(第7列)
                slave_id = row[2]
                address = row[3]
                func_code = row[4]

                # 查找匹配的通道名称
                channel_name = ""
                for config in self.channel_configs:
                    if (config['slave_id'] == slave_id and
                        config['address'] == address and
                        f"0x{config['function_code']:02X}" == func_code):
                        channel_name = config['name']
                        break

                # 如果没有匹配当前采集配置,尝试从历史通道中查找
                if not channel_name:
                    for hist_ch in self.history_channels:
                        if (hist_ch['slave_id'] == slave_id and
                            hist_ch['address'] == address and
                            hist_ch['function_code'] == func_code):
                            # 尝试从寄存器配置中匹配名称
                            for reg_config in self.register_configs:
                                if (reg_config['slave_id'] == slave_id and
                                    reg_config['address'] == address and
                                    reg_config['function_code'] == int(func_code, 16)):
                                    channel_name = reg_config['name']
                                    break
                            break

                name_item = QTableWidgetItem(channel_name)
                self.history_table.setItem(row_idx, 6, name_item)

            QMessageBox.information(self, "查询结果", f"共找到 {len(rows)} 条记录")

            # 查询完成后刷新通道列表
            self.load_history_channels()

        except Exception as e:
            QMessageBox.critical(self, "查询错误", f"查询失败: {str(e)}")
    
    def export_history_data(self):
        """导出历史数据到CSV"""
        try:
            import csv
            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "CSV文件 (*.csv);;所有文件 (*)"
            )
            
            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    # 写入表头
                    headers = []
                    for col in range(self.history_table.columnCount()):
                        headers.append(self.history_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    # 写入数据
                    for row in range(self.history_table.rowCount()):
                        row_data = []
                        for col in range(self.history_table.columnCount()):
                            item = self.history_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "导出成功", f"数据已导出到:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出失败: {str(e)}")
    
    def plot_history_data(self):
        """绘制历史数据曲线"""
        try:
            # 获取表格中的数据
            if self.history_table.rowCount() == 0:
                QMessageBox.warning(self, "提示", "请先查询数据")
                return

            # 清除现有曲线
            self.history_ax.clear()
            # 重置历史曲线数据存储
            self.history_plot_data = {}

            # 获取数据
            timestamps = []
            values = []
            addresses = []
            slave_ids = []

            for row in range(self.history_table.rowCount()):
                timestamp_item = self.history_table.item(row, 1)
                value_item = self.history_table.item(row, 5)
                address_item = self.history_table.item(row, 3)
                slave_id_item = self.history_table.item(row, 2)

                if timestamp_item and value_item and address_item and slave_id_item:
                    # 解析时间戳
                    timestamp_str = timestamp_item.text()
                    try:
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    value = float(value_item.text())
                    address = int(address_item.text())
                    slave_id = int(slave_id_item.text())

                    timestamps.append(timestamp)
                    values.append(value)
                    addresses.append(address)
                    slave_ids.append(slave_id)

            if not timestamps:
                QMessageBox.warning(self, "提示", "没有可绘制的数据")
                return

            # 按时间排序
            data = list(zip(timestamps, values, addresses, slave_ids))
            data.sort(key=lambda x: x[0])
            timestamps, values, addresses, slave_ids = zip(*data)

            # 按 (从站ID, 地址) 分组绘制
            from collections import defaultdict
            key_data = defaultdict(list)
            for i, (ts, val, addr, sid) in enumerate(zip(timestamps, values, addresses, slave_ids)):
                key = (sid, addr)
                key_data[key].append((ts, val))

            # 获取历史曲线样式设置（使用用户设置的持久化样式）
            settings = self.history_style_settings
            line_width = settings.get('line_width', 2.0)
            line_style_index = settings.get('line_style', 0)
            alpha = settings.get('alpha', 0.7)
            show_marker = settings.get('show_marker', True)
            marker_style = settings.get('marker_style', 'o')
            
            # 颜色映射 - 将中文颜色名称转换为matplotlib颜色代码
            color_map = {
                '蓝色': 'blue', '红色': 'red', '绿色': 'green', '橙色': 'orange',
                '紫色': 'purple', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
                '橄榄色': 'olive', '青色': 'cyan', '黑色': 'black',
                '深蓝色': 'navy', '深红色': 'darkred', '深绿色': 'darkgreen',
                '金色': 'gold', '银色': 'silver'
            }
            line_color = color_map.get(settings.get('line_color', '红色'), 'red')
            
            # 线条样式映射
            line_styles = ['-', '--', ':', '-.', (0, (3, 1, 1, 1))]
            line_style = line_styles[line_style_index]
            
            # 设置marker
            marker = marker_style if show_marker else None
            markersize = 5 if show_marker else None

            # 为每个组合绘制一条曲线
            for idx, (key, data_points) in enumerate(sorted(key_data.items())):
                sid, addr = key
                data_points.sort(key=lambda x: x[0])
                ts = [dp[0] for dp in data_points]
                vals = [dp[1] for dp in data_points]

                # 从当前采集配置中查找对应的通道名称和颜色
                channel_name = None
                channel_color = None
                function_code = None

                # 首先从channel_configs中查找
                for config in self.channel_configs:
                    if config['slave_id'] == sid and config['address'] == addr:
                        channel_name = config['name']
                        channel_color = config.get('color', '蓝色')
                        function_code = config.get('function_code')
                        break

                # 如果在channel_configs中没找到,尝试从数据库中查找
                if channel_name is None:
                    try:
                        conn = sqlite3.connect(self.db_file, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name, color, function_code FROM register_configs WHERE slave_id = ? AND address = ?",
                                     (sid, addr))
                        result = cursor.fetchone()
                        if result:
                            channel_name = result[0]
                            channel_color = result[1] if result[1] else '蓝色'
                            function_code = result[2]
                        conn.close()
                    except Exception as e:
                        print(f"从数据库查询通道信息失败: {e}")

                if channel_name:
                    label = channel_name
                else:
                    label = f'ID:{sid} Addr:{addr}'

                # 确定曲线颜色：优先使用通道配置的颜色，否则使用索引分配
                if channel_color:
                    curve_color = color_map.get(channel_color, line_color)
                else:
                    # 如果没有找到通道配置，按顺序分配颜色
                    curve_color = color_map.get(self.channel_colors[idx % len(self.channel_colors)], line_color)

                # 设置marker - 使用用户设置的持久化样式参数
                if show_marker:
                    line_obj = self.history_ax.plot(ts, vals, color=curve_color, linewidth=line_width,
                                       linestyle=line_style, label=label,
                                       marker=marker, markersize=markersize, alpha=alpha)[0]
                else:
                    line_obj = self.history_ax.plot(ts, vals, color=curve_color, linewidth=line_width,
                                       linestyle=line_style, label=label, alpha=alpha)[0]
                
                # 保存曲线数据用于悬停显示
                self.history_plot_data[label] = {
                    'x': ts,
                    'y': vals,
                    'line': line_obj,
                    'key': key
                }

            # 设置图表属性
            self.history_ax.set_xlabel('时间')
            self.history_ax.set_ylabel('数值')
            self.history_ax.set_title('历史数据曲线')

            # 根据历史曲线样式设置网格和图例（使用持久化设置）
            show_grid = self.history_style_settings.get('show_grid', True)
            show_legend = self.history_style_settings.get('show_legend', True)
            
            self.history_ax.grid(show_grid, alpha=0.3)

            if show_legend:
                self.history_ax.legend(loc='best', fontsize=8)
            else:
                legend = self.history_ax.get_legend()
                if legend:
                    legend.remove()

            # 自动调整x轴日期格式
            from matplotlib.dates import DateFormatter, AutoDateLocator
            import matplotlib.dates as mdates

            self.history_ax.xaxis.set_major_locator(AutoDateLocator())
            self.history_ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d %H:%M'))

            # 旋转x轴标签以便更好地显示时间
            self.history_ax.tick_params(axis='x', rotation=45, labelsize=8)

            # 自动调整布局
            self.history_figure.tight_layout()

            self.history_canvas.draw()

            QMessageBox.information(self, "成功", f"已绘制 {len(key_data)} 条曲线")

        except Exception as e:
            QMessageBox.critical(self, "绘制错误", f"绘制失败: {str(e)}")
    
    def delete_selected_history_data(self):
        """删除选中的历史数据"""
        try:
            selected_rows = self.history_table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.warning(self, "提示", "请先选择要删除的数据行")
                return
            
            # 收集选中的ID和相关信息用于显示
            delete_ids = []
            delete_info = []
            
            for row in selected_rows:
                row_idx = row.row()
                id_item = self.history_table.item(row_idx, 0)
                timestamp_item = self.history_table.item(row_idx, 1)
                slave_id_item = self.history_table.item(row_idx, 2)
                address_item = self.history_table.item(row_idx, 3)
                value_item = self.history_table.item(row_idx, 5)
                
                if id_item and timestamp_item:
                    data_id = int(id_item.text())
                    delete_ids.append(data_id)
                    
                    # 创建简要信息
                    info = f"ID: {data_id}, 时间: {timestamp_item.text()}"
                    if slave_id_item:
                        info += f", 从站: {slave_id_item.text()}"
                    if address_item:
                        info += f", 地址: {address_item.text()}"
                    if value_item:
                        info += f", 数值: {value_item.text()}"
                    
                    delete_info.append(info)
            
            if not delete_ids:
                QMessageBox.warning(self, "错误", "无法获取选中数据的ID")
                return
            
            # 显示确认对话框
            confirm_msg = f"确定要删除以下 {len(delete_ids)} 条数据吗？\n\n"
            confirm_msg += "\n".join(delete_info[:10])  # 最多显示前10条
            
            if len(delete_ids) > 10:
                confirm_msg += f"\n... 以及另外 {len(delete_ids) - 10} 条数据"
            
            reply = self.positioned_question("确认删除", confirm_msg)
            
            if reply == QMessageBox.StandardButton.Yes:
                conn = sqlite3.connect(self.db_file, timeout=10.0)
                cursor = conn.cursor()
                try:
                    # 构建IN查询
                    placeholders = ','.join(['?'] * len(delete_ids))
                    cursor.execute(f"DELETE FROM modbus_data WHERE id IN ({placeholders})", delete_ids)
                    conn.commit()
                    
                    # 重新查询以刷新表格
                    self.query_history_data()
                    
                    QMessageBox.information(self, "成功", f"已删除 {len(delete_ids)} 条数据")
                finally:
                    conn.close()
        
        except Exception as e:
            QMessageBox.critical(self, "删除错误", f"删除失败: {str(e)}")
    
    def delete_query_results(self):
        """删除符合查询条件的所有历史数据"""
        try:
            # 获取查询条件（与query_history_data相同）
            start_time = self.start_datetime.dateTime().toString('yyyy-MM-dd HH:mm:ss')
            end_time = self.end_datetime.dateTime().toString('yyyy-MM-dd HH:mm:ss')
            slave_id = self.history_slave_id.text().strip()
            address = self.history_address.text().strip()
            channel_data = self.history_channel_combo.currentData()
            
            # 构建查询条件
            conditions = ["timestamp >= ?", "timestamp <= ?"]
            params = [start_time, end_time]
            
            if slave_id:
                conditions.append("slave_id = ?")
                params.append(int(slave_id))
            
            if address:
                conditions.append("address = ?")
                params.append(int(address))
            
            # 如果选择了特定历史通道,根据通道数据筛选
            if channel_data:
                # 确保function_code格式正确
                func_code = channel_data['function_code']
                if isinstance(func_code, int):
                    # 转换为十六进制字符串格式，如 "0x03"
                    func_code_str = f"0x{func_code:02X}"
                else:
                    # 如果是字符串，确保格式正确
                    func_code_str = str(func_code)
                    if not func_code_str.startswith('0x'):
                        try:
                            func_code_int = int(func_code_str)
                            func_code_str = f"0x{func_code_int:02X}"
                        except ValueError:
                            pass  # 保持原样
                
                conditions.append("slave_id = ? AND address = ? AND function_code = ?")
                params.extend([channel_data['slave_id'], channel_data['address'], func_code_str])
            
            # 显示确认对话框
            confirm_msg = f"确定要删除以下条件的所有数据吗？\n"
            confirm_msg += f"时间范围: {start_time} 到 {end_time}\n"
            if slave_id:
                confirm_msg += f"从站ID: {slave_id}\n"
            if address:
                confirm_msg += f"寄存器地址: {address}\n"
            if channel_data:
                confirm_msg += f"通道: ID:{channel_data['slave_id']}, Addr:{channel_data['address']}\n"
            
            confirm_msg += "\n此操作无法撤销！"
            
            reply = self.positioned_question("确认删除查询结果", confirm_msg)
            
            if reply == QMessageBox.StandardButton.Yes:
                conn = sqlite3.connect(self.db_file, timeout=10.0)
                cursor = conn.cursor()
                try:
                    # 执行删除
                    delete_query = f"DELETE FROM modbus_data WHERE {' AND '.join(conditions)}"
                    cursor.execute(delete_query, params)
                    conn.commit()
                    
                    # 重新查询以刷新表格
                    self.query_history_data()
                    
                    # 刷新通道列表
                    self.load_history_channels()
                    
                    QMessageBox.information(self, "成功", "已删除符合条件的所有数据")
                finally:
                    conn.close()
        
        except Exception as e:
            QMessageBox.critical(self, "删除错误", f"删除失败: {str(e)}")
    
    def parse_function(self, func_str):
        """解析并返回可执行的函数"""
        func_str = func_str.replace('^', '**')
        
        # 替换math.前缀为np.
        func_str = re.sub(r'\bmath\.', 'np.', func_str)
        
        math_functions = {
            'sin': 'np.sin',
            'cos': 'np.cos',
            'tan': 'np.tan',
            'exp': 'np.exp',
            'log': 'np.log',
            'log10': 'np.log10',
            'sqrt': 'np.sqrt',
            'abs': 'np.abs',
            'pi': 'np.pi',
            'e': 'np.e',
            'arcsin': 'np.arcsin',
            'arccos': 'np.arccos',
            'arctan': 'np.arctan',
            'asin': 'np.arcsin',
            'acos': 'np.arccos',
            'atan': 'np.arctan',
            'sinh': 'np.sinh',
            'cosh': 'np.cosh',
            'tanh': 'np.tanh',
            'ceil': 'np.ceil',
            'floor': 'np.floor',
            'round': 'np.round',
            'sign': 'np.sign',
            'deg2rad': 'np.deg2rad',
            'rad2deg': 'np.rad2deg',
            'degrees': 'np.degrees',
            'radians': 'np.radians',
        }
        
        for func, np_func in math_functions.items():
            pattern = r'\b' + func + r'\b'
            func_str = re.sub(pattern, np_func, func_str)
        
        return func_str
    
    def plot_function(self):
        """绘制函数曲线"""
        try:
            func_str = self.function_input.text().strip()
            x_min = float(self.x_min_input.text())
            x_max = float(self.x_max_input.text())
            points = int(self.points_input.text())
            # 使用实时曲线样式设置
            settings = self.realtime_style_settings
            line_color_name = settings.get('line_color', '蓝色')
            line_width = settings.get('line_width', 2.0)
            show_grid = settings.get('show_grid', True)

            # 颜色映射
            color_map = {
                "蓝色": "blue", "红色": "red", "绿色": "green", "橙色": "orange",
                "紫色": "purple", "棕色": "brown", "粉色": "pink", "灰色": "gray",
                "橄榄色": "olive", "青色": "cyan", "黑色": "black",
                "深蓝色": "navy", "深红色": "darkred", "深绿色": "darkgreen",
                "金色": "gold", "银色": "silver"
            }
            line_color = color_map.get(line_color_name, "blue")

            if x_min >= x_max:
                QMessageBox.warning(self, "参数错误", "X最小值必须小于X最大值")
                return

            if points <= 0:
                QMessageBox.warning(self, "参数错误", "采样点数必须大于0")
                return

            x = np.linspace(x_min, x_max, points)
            parsed_func = self.parse_function(func_str)

            try:
                y = eval(parsed_func, {'np': np, 'x': x})
            except SyntaxError as e:
                QMessageBox.warning(self, "语法错误", f"函数语法错误: {str(e)}\n请检查函数表达式")
                return
            except NameError as e:
                QMessageBox.warning(self, "函数错误", f"未定义的函数或变量: {str(e)}\n请使用内置数学函数如sin, cos, log等")
                return
            except ValueError as e:
                QMessageBox.warning(self, "数学错误", f"数学错误: {str(e)}\n可能由于函数定义域问题（如log(-1)）")
                return
            except Exception as e:
                QMessageBox.warning(self, "函数错误", f"无法解析函数: {str(e)}")
                return

            if not isinstance(y, (np.ndarray, float, int)):
                QMessageBox.warning(self, "函数错误", "函数必须返回数值")
                return
            
            # 处理标量情况：常数函数
            if isinstance(y, (float, int)):
                y = np.full_like(x, y)

            self.ax.clear()
            self.ax.plot(x, y, color=line_color, linewidth=line_width)
            self.ax.set_xlabel('x')
            self.ax.set_ylabel(f'f(x) = {func_str}')
            self.ax.set_title('函数曲线')
            self.ax.grid(show_grid)
            self.canvas.draw()

        except ValueError as e:
            QMessageBox.warning(self, "参数错误", f"请输入有效的数值: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")
    
    def clear_plot(self):
        """清除图像"""
        self.ax.clear()
        self.canvas.draw()
    
    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        if self.is_collecting:
            self.stop_collection()
        
        if self.is_connected:
            self.disconnect_modbus()
        
        event.accept()

    class StyleSettingsDialog(QDialog):
        """曲线样式设置对话框"""
        def __init__(self, parent=None, is_realtime=True):
            super().__init__(parent)
            self.is_realtime = is_realtime
            self.setWindowTitle("实时曲线样式设置" if is_realtime else "历史曲线样式设置")
            self.setModal(True)
            self.setup_ui()
            
        def setup_ui(self):
            layout = QFormLayout(self)
            
            # 线条颜色
            self.line_color_input = QComboBox()
            self.line_color_input.addItems([
                "蓝色", "红色", "绿色", "橙色", "紫色", "棕色", "粉色", "灰色", "橄榄色", "青色",
                "黑色", "深蓝色", "深红色", "深绿色", "金色", "银色"
            ])
            self.line_color_input.setCurrentText("蓝色" if self.is_realtime else "红色")
            layout.addRow("线条颜色:", self.line_color_input)
            
            # 线条宽度
            self.line_width_input = QLineEdit()
            self.line_width_input.setText("2")
            layout.addRow("线条宽度:", self.line_width_input)
            
            # 线条样式
            self.line_style_input = QComboBox()
            self.line_style_input.addItems(["实线", "虚线", "点线", "点划线", "点-点-划线"])
            self.line_style_input.setCurrentIndex(0)
            layout.addRow("线条样式:", self.line_style_input)
            
            # 透明度
            self.alpha_input = QSpinBox()
            self.alpha_input.setRange(10, 100)
            self.alpha_input.setValue(80 if self.is_realtime else 70)
            self.alpha_input.setSuffix("%")
            layout.addRow("透明度:", self.alpha_input)
            
            # 显示网格
            self.grid_checkbox = QCheckBox("显示网格")
            self.grid_checkbox.setChecked(True)
            layout.addRow(self.grid_checkbox)
            
            # 显示图例
            self.legend_checkbox = QCheckBox("显示图例")
            self.legend_checkbox.setChecked(True)
            layout.addRow(self.legend_checkbox)
            
            # 显示数据点
            self.marker_checkbox = QCheckBox("显示数据点")
            self.marker_checkbox.setChecked(True)
            layout.addRow(self.marker_checkbox)
            
            # 数据点标记样式
            self.marker_style_input = QComboBox()
            self.marker_style_input.addItems([
                "圆形 (o)", "方形 (s)", "三角形 (^)", "倒三角形 (v)", 
                "菱形 (D)", "星形 (*)", "十字 (+)", "叉号 (x)", "点 (.)"
            ])
            self.marker_style_input.setCurrentIndex(0)
            layout.addRow("标记样式:", self.marker_style_input)
            
            # 按钮
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            layout.addRow(button_box)
            
        def get_settings(self):
            """获取样式设置"""
            # 标记样式映射
            marker_styles = ['o', 's', '^', 'v', 'D', '*', '+', 'x', '.']
            settings = {
                'line_color': self.line_color_input.currentText(),
                'line_width': float(self.line_width_input.text()),
                'line_style': self.line_style_input.currentIndex(),
                'alpha': self.alpha_input.value() / 100.0,
                'show_grid': self.grid_checkbox.isChecked(),
                'show_legend': self.legend_checkbox.isChecked(),
                'show_marker': self.marker_checkbox.isChecked(),
                'marker_style': marker_styles[self.marker_style_input.currentIndex()]
            }
            return settings


def main():
    app = QApplication(sys.argv)
    window = FunctionPlotter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
