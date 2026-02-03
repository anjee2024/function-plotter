"""
函数曲线绘制器 - 基础版本
专注于函数曲线绘制功能
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
    window.setWindowTitle("函数曲线绘制器 - 基础版")
    
    # 自动切换到函数曲线标签页
    try:
        # 查找函数曲线标签页并设置为当前页
        for i in range(window.tab_widget.count()):
            if window.tab_widget.tabText(i) == "函数曲线":
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
