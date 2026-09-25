from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8") if (this_directory / "README.md").exists() else ""

setup(
    name="codeui",
    version="0.1.0",
    author="Akram Alsubari",
    author_email="akramsubari@gmail.com",
    description="Universal static analysis code intelligence library, defect detector, graph visualizer, and agent context builder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AAlsubari/codeUI",
    project_urls={
        "Bug Tracker": "https://github.com/AAlsubari/codeUI/issues",
        "Source Code": "https://github.com/AAlsubari/codeUI",
        "Documentation": "https://github.com/AAlsubari/codeUI#readme",
    },
    packages=find_packages(include=["codeui", "codeui.*"]),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "mypy>=1.0.0",
            "build",
            "twine",
        ],
    },
    entry_points={
        "console_scripts": [
            "codeui=codeui.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Code Generators",
    ],
    keywords="code-analysis static-analysis code-graph ast ai-agents code-intelligence llm-context",
)
