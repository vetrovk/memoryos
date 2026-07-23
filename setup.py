from setuptools import setup


setup(
    name="memoryos-local",
    version="0.2.1",
    description="Local Markdown and SQLite engineering memory system.",
    python_requires=">=3.9",
    packages=["memoryos"],
    entry_points={"console_scripts": ["memory=memoryos.cli:main"]},
)
