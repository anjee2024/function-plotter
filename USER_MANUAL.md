# FunctionPlotter User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Features](#features)
5. [Detailed Guide](#detailed-guide)
6. [FAQ](#faq)
7. [Technical Support](#technical-support)

## Introduction

FunctionPlotter is a multi-functional application based on PyQt6, providing the following features:

- ✅ Mathematical function curve plotting
- ✅ Modbus TCP/RTU device real-time monitoring
- ✅ Historical data query and visualization
- ✅ Multi-channel data acquisition
- ✅ Custom function library management

## Quick Start

### Run the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run main program
python function_plotter.py
```

### Choose Different Versions

- **function_plotter.py** - Full version (all features)
- **data_collector.py** - Data collector (Modbus focused)
- **history_viewer.py** - History viewer (query focused)
- **function_plotter_simple.py** - Basic function plotter (plotting focused)

## Installation

### System Requirements

- **OS**: Windows 10/11 64-bit
- **Python**: 3.8 or higher
- **Runtime**: Visual C++ Redistributable (usually included)

### Installation Steps

1. Download program files
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the program:
   ```bash
   python function_plotter.py
   ```

### Dependencies

```
PyQt6==6.7.0          # GUI Framework
numpy==1.26.4          # Numerical Computing
matplotlib==3.8.4       # Chart Plotting
pymodbus==3.7.4        # Modbus Protocol
pyserial==3.5           # Serial Communication
```

## Features

### 1. Function Curve Plotting

**Features:**
- Support for common mathematical function expressions
- Custom function library management
- Parameter configuration (x-axis range, sampling points)
- Style settings (line color, width)
- Quick function buttons
- Grid display toggle
- Chinese character support

### 2. Modbus Real-time Monitoring

**Features:**
- Support for Modbus TCP and RTU connections
- Multi-channel data acquisition (up to 10 channels)
- Register configuration management
- Real-time curve display
- SQLite database storage
- Adjustable acquisition interval
- Data export functionality

**Supported Function Codes:**
- 0x01 - Read Coils
- 0x02 - Read Discrete Inputs
- 0x03 - Read Holding Registers
- 0x04 - Read Input Registers

### 3. Historical Data Query

**Features:**
- Time range query
- Slave ID filtering
- Data table display
- Curve visualization
- Export to CSV
- Data deletion functionality

## Detailed Guide

### Function Curve Plotting

#### Basic Usage

1. **Switch to Function Plotting Tab**
   - Click the "函数曲线" tab at the top

2. **Enter Function Expression**
   - Type a mathematical expression in the "函数 f(x)" input box
   - Examples:
     ```
     sin(x)              # Sine function
     x**2 + 2*x + 1     # Quadratic function
     exp(-x**2)          # Gaussian function
     log(x) + sqrt(x)     # Logarithm + Square root
     ```

3. **Set Parameters**
   - **X-axis Range**: Set minimum and maximum x values
   - **Sampling Points**: Set curve precision (more points = smoother curve)

4. **Adjust Style**
   - **Line Color**: Choose curve color
   - **Line Width**: Set line thickness

5. **Draw Curve**
   - Click the "绘制曲线" button
   - The curve will appear in the right chart area

#### Using Quick Functions

Built-in quick function buttons:
- **sin** - Sine function
- **cos** - Cosine function
- **tan** - Tangent function
- **exp** - Exponential function
- **log** - Logarithm function
- **sqrt** - Square root function
- **abs** - Absolute value function

Click a button to quickly add the function to the input box.

#### Managing Custom Functions

**Add Custom Function:**

1. Click the "添加函数" button
2. In the dialog, enter:
   - **Function Name**: e.g., "my_function"
   - **Function Expression**: e.g., "sin(x) + cos(x)"
   - **Description**: Optional, e.g., "Sine cosine combination"

3. Click "确定" to save

**Use Custom Function:**

1. Select a function from the "自定义函数库" list
2. Click the "使用选中" button
3. The function expression will be loaded into the input box

**Delete Custom Function:**

1. Select a function from the list
2. Click the "删除函数" button
3. Confirm deletion

### Modbus Real-time Monitoring

#### Mode Selection: Single vs Multi-channel

**Single Channel Mode:**
- Use traditional device parameter configuration
- Suitable for simple single-point acquisition

**Multi-channel Mode:**
- Support simultaneous acquisition of multiple channels
- Each channel has independent slave ID, address, function code
- Different channels use different colored curves
- Suitable for complex monitoring scenarios

#### Multi-channel Configuration

**Add Channel:**

1. In the "通道管理" area, click "添加通道"
2. Fill in channel information:
   - **Channel Name**: e.g., "Temperature Sensor"
   - **Slave ID**: Modbus slave address (1-247)
   - **Start Address**: Register address
   - **Register Count**: Number of registers to read
   - **Function Code**:
     - 3: Read Holding Registers
     - 4: Read Input Registers
     - 1: Read Coils
     - 2: Read Discrete Inputs
   - **Unit**: Optional, e.g., "℃", "V"
   - **Scale**: Value conversion scale (default 1.0)
   - **Offset**: Value conversion offset (default 0.0)
   - **Curve Color**: Choose curve display color

3. Click "确定" to add channel

**Delete Channel:**

1. Select channel in channel list
2. Click "删除通道" button
3. Confirm deletion

**Modify Channel Configuration:**

1. Select channel in channel list
2. Click "修改配置" button
3. Modify configuration
4. Click "确定" to save

#### Connecting to Device

**TCP Mode:**

1. Select connection type as "TCP"
2. Set parameters:
   - **Host Address**: e.g., "192.168.1.100"
   - **Port**: e.g., 502 (default)

**RTU Mode:**

1. Select connection type as "RTU"
2. Click "搜索" button to find available serial ports
3. Select serial port from dropdown (e.g., COM3)
4. Set serial parameters:
   - **Baud Rate**: 9600 (common value)
   - **Data Bits**: 8
   - **Stop Bits**: 1
   - **Parity**: None/Odd/Even

3. Click "连接设备" button

#### Start Data Acquisition

1. Set acquisition parameters:
   - **Acquisition Interval**: Data acquisition frequency (ms)
   - **Storage Interval**: Database save interval (seconds)
   - **Save to Database**: Check to enable

2. Click "开始采集" button

3. Real-time curves will start updating:
   - Single channel mode: One curve
   - Multi-channel mode: Multiple curves, each for a channel

4. Real-time data display:
   - Latest values displayed above curves
   - Includes values and timestamps

#### Stop and Clear Data

- **Stop Acquisition**: Click "停止采集" button
- **Clear Data**: Click "清除数据" button to clear all data

#### Using Register Configurations

**Add Configuration:**

1. Click "添加配置" in "寄存器配置" area
2. Fill in configuration (similar to adding channel)
3. Click "确定" to save

**Use Configuration:**

1. Select configuration from list
2. Click "使用配置" button
3. Configuration loads into device parameter area

**Delete Configuration:**

1. Select configuration from list
2. Click "删除配置" button

### Historical Data Query

#### Query Historical Data

1. **Switch to Historical Data Tab**
   - Click the "历史数据" tab

2. **Set Query Conditions:**
   - **Start Time**: Set start date and time
   - **End Time**: Set end date and time
   - **Slave ID** (Optional): Filter specific slave data

3. **Click "查询" button**
   - Data displays in table on left

#### View Historical Curves

1. After querying data
2. Click "显示曲线" button
3. System plots curves grouped by register address
   - Different addresses use different colors
   - Curves display on right chart area

#### Export Data

1. After querying data
2. Click "导出CSV" button
3. Choose save location
4. File saves in CSV format with all query results

#### Delete Historical Data

⚠️ **Warning: Deletion cannot be undone!**

**Delete Selected Data:**

1. Select rows in data table (multi-select supported)
2. Click "删除选中数据" button
3. View details in confirmation dialog
4. Click "是" to confirm

**Delete Query Results:**

1. Set query conditions
2. Click "删除查询结果" button (red)
3. View conditions in confirmation dialog
4. Click "是" to confirm

### Curve Style Settings

#### Real-time Curve Style

1. **Right-click** on real-time chart area
2. Style settings dialog appears
3. Set:
   - **Line Color**: Curve color
   - **Line Width**: Line thickness
   - **Line Style**: Solid, dashed, dotted, etc.
   - **Transparency**: Curve alpha
   - **Show Grid**: Toggle coordinate grid
   - **Show Legend**: Toggle curve legend
   - **Show Markers**: Toggle data point markers
   - **Marker Style**: Marker shape

4. Click "确定" to apply

#### Historical Curve Style

1. **Right-click** on historical chart area
2. Set same as real-time curves

#### Multi-channel Color Settings

In multi-channel mode, colors are set per channel:
1. Click "修改配置"
2. Select color in "曲线颜色" dropdown
3. Click "确定" to save
4. Color updates immediately if acquiring

### Database Information

Program uses SQLite database:

**Database Location:**
- Auto-created in program directory
- Filename: `modbus_data.db`

**Database Tables:**

**modbus_data** (Historical data):
- id: Primary key
- timestamp: Timestamp
- slave_id: Slave ID
- address: Register address
- function_code: Function code
- value: Value
- unit: Unit

**custom_functions** (Custom functions):
- id: Primary key
- name: Function name
- expression: Function expression
- description: Description

**register_configs** (Register configs):
- id: Primary key
- name: Config name
- slave_id: Slave ID
- address: Address
- count: Count
- function_code: Function code
- unit: Unit
- scale: Scale
- offset: Offset
- color: Curve color

## FAQ

### Q1: Program won't start

**Possible causes:**
1. Python version too old (needs 3.8+)
2. Dependencies not installed
3. Missing runtime libraries

**Solutions:**
1. Check Python version: `python --version`
2. Install dependencies: `pip install -r requirements.txt`
3. Install Visual C++ Redistributable

### Q2: Chinese characters display as garbled text

**Solution:**
Program includes Chinese font support. If issues persist:
1. Ensure Chinese fonts installed (SimHei, Microsoft YaHei)
2. Restart program

### Q3: Modbus connection failed

**Checklist:**
1. Device properly connected
2. IP/port configuration correct
3. Serial parameters correct
4. Slave ID correct
5. Firewall not blocking

**Solutions:**
1. Test with Modbus debug tool
2. Check network/serial connection
3. Verify device parameters

### Q4: Can't find serial port in RTU mode

**Solution:**
1. Click "搜索" button to auto-search
2. Check serial port drivers installed
3. Confirm COM port name in Device Manager
4. Manually enter COM port (e.g., COM3)

### Q5: Curves not displaying or abnormal

**Possible causes:**
1. Improper data range settings
2. Acquisition interval too short
3. Values out of chart range

**Solutions:**
1. Check Y-axis range
2. Increase acquisition interval
3. Click "auto scale" in chart toolbar

### Q6: Program freezes during acquisition

**Solution:**
1. Increase acquisition interval (≥100ms recommended)
2. Reduce number of channels
3. Close unnecessary background programs
4. Restart program

### Q7: How to backup data?

**Backup database:**
1. Close program
2. Copy `modbus_data.db` to backup location
3. Backup can be restored anytime

### Q8: How to set colors in multi-channel mode?

**Method:**
1. Click "修改配置" button
2. Select color in "曲线颜色" dropdown
3. Save configuration
4. Color applies immediately to corresponding channel

### Q9: How to change data storage location?

**Solution:**
Current version saves to program directory. To change:
1. Move `modbus_data.db` to new location
2. Program will create database in new location

### Q10: What mathematical functions are supported?

**Supported:**
- **Trigonometric**: sin, cos, tan, asin, acos, atan
- **Hyperbolic**: sinh, cosh, tanh
- **Exponential/Log**: exp, log, log10, log2
- **Others**: sqrt, abs, pow, round
- **Constants**: pi, e

**Examples:**
```
sin(x) + cos(x)          # Trigonometric
exp(x) + exp(-x)         # Exponential
log(x) / log(2)          # Logarithmic
sqrt(x**2 + y**2)        # Composite
pi * x                    # Using constants
```

## Technical Support

### Getting Help

If you encounter issues:

1. **View Logs**
   - Debug info output to console
   - Record errors for troubleshooting

2. **Check Documentation**
   - Read relevant sections in this manual
   - Check program tooltips and prompts

3. **Database Issues**
   - Check if `modbus_data.db` exists
   - Confirm file not locked by other program

### Performance Optimization

1. **Reasonable Acquisition Interval**
   - Recommended ≥100ms
   - Too short may cause performance issues

2. **Reasonable Storage Interval**
   - Storage interval should be ≥ acquisition interval
   - Recommended ≥5 seconds

3. **Regular Data Cleanup**
   - Delete unnecessary historical data
   - Keep database file size reasonable

4. **Channel Count Control**
   - Multi-channel mode: ≤10 channels recommended
   - Too many channels may affect performance

### Data Security

**Recommendations:**
1. Regularly backup database file
2. Confirm before deleting data
3. Don't manually edit database file
4. Use export function to backup data

## Appendix

### Keyboard Shortcuts

- **Ctrl + Enter**: Draw curve (Function Plotting tab)
- **F5**: Refresh query results (Historical Data tab)
- **Delete**: Delete selected items

### Supported File Formats

- **Database**: SQLite (.db)
- **Export**: CSV (.csv)

### Version History

**Version 1.0.0**
- Initial release
- Function curve plotting
- Modbus TCP/RTU connection
- Multi-channel data acquisition
- Historical data query
- Data export

---

**Enjoy using FunctionPlotter!**

For any questions or suggestions, please provide feedback.
