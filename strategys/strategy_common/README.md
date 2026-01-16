# 通用网格交易策略教程

## 📋 简介

通用网格交易策略，支持多个交易所（StandX、GRVT 等），自动执行做多做空订单管理，支持持仓自动平仓。

## 🎯 特性

- ✅ 支持多交易所（StandX、GRVT 等）
- ✅ 通过命令行参数指定交易所
- ✅ 统一的配置格式
- ✅ 自动网格管理
- ✅ ADX 动态价格间距调整
- ✅ 持仓自动平仓

## 📊 策略逻辑

### 执行流程

1. **获取价格**: 获取当前交易对价格
2. **生成网格**: 根据当前价格、价格间距和网格数量生成做多/做空网格数组
   - 做多数组：当前价格 - 价格间距 向下生成网格
   - 做空数组：当前价格 + 价格间距 向上生成网格
3. **查询订单**: 获取当前所有未成交订单
4. **计算撤单**: 找出不在目标网格中的订单
5. **执行撤单**: 批量撤销不需要的订单
6. **计算下单**: 找出目标网格中缺失的订单
7. **执行下单**: 为缺失的网格价格创建限价单
8. **检查持仓**: 如果检测到持仓，先取消所有未成交订单，然后市价平仓
9. **循环执行**: 等待指定时间后重复上述流程

## ⚠️ 风险提示

### 主要风险

1. **市场风险**
   - 价格剧烈波动可能导致订单快速成交
   - 单边行情可能导致大量订单同时成交
   - 极端行情可能导致滑点损失

2. **技术风险**
   - 网络中断可能导致策略停止运行
   - API 限制可能导致订单失败
   - 程序错误可能导致异常交易

3. **资金风险**
   - 网格策略需要足够的资金支持
   - 订单数量过多可能导致资金分散
   - 持仓平仓可能产生额外损失

4. **操作风险**
   - 配置错误可能导致意外交易
   - 私钥/API Key 泄露可能导致资金损失
   - 策略参数不当可能导致亏损

### 使用建议

- ✅ 先用小额资金测试策略
- ✅ 充分理解策略逻辑后再使用
- ✅ 定期检查策略运行状态
- ✅ 设置合理的网格参数
- ✅ 确保网络连接稳定
- ❌ 不要使用全部资金
- ❌ 不要在不理解的情况下使用
- ❌ 不要忽略风险提示

### 免责声明

**本策略仅供学习和研究使用。使用本策略进行交易的所有风险由使用者自行承担。作者不对任何交易损失负责。**

## 🔧 环境要求

- Python 3.9 或更高版本
- 交易所账户和认证信息（私钥或 API Key）

## 📦 安装步骤

### Linux / Mac

#### 方式一：使用 Git（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/Dazmon88/DD-strategy-bot.git
cd DD-strategy-bot

# 2. 更新代码（后续更新时使用）
git pull origin main
```

#### 方式二：使用 curl 下载

```bash
# 1. 下载并解压
curl -L https://github.com/Dazmon88/DD-strategy-bot/archive/refs/heads/main.zip -o DD-strategy-bot.zip
unzip DD-strategy-bot.zip
cd DD-strategy-bot-main
```

#### 方式三：使用 wget 下载

```bash
# 1. 下载并解压
wget https://github.com/Dazmon88/DD-strategy-bot/archive/refs/heads/main.zip
unzip main.zip
cd DD-strategy-bot-main
```

#### 后续步骤（所有方式通用）

```bash
# 2. 创建虚拟环境（推荐）
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

### Windows

```powershell
# 1. 进入项目根目录
cd C:\path\to\DD-strategy-bot

# 2. 创建虚拟环境（推荐）
python -m venv venv

# 3. 激活虚拟环境
venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt
```

## ⚙️ 配置

编辑 `config.yaml` 文件，配置多个交易所：

```yaml
exchanges:
  standx:
    exchange_name: standx
    private_key: "你的私钥"  # StandX 私钥
    chain: bsc              # 或 "solana"
    symbol: BTC-USD         # 交易对
  
  grvt:
    exchange_name: grvt
    api_key: "你的API Key"           # GRVT API Key
    trading_account_id: "你的交易账户ID"  # GRVT 交易账户ID
    private_key: "你的私钥"          # GRVT 私钥
    env: prod                # 环境：prod, testnet, staging, dev
    symbol: BTC-USDT         # 交易对

grid:
  upper_price: 200000    # 价格上限
  lower_price: 60000     # 价格下限
  price_step: 5          # 价格步长
  grid_count: 5          # 网格数量
  price_spread: 50       # 价格间距
  order_quantity: 0.002  # 每单数量
  sleep_interval: 1      # 循环间隔（秒）

risk:
  enable: true           # 是否启用风险控制
  adx_threshold: 25      # ADX 阈值
  adx_max: 60           # ADX 最大值
```

### 参数说明

#### 交易所配置

**StandX:**
- `private_key`: StandX 钱包私钥
- `chain`: 链类型，`bsc` 或 `solana`
- `symbol`: 交易对，如 `BTC-USD`

**GRVT:**
- `api_key`: GRVT API Key
- `trading_account_id`: GRVT 交易账户ID
- `private_key`: GRVT 私钥
- `env`: 环境，`prod`（生产）、`testnet`（测试网）、`staging`、`dev`
- `symbol`: 交易对，如 `BTC-USDT`（会自动转换为 `BTC_USDT_Perp`）

#### 网格配置

- `price_step`: 网格价格间隔
- `grid_count`: 每个方向的网格数量
- `price_spread`: 当前价格与网格中心的距离
- `order_quantity`: 每个订单的交易数量
- `sleep_interval`: 策略循环间隔时间（秒）

#### 风险控制配置

- `enable`: 是否启用 ADX 动态价格间距调整
- `adx_threshold`: ADX 阈值，低于此值使用默认 `price_spread`
- `adx_max`: ADX 最大值，超过此值按此值处理（ADX 在 25-60 之间动态调整）

## 🚀 运行策略

### 基本用法

```bash
# 确保在虚拟环境中
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 进入策略目录
cd strategys/strategy_common

# 运行策略（必须指定交易所）
python notrade_mm.py --exchange standx
# 或
python notrade_mm.py --exchange grvt
```

### 指定配置文件

```bash
# 使用自定义配置文件
python notrade_mm.py --exchange standx --config config.yaml
```

### 命令行参数

- `-e, --exchange`: **必需**，指定要使用的交易所名称（从 `config.yaml` 的 `exchanges` 中选择）
- `-c, --config`: 可选，指定配置文件路径（默认: `config.yaml`）

## 📺 使用 Screen 后台运行（推荐）

在服务器上运行时，建议使用 `screen` 让策略在后台持续运行，即使断开 SSH 连接也不会中断。

### 安装 Screen

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install screen
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install screen
```

**macOS:**
```bash
brew install screen
```

### Screen 基本用法

#### 1. 创建新的 Screen 会话

```bash
# 创建一个名为 strategy 的会话
screen -S strategy

# 或者直接创建（会自动命名）
screen
```

#### 2. 在 Screen 中运行策略

```bash
# 确保在虚拟环境中
source venv/bin/activate

# 进入策略目录
cd strategys/strategy_common

# 运行策略
python notrade_mm.py --exchange standx
```

#### 3. 分离（detached）Screen 会话

按 `Ctrl + A`，然后按 `D`（先松开 Ctrl+A，再按 D）

或者直接关闭终端窗口，会话会继续在后台运行。

#### 4. 查看所有 Screen 会话

```bash
screen -ls
```

#### 5. 重新连接到 Screen 会话

```bash
# 通过会话名称连接
screen -r strategy

# 或者通过会话 ID 连接
screen -r 12345
```

#### 6. 停止 Screen 会话

**方法一：在会话内停止**
```bash
# 先连接到会话
screen -r strategy

# 按 Ctrl + C 停止策略
# 然后输入 exit 退出会话
exit
```

**方法二：强制停止会话**
```bash
# 如果会话卡住无法连接，可以强制停止
screen -X -S strategy quit
```

### Screen 常用快捷键

在 Screen 会话内，按 `Ctrl + A` 后：

- `D` - 分离会话（detach），让程序继续在后台运行
- `C` - 创建新的窗口
- `N` - 切换到下一个窗口
- `P` - 切换到上一个窗口
- `[` - 进入复制模式（可以滚动查看历史输出）
- `?` - 显示所有快捷键帮助
- `K` - 强制终止当前窗口（会弹出确认提示）

**注意：** 所有快捷键都需要先按 `Ctrl + A`，然后松开，再按对应的字母键。

## 🛑 停止策略

### 在普通终端中运行

按 `Ctrl + C` 停止策略运行

### 在 Screen 会话中运行

1. 连接到 Screen 会话：`screen -r strategy`
2. 按 `Ctrl + C` 停止策略
3. 输入 `exit` 退出会话

## ⚠️ 注意事项

- 确保交易所认证信息（私钥/API Key）安全，不要泄露
- 建议先用小额资金测试
- 策略会持续运行，直到手动停止
- 注意网络连接稳定性
- 建议在 VPS 或服务器上运行
- **必须通过 `--exchange` 参数指定交易所，否则脚本会退出**

## 🔗 相关链接

- [StandX 官网](https://standx.com)
- [GRVT 官网](https://grvt.io)
- [项目主 README](../../README.md)

---

**作者**: [@ddazmon](https://twitter.com/ddazmon)  
**免责声明**: 本策略仅供学习使用，交易有风险，使用需谨慎。
