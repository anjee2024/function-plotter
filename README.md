# FunctionPlotter

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**一个基于 PyQt6 的多功能应用程序，支持数学函数曲线绘制和 Modbus TCP/RTU 设备实时数据监控**

[English](USER_MANUAL.md) | [中文](使用说明.md)

</div>

## ✨ 特性

### 📊 函数曲线绘制
- 支持常见数学函数表达式
- 自定义函数库管理
- 参数配置（x轴范围、采样点数）
- 样式设置（线条颜色、宽度）
- 中文字符支持

### 🔌 Modbus 实时监控
- 支持 Modbus TCP 和 RTU 连接
- 多通道数据采集（最多10个通道）
- 寄存器配置管理
- 实时曲线显示
- SQLite 数据库存储
- 数据导出功能

### 📈 历史数据查询
- 时间范围查询
- 从站ID筛选
- 数据表格展示
- 曲线可视化
- 导出为 CSV

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
# 完整版
python function_plotter.py

# 数据采集器
python data_collector.py

# 历史数据查看器
python history_viewer.py

# 基础函数绘制器
python function_plotter_simple.py
```

## 📖 使用说明

- [中文使用说明](使用说明.md)
- [English User Manual](USER_MANUAL.md)

## 🛠️ 技术栈

- **GUI Framework**: PyQt6
- **Numerical Computing**: NumPy
- **Plotting**: Matplotlib
- **Modbus Protocol**: pymodbus
- **Serial Communication**: pyserial
- **Database**: SQLite3

## 📸 截图

### 函数曲线绘制
![Function Plotting](#)

### Modbus 实时监控
![Modbus Monitoring](#)

### 历史数据查询
![History Query](#)

## 🌟 功能演示

### 多通道数据采集
支持同时采集最多10个通道数据，每个通道独立配置：
- 从站ID
- 寄存器地址
- 功能码
- 单位
- 比例和偏移量
- 曲线颜色

### 自定义函数
支持添加、使用和管理自定义数学函数，方便快速调用常用表达式。

### 数据导出
历史数据可导出为 CSV 格式，便于后续分析。

## 📋 系统要求

- **操作系统**: Windows 10/11 64位
- **Python**: 3.8 或更高版本
- **运行库**: Visual C++ Redistributable

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👤 作者

Your Name

## 📮 联系方式

如有问题或建议，请提交 Issue。
