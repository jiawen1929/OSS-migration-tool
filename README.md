# OSS迁移工具 🚀

> 一个用于将阿里云OSS和腾讯云COS中的文件迁移到MinIO的Python工具。支持断点续传、文件校验、状态追踪等功能。

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.6%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Author](https://img.shields.io/badge/author-Jiawen1929-orange)

</div>

## ✨ 功能特点

### 📦 基础功能
- ✅ 支持从阿里云OSS和腾讯云COS下载文件
- ✅ 支持上传文件到MinIO
- ✅ 保持原始文件路径结构
- ✅ 支持单文件和批量迁移
- ✅ 交互式操作界面

### 🚀 高级特性
- 🛡️ 文件完整性验证（MD5校验）
- 🔄 断点续传支持
- 📊 详细的迁移状态追踪
- 📁 自动跳过目录对象
- 🔁 支持迁移失败重试
- 🔍 MinIO连接测试功能

### 🔐 数据安全
- ✅ 文件上传前后大小校验
- ✅ 下载文件MD5校验
- ✅ 上传验证机制
- ✅ 状态持久化存储

## 💡 实现思路

### 📂 文件组织
- 按来源分别存储（aliyun/tencent目录）
- 保持原始文件路径结构
- 使用JSON文件记录迁移状态

### 📝 状态追踪
- 记录每个文件的下载状态
- 记录文件hash值和大小
- 记录上传状态和时间
- 记录失败原因和时间

### 🔄 断点续传
- 检查本地已下载文件
- 验证文件完整性
- 支持中断后继续
- 自动跳过已完成任务

## 🔧 环境要求

- Python 3.6+
- 依赖包：
  ```
  oss2          # 阿里云OSS SDK
  cos-python-sdk-v5  # 腾讯云COS SDK
  minio         # MinIO Python客户端
  pyyaml        # 配置文件解析
  tqdm          # 进度条显示
  ```

## 📥 安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/jiawen1929/oss-migration-tool.git
   cd oss-migration-tool
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置：
   - 复制 `config.yaml.example` 为 `config.yaml`
   - 填写相关配置信息

## 🚀 快速开始

1. 配置文件设置示例：
   ```yaml
   # 阿里云OSS配置
   aliyun:
     access_key: "your_access_key"    # 从阿里云控制台获取
     access_secret: "your_secret"     # 从阿里云控制台获取
     endpoint: "oss-cn-xxx.com"       # 例如：oss-cn-hangzhou.aliyuncs.com
     bucket: "your-bucket"            # 你的OSS bucket名称

   # 腾讯云COS配置
   tencent:
     secret_id: "your_secret_id"      # 从腾讯云控制台获取
     secret_key: "your_secret_key"    # 从腾讯云控制台获取
     region: "ap-xxx"                 # 例如：ap-guangzhou
     bucket: "your-bucket"            # 你的COS bucket名称

   # MinIO配置
   minio:
     endpoint: "ip:port"              # 例如：192.168.1.100:9000
     access_key: "your_access_key"    # MinIO访问密钥
     secret_key: "your_secret_key"    # MinIO密钥
     bucket: "your-bucket"            # MinIO bucket名称
     secure: false                    # 使用HTTPS则设为true
   ```

2. 运行程序：
   ```bash
   python migrate_to_minio.py
   ```

## 📖 使用指南

### 🔰 第一次使用

1. 首先使用选项9（测试MinIO上传）验证MinIO配置是否正确
2. 使用选项1和2查看需要迁移的文件列表
3. 确认文件列表无误后，开始迁移操作

### 🎯 功能选项

| 选项 | 功能 | 说明 |
|------|------|------|
| 1 | 列出阿里云OSS文件 | 显示文件列表及下载状态 |
| 2 | 列出腾讯云COS文件 | 显示文件列表及下载状态 |
| 3 | 下载阿里云文件 | 支持单个/批量下载 |
| 4 | 下载腾讯云文件 | 支持单个/批量下载 |
| 5 | 上传文件到MinIO | 支持单个/批量上传 |
| 6 | 查看已下载文件 | 显示本地文件状态 |
| 7 | 查看迁移状态 | 显示总体迁移进度 |
| 8 | 验证已上传文件 | 验证文件完整性 |
| 9 | 测试MinIO上传 | 测试连接配置 |

### ⚠️ 注意事项

#### 🔒 配置安全
- 请妥善保管配置文件
- 不要将配置文件提交到代码仓库
- 建议使用环境变量或配置管理工具

#### 💾 存储空间
- 确保本地有足够的存储空间
- 下载目录会按来源分别存储文件
- 注意及时清理已迁移的文件

#### 🌐 网络环境
- 建议在稳定的网络环境下操作
- 支持断点续传，不用担心网络中断
- 大文件传输可能需要较长时间

## ❓ 常见问题

| 问题 | 解决方案 |
|------|----------|
| 配置文件加载失败 | 检查config.yaml格式是否正确 |
| 连接失败 | 检查网络连接和配置信息 |
| 空间不足 | 清理下载目录或增加存储空间 |
| 验证失败 | 重新下载或上传该文件 |

## 📝 License

MIT License

## 👨‍💻 作者

[Jiawen1929](https://www.sujiawen.com)

## 📅 更新日志

### v1.0.0 (2024-03-14)
- 🎉 初始版本发布
- ✨ 支持阿里云OSS和腾讯云COS迁移
- 🔄 支持断点续传和文件验证
