#!/usr/bin/env python3
# 注释：允许直接执行以查看元数据
from pathlib import Path  # 注释：用于定位文件并读取内容
from setuptools import find_packages, setup  # 注释：导入 setuptools 构建函数

# 注释：定义项目根路径
PROJECT_ROOT = Path(__file__).resolve().parent
# 注释：读取版本号，取首个标记避免行尾注释影响
VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").split()[0]
# 注释：读取 README 作为长描述，兼容 PyPI 展示
LONG_DESCRIPTION = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
# 注释：解析运行时依赖，忽略注释与空行
INSTALL_REQUIRES = [
    line.strip()
    for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]

# 注释：调用 setup() 声明包元信息
setup(
    name="asrprogram",  # 注释：PyPI 包名称
    version=VERSION,  # 注释：使用 VERSION 文件中的版本号
    description="Lightweight word-level timestamp transcription pipeline",  # 注释：简短描述
    long_description=LONG_DESCRIPTION,  # 注释：详细描述
    long_description_content_type="text/markdown",  # 注释：标注 README 格式
    author="ASRProgram Developers",  # 注释：作者信息
    license="MIT",  # 注释：使用 MIT License
    url="https://github.com/example/asrprogram",  # 注释：项目主页占位符
    package_dir={"": "src"},  # 注释：指示源码位于 src 目录
    packages=find_packages("src"),  # 注释：自动发现包
    include_package_data=True,  # 注释：配合 MANIFEST.in 包含额外文件
    install_requires=INSTALL_REQUIRES,  # 注释：运行时依赖列表
    python_requires=">=3.9",  # 注释：最低 Python 版本要求
    entry_points={
        "console_scripts": ["asrprogram=src.cli.main:main"],  # 注释：提供 CLI 入口
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],  # 注释：PyPI 分类标签
    keywords="asr whisper transcription",  # 注释：关键词便于搜索
)
