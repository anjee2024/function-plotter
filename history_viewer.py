"""
历史数据查看器 - 专注于历史数据查询和可视化
这是一个独立的历史数据查看工具
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from function_plotter import FunctionPlotter
from PyQt6.QtWidgets import QApplication, QTabWidget

def main():
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = FunctionPlotter()
    
    # 设置窗口标题
    window.setWindowTitle("历史数据查看器 - Modbus历史数据")
    
    # 自动切换到历史数据标签页
    try:
        # 查找历史数据标签页并设置为当前页
        for i in range(window.tab_widget.count()):
            if window.tab_widget.tabText(i) == "历史数据":
                window.tab_widget.setCurrentIndex(i)
                break
    except:
        pass
    
    # 显示窗口
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
