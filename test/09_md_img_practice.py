"""
实践 3.2：MD 图片处理 - 多模态视觉理解 + MinIO

任务：跟踪一次图片处理的完整数据流。
运行命令: uv run python test/09_md_img_practice.py
"""

import re
from dataclasses import dataclass
from typing import Optional


# ============================================================
# 模拟 VL 模型调用
# ============================================================

def call_vl_model(image_path: str) -> str:
    """模拟 VL 模型理解图片（实际项目中调用 qwen3-vl-flash）"""
    # 模拟返回描述
    descriptions = {
        "warning.jpg": "安全警告图标，红色三角形内带感叹号",
        "diagram.png": "产品内部结构示意图，展示电路板布局",
        "photo.jpg": "产品实物照片，黑色外壳带蓝色指示灯"
    }
    for key, desc in descriptions.items():
        if key in image_path:
            return desc
    return "图片内容（模拟描述）"


# ============================================================
# 模拟 MinIO 上传
# ============================================================

def upload_to_minio(image_path: str, bucket: str = "knowledge-base") -> str:
    """模拟上传图片到 MinIO，返回访问 URL"""
    # 模拟：把本地路径转成 URL
    filename = image_path.split("/")[-1]
    return f"http://localhost:9000/{bucket}/images/{filename}"


# ============================================================
# 任务 1：提取 MD 中的图片标签
# 从 Markdown 文本中提取所有 ![alt](path) 格式的图片
# ============================================================

# TODO: 提取图片标签
# 输入: "这是一张图 ![安全警示](images/warning.jpg) 请注意"
# 输出: [("安全警示", "images/warning.jpg")]
# 提示：使用正则表达式 r'!\[([^\]]*)\]\(([^)]+)\)'

def extract_images(md_content: str) -> list[tuple[str, str]]:
    """提取 MD 中的图片标签，返回 [(alt, path), ...]"""
    # TODO: 实现正则提取
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    return re.findall(pattern, md_content)


# ============================================================
# 任务 2：处理单张图片
# 调用 VL 模型 + 上传 MinIO + 生成替换文本
# ============================================================

# TODO: 处理单张图片
# 输入: alt="安全警示", path="images/warning.jpg"
# 输出: {
#     "alt": "安全警示",
#     "original_path": "images/warning.jpg",
#     "description": "安全警告图标，红色三角形内带感叹号",
#     "url": "http://localhost:9000/knowledge-base/images/warning.jpg"
# }


@dataclass
class ProcessedImage:
    alt: str
    original_path: str
    description: str
    url: str


def process_image(alt: str, path: str) -> ProcessedImage:
    """处理单张图片：VL 理解 + MinIO 上传"""
    # TODO: 调用 call_vl_model 和 upload_to_minio
    description = call_vl_model(path)
    url = upload_to_minio(path)
    return ProcessedImage(
        alt=alt,
        original_path=path,
        description=description,
        url=url
    )


# ============================================================
# 任务 3：替换 MD 中的图片标签
# 把 ![alt](path) 替换成 ![alt](url)\n> description
# ============================================================

# TODO: 替换图片标签
# 输入: md_content + 处理后的图片列表
# 输出: 替换后的 MD 内容

def replace_images(md_content: str, processed: list[ProcessedImage]) -> str:
    """替换 MD 中的图片标签为 URL + 描述"""
    result = md_content
    for img in processed:
        # 原始标签
        original = f"![{img.alt}]({img.original_path})"
        # 新标签：URL + 描述
        new = f"![{img.alt}]({img.url})\n> {img.description}"
        result = result.replace(original, new)
    return result


# ============================================================
# 任务 4：端到端测试
# 完整的 MD 图片处理流程
# ============================================================

# TODO: 用以下 MD 内容测试：
md = """
# 产品安全手册

## 安全警示
![安全警示](images/warning.jpg)
请务必遵守以下安全规范。

## 产品结构
![结构示意图](images/diagram.png)
展示了产品内部电路布局。
"""

# 流程：
#   1. extract_images → 提取图片
#   2. 对每张图片调用 process_image
#   3. replace_images → 替换 MD 内容
#   4. 打印处理后的 MD
images = extract_images(md)
processed = [process_image(alt, path) for alt, path in images]
new_md = replace_images(md, processed)
print(new_md)

# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试 1：提取图片标签")
    print("=" * 60)

    md = """
# 产品安全手册

## 安全警示
![安全警示](images/warning.jpg)
请务必遵守以下安全规范。

## 产品结构
![结构示意图](images/diagram.png)
展示了产品内部电路布局。
"""

    images = extract_images(md)
    print(f"提取到 {len(images)} 张图片:")
    for alt, path in images:
        print(f"  - [{alt}]({path})")

    assert len(images) == 2
    print("✅ 提取成功")

    print("\n" + "=" * 60)
    print("测试 2：处理图片")
    print("=" * 60)

    processed = [process_image(alt, path) for alt, path in images]
    for img in processed:
        print(f"  [{img.alt}]")
        print(f"    描述: {img.description}")
        print(f"    URL: {img.url}")

    assert all(img.url.startswith("http") for img in processed)
    assert all(len(img.description) > 0 for img in processed)
    print("✅ 处理成功")

    print("\n" + "=" * 60)
    print("测试 3：替换 MD 内容")
    print("=" * 60)

    new_md = replace_images(md, processed)
    print(new_md)

    assert "http://localhost:9000" in new_md
    assert "安全警告图标" in new_md
    assert "images/warning.jpg" not in new_md  # 本地路径应被替换
    print("✅ 替换成功")

    print("\n🎉 三个测试全部通过！")
