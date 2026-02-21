"""
MCPBridge - MCP/A2A Protocol Interoperability for BCH
Setup configuration for pip installation.
"""
from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="mcpbridge",
    version="1.0.0",
    author="ATLAS (Team Brain)",
    author_email="atlas@teambrain.metaphy.com",
    description="MCP/A2A Protocol Interoperability for BCH - Internet of Agents Gateway",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DonkRonk17/MCPBridge",
    py_modules=["mcpbridge"],
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "mcpbridge=mcpbridge:main",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="mcp a2a protocol bridge ai agents internet-of-agents bch beacon-hq",
    project_urls={
        "Bug Reports": "https://github.com/DonkRonk17/MCPBridge/issues",
        "Source": "https://github.com/DonkRonk17/MCPBridge",
    },
)
