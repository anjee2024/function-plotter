"""
数据采集器 - 专注于Modbus数据采集和实时显示
这是一个独立的数据采集工具
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from function_plotter import FunctionPlotter
from PyQt6.QtWidgets import QApplication

def main():
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = FunctionPlotter()
    
    # 设置窗口标题
    window.setWindowTitle("数据采集器 - Modbus实时采集")
    
    # 显示窗口
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
