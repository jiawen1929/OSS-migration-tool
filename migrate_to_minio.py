import oss2
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from minio import Minio
import os
import hashlib
import json
from datetime import datetime
from tqdm import tqdm
import yaml

def load_config():
    """加载配置文件"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
        return None

# 加载配置
config = load_config()
if not config:
    print("无法加载配置文件，程序退出")
    exit(1)

# 阿里云OSS配置
ali_access_key = config['aliyun']['access_key']
ali_access_secret = config['aliyun']['access_secret']
ali_endpoint = config['aliyun']['endpoint']
ali_bucket = config['aliyun']['bucket']

# 腾讯云COS配置
tx_secret_id = config['tencent']['secret_id']
tx_secret_key = config['tencent']['secret_key']
tx_region = config['tencent']['region']
tx_bucket = config['tencent']['bucket']

# MinIO配置
minio_endpoint = config['minio']['endpoint']
minio_access_key = config['minio']['access_key']
minio_secret_key = config['minio']['secret_key']
minio_bucket = config['minio']['bucket']
minio_secure = config['minio']['secure']

class FileStatus:
    def __init__(self, source_path):
        self.status_file = source_path + '_status.json'
        self.load_status()

    def load_status(self):
        if os.path.exists(self.status_file):
            with open(self.status_file, 'r', encoding='utf-8') as f:
                self.status = json.load(f)
        else:
            self.status = {
                'downloaded': {},  # {file_key: {'hash': 'xxx', 'size': 123, 'time': 'xxx'}}
                'uploaded': {},    # {file_key: {'hash': 'xxx', 'time': 'xxx'}}
                'failed': {}       # {file_key: {'error': 'xxx', 'time': 'xxx'}}
            }

    def save_status(self):
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)

    def mark_downloaded(self, file_key, file_hash, file_size):
        self.status['downloaded'][file_key] = {
            'hash': file_hash,
            'size': file_size,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save_status()

    def mark_uploaded(self, file_key, file_hash):
        self.status['uploaded'][file_key] = {
            'hash': file_hash,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save_status()

    def mark_failed(self, file_key, error):
        self.status['failed'][file_key] = {
            'error': str(error),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save_status()

def get_file_hash(filepath):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def init_clients():
    """初始化所有客户端"""
    try:
        # 初始化阿里云客户端
        auth = oss2.Auth(ali_access_key, ali_access_secret)
        ali_client = oss2.Bucket(auth, ali_endpoint, ali_bucket)
        
        # 初始化腾讯云客户端
        config = CosConfig(Region=tx_region, SecretId=tx_secret_id, SecretKey=tx_secret_key)
        tx_client = CosS3Client(config)
        
        # 初始化MinIO客户端
        minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=minio_secure
        )
        
        return ali_client, tx_client, minio_client
    except Exception as e:
        print(f"初始化客户端时出错: {str(e)}")
        return None, None, None

def get_ali_files(ali_client):
    """获取阿里云OSS的文件列表"""
    print("\n正在获取阿里云OSS文件列表...")
    ali_files = []
    try:
        for obj in oss2.ObjectIterator(ali_client):
            # 跳过以'/'结尾的对象（目录）
            if not obj.key.endswith('/'):
                ali_files.append(obj.key)
        print(f"找到 {len(ali_files)} 个文件")
        return ali_files
    except Exception as e:
        print(f"获取阿里云文件列表失败: {str(e)}")
        return []

def get_tx_files(tx_client):
    """获取腾讯云COS的文件列表"""
    print("\n正在获取腾讯云COS文件列表...")
    tx_files = []
    try:
        marker = ""
        while True:
            response = tx_client.list_objects(tx_bucket, Marker=marker)
            if 'Contents' in response:
                for content in response['Contents']:
                    # 跳过以'/'结尾的对象（目录）
                    if not content['Key'].endswith('/'):
                        tx_files.append(content['Key'])
            if response['IsTruncated'] == 'false':
                break
            marker = response['NextMarker']
        print(f"找到 {len(tx_files)} 个文件")
        return tx_files
    except Exception as e:
        print(f"获取腾讯云文件列表失败: {str(e)}")
        return []

def get_file_info(file_path):
    """获取文件信息（大小和哈希值）"""
    if not os.path.exists(file_path):
        return None, None
    
    size = os.path.getsize(file_path)
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return size, hash_md5.hexdigest()

def get_download_path(file_key, source):
    """获取下载文件的本地保存路径"""
    # 根据来源创建对应的下载目录
    base_dir = os.path.join('downloads', source)
    # 保持原始路径结构
    full_path = os.path.join(base_dir, file_key)
    # 确保目录存在
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return full_path

def download_file(client, file_key, is_ali=True, status_tracker=None):
    """下载单个文件并记录状态"""
    try:
        # 根据来源确定存路径
        source = 'aliyun' if is_ali else 'tencent'
        file_path = get_download_path(file_key, source)
        
        # 检查是否已经下载
        if status_tracker and file_key in status_tracker.status['downloaded']:
            existing_info = status_tracker.status['downloaded'][file_key]
            if os.path.exists(file_path):
                size, file_hash = get_file_info(file_path)
                if file_hash == existing_info['hash']:
                    print(f"文件已存在且校验通过: {file_key}")
                    return True, file_path, file_hash, size
        
        print(f"开始下载: {file_key}")
        if is_ali:
            client.get_object_to_file(file_key, file_path)
        else:
            client.download_file(
                Bucket=tx_bucket,
                Key=file_key,
                DestFilePath=file_path
            )
        
        size, file_hash = get_file_info(file_path)
        
        if status_tracker:
            status_tracker.mark_downloaded(file_key, file_hash, size)
        
        return True, file_path, file_hash, size
    except Exception as e:
        if status_tracker:
            status_tracker.mark_failed(file_key, str(e))
        print(f"下载失败: {str(e)}")
        return False, None, None, None

def verify_minio_upload(minio_client, remote_path, local_file):
    """验证MinIO上传是否成功"""
    try:
        # 获取MinIO中文件的信息
        stat = minio_client.stat_object(minio_bucket, remote_path)
        # 获取本地文件信息
        local_size, local_hash = get_file_info(local_file)
        # 比较大小
        if stat.size != local_size:
            return False, "文件大小不匹配"
        return True, None
    except Exception as e:
        return False, str(e)

def show_migration_summary(status_tracker):
    """显示迁移总结"""
    print("\n=== 迁移状态总结 ===")
    print(f"总下载文件数: {len(status_tracker.status['downloaded'])}")
    print(f"总上传文件数: {len(status_tracker.status['uploaded'])}")
    print(f"失败文件数: {len(status_tracker.status['failed'])}")
    
    if status_tracker.status['failed']:
        print("\n失败的文件:")
        for file_key, info in status_tracker.status['failed'].items():
            print(f"- {file_key}: {info['error']}")

def check_existing_downloads():
    """检查并记录已存在的下载文件"""
    ali_status = FileStatus('aliyun')
    tx_status = FileStatus('tencent')
    
    # 检查阿里云下载目录
    ali_dir = os.path.join('downloads', 'aliyun')
    if os.path.exists(ali_dir):
        for root, _, files in os.walk(ali_dir):
            for file in files:
                full_path = os.path.join(root, file)
                # 跳过隐藏文件和临时文件
                if file.startswith('.') or file.endswith('.tmp'):
                    continue
                relative_path = os.path.relpath(full_path, ali_dir)
                size, file_hash = get_file_info(full_path)
                ali_status.mark_downloaded(relative_path, file_hash, size)
    
    # 检查腾讯云下载目录
    tx_dir = os.path.join('downloads', 'tencent')
    if os.path.exists(tx_dir):
        for root, _, files in os.walk(tx_dir):
            for file in files:
                full_path = os.path.join(root, file)
                # 跳过隐藏文件和临时文件
                if file.startswith('.') or file.endswith('.tmp'):
                    continue
                relative_path = os.path.relpath(full_path, tx_dir)
                size, file_hash = get_file_info(full_path)
                tx_status.mark_downloaded(relative_path, file_hash, size)
    
    return ali_status, tx_status

def test_minio_upload():
    """测试MinIO上传功能"""
    try:
        print("\n=== 开始MinIO上传测试 ===")
        
        # 创建测试文件
        test_content = "���是一个测试文件，用于验证MinIO上传功能。"
        test_file = "minio_test.txt"
        test_remote_path = "test/minio_test.txt"
        
        print("1. 创建测试文件...")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        # 初始化MinIO客户端
        print("2. 连接MinIO服务器...")
        minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=minio_secure
        )
        
        # 确保bucket存在
        print("3. 检查bucket...")
        if not minio_client.bucket_exists(minio_bucket):
            minio_client.make_bucket(minio_bucket)
            print(f"创建bucket: {minio_bucket}")
        else:
            print(f"bucket已存在: {minio_bucket}")
        
        # 上传文件
        print("4. 上传测试文件...")
        minio_client.fput_object(minio_bucket, test_remote_path, test_file)
        
        # 验证上传
        print("5. 验证上传...")
        try:
            stat = minio_client.stat_object(minio_bucket, test_remote_path)
            print(f"文件大小: {stat.size} 字节")
            print(f"上传时间: {stat.last_modified}")
            
            # 下载并验��内容
            print("6. 验证文件内容...")
            test_download = "minio_test_download.txt"
            minio_client.fget_object(minio_bucket, test_remote_path, test_download)
            
            with open(test_download, 'r', encoding='utf-8') as f:
                downloaded_content = f.read()
            
            if downloaded_content == test_content:
                print("文件内容验证通过！")
            else:
                print("警告：文件内容不匹配！")
            
            # 清理测试文件
            print("7. 清理测试文件...")
            os.remove(test_file)
            os.remove(test_download)
            minio_client.remove_object(minio_bucket, test_remote_path)
            
            print("\n测试完成：MinIO配置正常，可开始迁移！")
            return True
            
        except Exception as e:
            print(f"验证失败: {str(e)}")
            return False
            
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        return False
    finally:
        # 确保清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(test_download):
            os.remove(test_download)

def main():
    # 初始化客户端
    print("正在初始化客户端...")
    ali_client, tx_client, minio_client = init_clients()
    if not all([ali_client, tx_client, minio_client]):
        print("初始化失败，程序退出")
        return

    # 检查已存在的下载文件
    print("正在检查已下载的文件...")
    ali_status, tx_status = check_existing_downloads()

    while True:
        print("\n=== 文件迁移工具 ===")
        print("By Jiawen1929[www.sujiawen.com]\n\n")
        print("1. 列出阿里云OSS文件")
        print("2. 列出腾讯云COS文件")
        print("3. 下载阿里云文件")
        print("4. 下载腾讯云文件")
        print("5. 上传文件到MinIO")
        print("6. 查看已下载文件")
        print("7. ��看迁移状态")
        print("8. 验证已上传文件")
        print("9. 测试MinIO上传")
        print("0. 退出")
        
        choice = input("\n请选择操作 (0-9): ")
        
        if choice == '1':
            files = get_ali_files(ali_client)
            print("\n文件列表：")
            for i, f in enumerate(files, 1):
                status = "已下载" if f in ali_status.status['downloaded'] else "未下载"
                print(f"{i}. {f} [{status}]")
        
        elif choice == '2':
            files = get_tx_files(tx_client)
            print("\n文件列表：")
            for i, f in enumerate(files, 1):
                status = "已下载" if f in tx_status.status['downloaded'] else "未下载"
                print(f"{i}. {f} [{status}]")
        
        elif choice == '3':
            files = get_ali_files(ali_client)
            if not files:
                continue
                
            print("\n可下载的文件：")
            for i, f in enumerate(files, 1):
                status = "已下载" if f in ali_status.status['downloaded'] else "未下载"
                print(f"{i}. {f} [{status}]")
                
            idx = input("\n请选择要下载的文件序号 (输入all下载全部): ")
            if idx.lower() == 'all':
                for f in tqdm(files, desc="下载进度"):
                    if f not in ali_status.status['downloaded']:
                        success, path, file_hash, size = download_file(
                            ali_client, f, True, ali_status
                        )
                        if success:
                            print(f"\n成功下载: {f}")
                            print(f"保存位置: {path}")
                            print(f"文件大小: {size/1024:.2f}KB")
                            print(f"文件Hash: {file_hash}")
            else:
                try:
                    idx = int(idx) - 1
                    if 0 <= idx < len(files):
                        success, path, file_hash, size = download_file(
                            ali_client, files[idx], True, ali_status
                        )
                        if success:
                            print(f"成功下载: {files[idx]}")
                            print(f"保存位置: {path}")
                            print(f"文件大小: {size/1024:.2f}KB")
                            print(f"文件Hash: {file_hash}")
                except ValueError:
                    print("无效的输入")
        
        elif choice == '4':
            files = get_tx_files(tx_client)
            if not files:
                continue
                
            print("\n可下载的文件：")
            for i, f in enumerate(files, 1):
                status = "已下载" if f in tx_status.status['downloaded'] else "未下载"
                print(f"{i}. {f} [{status}]")
                
            idx = input("\n请选择要下载的文件序号 (输入all下载全部): ")
            if idx.lower() == 'all':
                for f in tqdm(files, desc="下载进度"):
                    if f not in tx_status.status['downloaded']:
                        success, path, file_hash, size = download_file(
                            tx_client, f, False, tx_status
                        )
                        if success:
                            print(f"\n成功下载: {f}")
                            print(f"保存位置: {path}")
                            print(f"文件大小: {size/1024:.2f}KB")
                            print(f"文件Hash: {file_hash}")
            else:
                try:
                    idx = int(idx) - 1
                    if 0 <= idx < len(files):
                        success, path, file_hash, size = download_file(
                            tx_client, files[idx], False, tx_status
                        )
                        if success:
                            print(f"成功下载: {files[idx]}")
                            print(f"保存位置: {path}")
                            print(f"文件大小: {size/1024:.2f}KB")
                            print(f"文件Hash: {file_hash}")
                except ValueError:
                    print("无效的输入")
        
        elif choice == '5':
            print("\n正在扫描下载目录...")
            all_files = []
            
            # 扫描阿里云目录
            ali_dir = os.path.join('downloads', 'aliyun')
            if os.path.exists(ali_dir):
                for root, _, files in os.walk(ali_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, ali_dir)
                        all_files.append(('aliyun', relative_path, full_path))
            
            # 扫描腾讯云目录
            tx_dir = os.path.join('downloads', 'tencent')
            if os.path.exists(tx_dir):
                for root, _, files in os.walk(tx_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, tx_dir)
                        all_files.append(('tencent', relative_path, full_path))
            
            if not all_files:
                print("没有找到可上传的文件")
                continue
            
            print("\n可上传的文件：")
            for i, (source, relative_path, full_path) in enumerate(all_files, 1):
                size, _ = get_file_info(full_path)
                status_tracker = ali_status if source == 'aliyun' else tx_status
                uploaded = "已上传" if relative_path in status_tracker.status['uploaded'] else "未上传"
                print(f"{i}. [{source}] {relative_path} ({size/1024:.2f}KB) [{uploaded}]")
            
            idx = input("\n请选择要上传的文件序号 (输入all上传全部): ")
            if idx.lower() == 'all':
                for source, relative_path, full_path in tqdm(all_files, desc="上传进度"):
                    status_tracker = ali_status if source == 'aliyun' else tx_status
                    if relative_path not in status_tracker.status['uploaded']:
                        print(f"\n正在上传: [{source}] {relative_path}")
                        try:
                            minio_client.fput_object(minio_bucket, relative_path, full_path)
                            success, error = verify_minio_upload(minio_client, relative_path, full_path)
                            if success:
                                print("上传成功并验证通过")
                                size, file_hash = get_file_info(full_path)
                                status_tracker.mark_uploaded(relative_path, file_hash)
                            else:
                                print(f"上传验证失败: {error}")
                        except Exception as e:
                            print(f"上传失败: {str(e)}")
            else:
                try:
                    idx = int(idx) - 1
                    if 0 <= idx < len(all_files):
                        source, relative_path, full_path = all_files[idx]
                        status_tracker = ali_status if source == 'aliyun' else tx_status
                        print(f"\n正在上传: [{source}] {relative_path}")
                        try:
                            minio_client.fput_object(minio_bucket, relative_path, full_path)
                            success, error = verify_minio_upload(minio_client, relative_path, full_path)
                            if success:
                                print("上传成功并验证通过")
                                size, file_hash = get_file_info(full_path)
                                status_tracker.mark_uploaded(relative_path, file_hash)
                            else:
                                print(f"上传验证失败: {error}")
                        except Exception as e:
                            print(f"上传失败: {str(e)}")
                except ValueError:
                    print("无效的输入")
        
        elif choice == '6':
            print("\n=== 已下载的文件 ===")
            
            # 显示阿里云文件
            ali_dir = os.path.join('downloads', 'aliyun')
            if os.path.exists(ali_dir):
                print("\n阿里云文件：")
                for root, _, files in os.walk(ali_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, ali_dir)
                        size, file_hash = get_file_info(full_path)
                        uploaded = "已上传" if relative_path in ali_status.status['uploaded'] else "未上传"
                        print(f"- {relative_path} ({size/1024:.2f}KB) [{uploaded}]")
            
            # 显示腾讯云文件
            tx_dir = os.path.join('downloads', 'tencent')
            if os.path.exists(tx_dir):
                print("\n腾讯云文件：")
                for root, _, files in os.walk(tx_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, tx_dir)
                        size, file_hash = get_file_info(full_path)
                        uploaded = "已上传" if relative_path in tx_status.status['uploaded'] else "未上传"
                        print(f"- {relative_path} ({size/1024:.2f}KB) [{uploaded}]")
        
        elif choice == '7':
            print("\n=== 阿里云迁移状态 ===")
            show_migration_summary(ali_status)
            print("\n=== 腾讯云迁移状态 ===")
            show_migration_summary(tx_status)
        
        elif choice == '8':
            print("\n开始验证已上传文件...")
            all_uploaded = list(ali_status.status['uploaded'].keys()) + list(tx_status.status['uploaded'].keys())
            for remote_path in tqdm(all_uploaded, desc="验证进度"):
                local_path = os.path.join('downloads', remote_path.replace('/', '_'))
                if os.path.exists(local_path):
                    success, error = verify_minio_upload(minio_client, remote_path, local_path)
                    if success:
                        print(f"文件验证通过: {remote_path}")
                    else:
                        print(f"文件验证失���: {remote_path} - {error}")
                else:
                    print(f"本地文件不存在: {local_path}")
        
        elif choice == '9':
            test_minio_upload()
        
        elif choice == '0':
            print("程序退出")
            break
        
        else:
            print("无效的选择，请重试")

if __name__ == '__main__':
    main() 